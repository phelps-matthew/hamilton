import asyncio
import logging
from datetime import datetime, timezone, timedelta
from hamilton.base.task import Task, TaskGenerator
from hamilton.operators.orchestrator.client import OrchestratorClient
from hamilton.operators.astrodynamics.client import AstrodynamicsClient
from hamilton.common.utils import utc_to_local

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, shutdown_event: asyncio.Event = None):
        try:
            self.task_generator: TaskGenerator = TaskGenerator()
            self.orchestrator: OrchestratorClient = OrchestratorClient()
            self.astrodynamics: AstrodynamicsClient = AstrodynamicsClient()
        except Exception as e:
            logger.error(f"An error occurred while initializing Scheduler: {e}")
        self.client_list = [self.task_generator, self.orchestrator, self.astrodynamics]
        self.last_dispatched_task = None
        self.is_running = False
        self.dispatch_buffer = timedelta(minutes=6)
        self.queue_length = 10
        self.task_queue: asyncio.Queue = asyncio.Queue(maxsize=self.queue_length)
        self.shutdown_event: asyncio.Event = shutdown_event
        self.orchestrator_is_ready = asyncio.Event()
        self.current_mode = None
        self.mode_change_event = asyncio.Event()

    async def start(self):
        logger.info("Starting Scheduler.")
        self.is_running = True
        for client in self.client_list:
            try:
                await client.start()
            except Exception as e:
                logger.error(f"An error occurred while starting {client}: {e}")
        orchestrator_status = await self.orchestrator.status()
        logger.info(f"Orchestrator status: {orchestrator_status}")
        await self.set_orchestrator_status_event(**orchestrator_status)
        logger.info(f"Orchestrator status event is set: {self.orchestrator_is_ready.is_set()}")
        await self.set_mode("inactive")

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
        queue_list = [self.format_task_details(task) for task in self.task_queue._queue]
        last_dispatched_task = self.format_task_details(self.last_dispatched_task)
        return {
            "mode": self.current_mode,
            "is_running": self.is_running,
            "queue": queue_list,
            "last_dispatched_task": last_dispatched_task,
        }

    async def set_orchestrator_status_event(self, status: str):
        if status == "idle":
            self.orchestrator_is_ready.set()
            logger.info("Orchestrator ready event set.")
        elif status == "active":
            self.orchestrator_is_ready.clear()
            logger.info("Orchestrator read event cleared.")

    def format_task_details(self, task) -> dict:
        task_details = {}
        if task:
            task_details["sat_id"] = task["parameters"]["sat_id"]
            task_details["aos"] = utc_to_local(task["parameters"]["aos"]["time"])
            task_details["los"] = utc_to_local(task["parameters"]["los"]["time"])
        return task_details

    async def retrieve_tasks_from_db(self, start_time: datetime = None, end_time: datetime = None) -> list[Task]:
        """Retrieve satellite records with AOS between `start_time` and `end_time`, ascending in AOS."""
        if start_time is None:
            start_time = datetime.now(timezone.utc)
        if end_time is None:
            end_time = datetime.now(timezone.utc) + timedelta(hours=1)
        sats_aos_los = await self.astrodynamics.get_all_aos_los(start_time, end_time)
        task_list = []
        for sat_id, aos, los in sats_aos_los:
            task = await self.task_generator.generate_task(sat_id)
            if task is not None:
                task_list.append(task)

        logger.info(f"Tasks retrieved: {len(task_list)}")
        return task_list

    async def enqueue_task_manual(self, task: Task):
        """Force insert a specific task into the queue, such as that received from a CollectRequest."""
        await self.task_queue.put(task)

    async def enqueue_tasks(self):
        """Enqueue tasks, respecting dispatch buffer time and AOS/LOS overlap."""
        if self.task_queue.full():
            return

        if self.task_queue.empty():
            if self.last_dispatched_task is None:
                # No previous task, start from the current time
                start_time = datetime.now(timezone.utc)
            else:
                # Use the LOS of the last dispatched task plus the buffer
                start_time = self.last_dispatched_task["parameters"]["los"]["time"] + self.dispatch_buffer
        else:
            last_task = self.task_queue._queue[-1]
            start_time = last_task["parameters"]["los"]["time"] + self.dispatch_buffer

        end_time = start_time + timedelta(hours=4)
        tasks = await self.retrieve_tasks_from_db(start_time=start_time, end_time=end_time)
        for task in tasks:
            aos = task["parameters"]["aos"]["time"]
            los = task["parameters"]["los"]["time"]
            if self.task_queue.empty() or (
                aos >= self.task_queue._queue[-1]["parameters"]["los"]["time"] + self.dispatch_buffer
            ):
                logger.info(f"Adding task_id:{task['task_id']}, sat_id:{task['parameters']['sat_id']} to queue")
                await self.task_queue.put(task)
                if self.task_queue.full():
                    break
        logger.info(f"Queue length: {self.task_queue.qsize()}")
        for task in self.task_queue._queue:
            aos = task["parameters"]["aos"]["time"].isoformat()
            los = task["parameters"]["los"]["time"].isoformat()
            logger.info(f"aos: {aos}, los: {los}")

    async def dispatch_task_from_queue(self, task) -> None:
        """Dispatch the next task from the queue to the orchestrator."""
        # await self.orchestrator.orchestrate(task)
        self.last_dispatched_task = task

    async def wait_until_first_completed(self, events: list[asyncio.Event], coroutines: list = None):
        """Wait until the first event or coroutine in the list is completed and return the completed task."""
        if coroutines is None:
            coroutines = []
        event_tasks = [asyncio.create_task(event.wait()) for event in events]
        coroutine_tasks = [asyncio.create_task(coro) for coro in coroutines]
        done, pending = await asyncio.wait(event_tasks + coroutine_tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        return done.pop()

    async def set_mode(self, mode: str = "survey") -> None:
        """Switch between different modes of operation."""
        self.current_mode = mode
        self.mode_change_event.set()  # Signal mode change
        self.mode_change_event.clear()  # Reset the event for future use
        if mode == "survey":
            await self.run_survey()
        elif mode == "standby":
            await self.run_standby()
        elif mode == "inactive":
            await self.run_inactive()
        else:
            logger.error(f"Unknown mode: {mode}")

    async def run_survey(self):
        """Run survey mode to continuously enqueue and dispatch tasks."""
        logger.info("Running survey mode.")
        while self.current_mode == "survey" and not self.shutdown_event.is_set():
            logger.info("Waiting for orchestrator to be idle..")
            await self.wait_until_first_completed(
                [self.orchestrator_is_ready, self.mode_change_event, self.shutdown_event]
            )
            if self.current_mode != "survey" or self.shutdown_event.is_set():
                break
            logger.info("Enqueuing new tasks..")
            await self.enqueue_tasks()
            next_async_task = await self.wait_until_first_completed(
                [self.mode_change_event, self.shutdown_event], [self.task_queue.get()]
            )
            if self.current_mode != "survey" or self.shutdown_event.is_set():
                break
            next_task = next_async_task.result()
            sleep_time = (next_task["parameters"]["aos"]["time"] - datetime.now(timezone.utc)).total_seconds()
            sleep_time -= 60  # time to slew to AOS
            if sleep_time > 0:
                logger.info(f"Sleeping until (AOS - 60s) for {sleep_time} seconds..")
                await self.wait_until_first_completed(
                    [self.mode_change_event, self.shutdown_event], [asyncio.sleep(sleep_time)]
                )
            if self.current_mode != "survey" or self.shutdown_event.is_set():
                break
            logger.info("Dispatching task from queue.")
            await self.dispatch_task_from_queue(next_task)

    async def run_standby(self):
        """Run standby mode to dispatch manually inserted tasks."""
        logger.info("Running standby mode.")
        while self.current_mode == "standby" and not self.shutdown_event.is_set():
            logger.info("Waiting for orchestrator to be idle..")
            await self.wait_until_first_completed(
                [self.orchestrator_is_ready, self.mode_change_event, self.shutdown_event]
            )
            if self.current_mode != "standby" or self.shutdown_event.is_set():
                break
            logger.info("Waiting for non-empty queue..")
            next_async_task = await self.wait_until_first_completed(
                [self.mode_change_event, self.shutdown_event], [self.task_queue.get()]
            )
            next_task = next_async_task.result()
            if self.current_mode != "standby" or self.shutdown_event.is_set():
                break
            sleep_time = (next_task["parameters"]["aos"]["time"] - datetime.now(timezone.utc)).total_seconds()
            sleep_time -= 60  # time to slew to AOS
            if sleep_time > 0:
                logger.info(f"Sleeping until (AOS - 60s) for {sleep_time} seconds..")
                await self.wait_until_first_completed(
                    [self.mode_change_event, self.shutdown_event], [asyncio.sleep(sleep_time)]
                )
            if self.current_mode != "standby" or self.shutdown_event.is_set():
                break
            logger.info("Dispatching task from queue.")
            await self.dispatch_task_from_queue(next_task)

    async def run_inactive(self):
        """Deactivate all scheduling."""
        logger.info("Running inactive mode. No tasks will be dispatched.")
        await self.wait_until_first_completed([self.shutdown_event, self.mode_change_event])
