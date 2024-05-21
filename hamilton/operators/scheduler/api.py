import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from hamilton.base.task import Task, TaskGenerator
from hamilton.operators.orchestrator.client import OrchestratorClient
from hamilton.operators.astrodynamics.client import AstrodynamicsClient

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self):
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
        self.shutdown_event = asyncio.Event()
        self.orchestrator_status_event = asyncio.Event()
        self.current_mode = None

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
            "queue": list(self.task_queue._queue),
        }

    async def set_orchestrator_status_event(self, status: str):
        if status == "active":
            self.orchestrator_status_event.set()
        elif status == "idle":
            self.orchestrator_status_event.clear()

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
        await self.orchestrator.orchestrate(task)
        self.last_dispatched_task = task

    async def set_mode(self, mode: str = "survey") -> None:
        """Switch between different modes of operation."""
        self.current_mode = mode
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
            logger.info("Waiting for orchestrator status event.")
            await self.orchestrator_status_event.wait()
            logger.info("Orchestrator status event set. Enqueuing new tasks.")
            await self.enqueue_tasks()
            next_task = await self.task_queue.get()
            sleep_time = (next_task["parameters"]["aos"]["time"] - datetime.now(timezone.utc)).total_seconds()
            sleep_time -= 60 # time to slew to AOS
            if sleep_time > 0:
                logger.info(f"Sleeping until AOS for {sleep_time} seconds.")
                await asyncio.sleep(sleep_time)
            logger.info("Dispatching task from queue.")
            await self.dispatch_task_from_queue(next_task)

    async def run_standby(self):
        """Run standby mode to dispatch manually inserted tasks."""
        logger.info("Running standby mode.")
        while self.current_mode == "standby" and not self.shutdown_event.is_set():
            logger.info("Waiting for orchestrator status event.")
            await self.orchestrator_status_event.wait()
            logger.info("Orchestrator status event set.")
            logger.info("Waiting for non-empty queue")
            next_task = await self.task_queue.get()
            sleep_time = (next_task["parameters"]["aos"]["time"] - datetime.now(timezone.utc)).total_seconds()
            sleep_time -= 60 # time to slew to AOS
            if sleep_time > 0:
                logger.info(f"Sleeping until AOS for {sleep_time} seconds.")
                await asyncio.sleep(sleep_time)
            logger.info("Dispatching task from queue.")
            await self.dispatch_task_from_queue(next_task)

    async def run_inactive(self):
        """Deactivate all scheduling."""
        logger.info("Scheduler is inactive. No tasks will be dispatched.")
        while self.current_mode == "inactive" and not self.shutdown_event.is_set():
            await asyncio.sleep(10)  # Sleep to prevent busy-waiting
