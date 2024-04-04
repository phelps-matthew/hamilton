import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from hamilton.base.task import Task, TaskType
from hamilton.operators.radiometrics.client import RadiometricsClient
from hamilton.operators.astrodynamics.client import AstrodynamicsClient
from hamilton.operators.orchestrator.client import OrchestratorClient

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, orchestrator):
        self.radiometrics: RadiometricsClient = None
        self.astrodynamics: AstrodynamicsClient = None
        self.orchestrator: OrchestratorClient = orchestrator
        self.client_list = [self.radiometrics, self.astrodynamics, self.orchestrator]
        self.targets: list[str] = []
        self.task_queue: list[Task] = []
        self.queue_non_empty_event = asyncio.Event()
        self.is_running = False
        self.refresh_interval = timedelta(hours=2)
        self.dispatch_buffer = timedelta(minutes=2)

    async def start(self):
        logger.info("Starting Scheduler.")
        self.is_running = True
        for client in self.client_list:
            try:
                await client.start()
            except Exception as e:
                logger.error(f"An error occurred while starting {client}: {e}")

    async def stop(self):
        logger.info("Stopping Scheduler.")
        await self.stop_scheduling()
        for client in self.client_list:
            try:
                await client.stop()
            except Exception as e:
                logger.error(f"An error occurred while stopping {client}: {e}")

    async def stop_scheduling(self):
        self.is_running = False
        self.shutdown_event.set()
        logger.info("Scheduling loop stopped.")

    async def status(self) -> dict:
        return {
            "is_running": self.is_running,
            "targets": self.targets,
            "queued_tasks": [task["task_id"] for task in self.task_queue],
        }

    async def add_target(self, sat_id: str):
        if sat_id not in self.targets:
            self.targets.append(sat_id)
            logger.info(f"Added target: {sat_id}")
        else:
            logger.warning(f"Target {sat_id} already exists.")

    async def remove_target(self, sat_id: str):
        if sat_id in self.targets:
            self.targets.remove(sat_id)
            logger.info(f"Removed target: {sat_id}")
        else:
            logger.warning(f"Target {sat_id} does not exist.")

    async def force_refresh(self):
        logger.info("Forcing task refresh.")
        await self._refresh_tasks()

    async def run(self):
        logger.info("Starting scheduling loop.")
        while self.is_running and not self.shutdown_event.is_set():
            await self._refresh_tasks()
            await self._dispatch_tasks()
            await asyncio.wait(
                [self.shutdown_event.wait(), asyncio.sleep(self.dispatch_buffer.total_seconds())],
                return_when=asyncio.FIRST_COMPLETED,
            )

    async def _refresh_tasks(self):
        logger.info("Refreshing tasks.")
        new_tasks = []
        for sat_id in self.targets:
            task = await self._generate_task(sat_id)
            if task:
                new_tasks.append(task)
        if new_tasks:
            self._update_task_queue(new_tasks)
            self.queue_non_empty_event.set()

    def _update_task_queue(self, new_tasks: list[Task]):
        self.task_queue = self._remove_matching_tasks(self.task_queue, new_tasks)
        self.task_queue.extend(new_tasks)
        self.task_queue.sort(key=lambda t: t["parameters"]["aos"]["time"])
        self.task_queue = self._remove_overlapping_tasks(self.task_queue)

    def _remove_matching_tasks(self, existing_tasks: list[Task], new_tasks: list[Task]) -> list[Task]:
        non_matching_tasks = []
        for existing_task in existing_tasks:
            if not any(self._tasks_match(existing_task, new_task) for new_task in new_tasks):
                non_matching_tasks.append(existing_task)
        return non_matching_tasks

    def _tasks_match(self, task1: Task, task2: Task) -> bool:
        return (
            task1["parameters"]["sat_id"] == task2["parameters"]["sat_id"]
            and task1["parameters"]["aos"]["time"] == task2["parameters"]["aos"]["time"]
            and task1["parameters"]["los"]["time"] == task2["parameters"]["los"]["time"]
        )

    def _remove_overlapping_tasks(self, tasks: list[Task]) -> list[Task]:
        non_overlapping_tasks = []
        for task in tasks:
            if not any(self._tasks_overlap(task, t) for t in non_overlapping_tasks):
                non_overlapping_tasks.append(task)
        return non_overlapping_tasks

    def _tasks_overlap(self, task1: Task, task2: Task) -> bool:
        aos1 = task1["parameters"]["aos"]["time"]
        los1 = task1["parameters"]["los"]["time"]
        aos2 = task2["parameters"]["aos"]["time"]
        los2 = task2["parameters"]["los"]["time"]

        return (aos1 <= aos2 <= los1) or (aos1 <= los2 <= los1) or (aos2 <= aos1 <= los2) or (aos2 <= los1 <= los2)

    async def _dispatch_tasks(self):
        while not self.shutdown_event.is_set():
            # Wait until the queue is non-empty or the shutdown event is set
            if not self.task_queue:
                await asyncio.wait(
                    [self.shutdown_event.wait(), self.queue_non_empty_event.wait()], return_when=asyncio.FIRST_COMPLETED
                )
                if self.shutdown_event.is_set():
                    break  # Exit if the scheduler is stopping

            # It's possible for the task queue to become empty again before this point, so check again
            while self.task_queue and not self.shutdown_event.is_set():
                self.queue_non_empty_event.clear()  # Clear the event until new tasks are added again
                current_time = datetime.now(timezone.utc)
                task = self.task_queue[0]
                aos_time = task["parameters"]["aos"]["time"]
                los_time = task["parameters"]["los"]["time"]
                time_until_aos = (aos_time - current_time).total_seconds() - self.dispatch_buffer.total_seconds()

                if time_until_aos > 0:
                    # Wait until it's time to dispatch the task, considering the dispatch buffer
                    await asyncio.wait(
                        [self.shutdown_event.wait(), asyncio.sleep(time_until_aos)], return_when=asyncio.FIRST_COMPLETED
                    )
                    if self.shutdown_event.is_set():
                        break  # Exit if the scheduler is stopping

                # Re-check the current time after waiting
                current_time = datetime.now(timezone.utc)
                if current_time >= aos_time - self.dispatch_buffer and current_time <= los_time:
                    self.task_queue.pop(0)
                    await self.orchestrator.orchestrate(task)
                    logger.info(f"Dispatched task: {task['task_id']}")
                    # Wait until LOS time or shutdown event
                    await asyncio.wait(
                        [self.shutdown_event.wait(), asyncio.sleep((los_time - current_time).total_seconds())],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    await self.orchestrator.stop_tracking()
                    logger.info(f"Task {task['task_id']} completed.")
                else:
                    # If the current time is beyond LOS, remove the task without dispatching
                    self.task_queue.pop(0)
                    logger.info(f"Task {task['task_id']} skipped, beyond LOS time.")

    async def _generate_task(self, sat_id: str) -> Optional[Task]:
        aos_los = await self.astrodynamics.get_aos_los(sat_id)
        interpolated_orbit = await self.astrodynamics.interpolate_orbit(sat_id)
        downlink_freqs = await self.radiometrics.get_downlink_freqs(sat_id)

        task = {
            "source": "hamilton",
            "timestamp": datetime.now().isoformat(),
            "task_id": str(uuid.uuid4()),
            "task_type": "leo_track",
            "parameters": {
                "sat_id": sat_id,
                "aos": aos_los.get("aos", None),
                "tca": aos_los.get("tca", None),
                "los": aos_los.get("los", None),
                "sdr": {"sat_id": sat_id, "freq": downlink_freqs[0]},
                "interpolated_orbit": interpolated_orbit,
            },
        }

        if self._validate_task(task):
            return task
        else:
            logger.error(f"Generated task for {sat_id} is invalid.")
            return None

    def _validate_task(self, task: Task) -> bool:
        parameters = task["parameters"]
        if not parameters:
            return False
        try:
            aos_time = parameters["aos"]["time"]
            los_time = parameters["los"]["time"]
        except KeyError:
            return False
        current_time = datetime.now(timezone.utc)

        if aos_time and los_time and aos_time < los_time and los_time > current_time:
            return True
        else:
            return False
