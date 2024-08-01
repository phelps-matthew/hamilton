import asyncio
import logging
from datetime import datetime, timezone, timedelta
from hamilton.base.task import Task, TaskGenerator
from hamilton.operators.orchestrator.client import OrchestratorClient
from hamilton.operators.astrodynamics.client import AstrodynamicsClient
from hamilton.common.utils import utc_to_local, wait_until_first_completed

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
        self.current_task = None
        self.is_running = False
        self.shutdown_event: asyncio.Event = shutdown_event
        self.orchestrator_is_ready = asyncio.Event()
        self.current_mode = None
        self.mode_change_event = asyncio.Event()
        self.new_task_event = asyncio.Event()

        self.dispatch_buffer = timedelta(minutes=6)
        self.queue_length = 10
        self.task_queue: asyncio.Queue = asyncio.Queue(maxsize=self.queue_length)
        self.collect_request_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()

    async def start(self):
        """Start the scheduler and its clients."""
        logger.info("Starting Scheduler.")
        self.is_running = True
        for client in self.client_list:
            try:
                await client.start()
            except Exception as e:
                logger.error(f"An error occurred while starting {client}: {e}")
        orchestrator_status = await self.orchestrator.status()
        logger.info(f"Orchestrator status: {orchestrator_status}")
        if orchestrator_status is not None:
            await self.set_orchestrator_status_event(**orchestrator_status)
            logger.info(f"Orchestrator status event is set: {self.orchestrator_is_ready.is_set()}")
        await self.set_mode("inactive")

    async def stop(self):
        """Stop the scheduler and its clients."""
        logger.info("Stopping Scheduler.")
        await self.stop_scheduling()
        for client in self.client_list:
            try:
                await client.stop()
            except Exception as e:
                logger.error(f"An error occurred while stopping {client}: {e}")

    async def status(self) -> dict:
        """Get the current status of the scheduler."""
        task_queue = [self.format_task_details(task) for task in self.task_queue._queue]
        collect_request_queue = [self.format_task_details(cr[1]) for cr in self.collect_request_queue._queue]
        last_dispatched_task = self.format_task_details(self.last_dispatched_task)
        current_task = self.format_task_details(self.current_task)
        return {
            "mode": self.current_mode,
            "is_running": self.is_running,
            "task_queue": task_queue,
            "collect_request_queue": collect_request_queue,
            "last_dispatched_task": last_dispatched_task,
            "current_task": current_task,
        }

    async def stop_scheduling(self):
        """Stop the scheduling loop."""
        self.is_running = False
        self.shutdown_event.set()
        logger.info("Scheduling loop stopped.")

    async def enqueue_tasks_survey(self):
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
        tasks = await self.retrieve_tasks_from_astrodynamics(start_time=start_time, end_time=end_time)
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

    async def enqueue_collect_request_task(self, task: Task):
        """Enqueue a specific task into the collect request queue."""
        logger.info(f"Enqueueing collect request task: {task['task_id']}")
        await self.collect_request_queue.put((task["parameters"]["aos"]["time"], task))
        await self.sort_collect_request_queue()
        self.new_task_event.set()

    async def sort_collect_request_queue(self):
        """Validate tasks in the priority queue and ensure enough break time between tasks and that AOS is in the future."""
        logger.info(f"Sorting collect request queue of current size: {self.collect_request_queue.qsize()}")
        current_time_plus_60 = datetime.now(timezone.utc) + timedelta(seconds=60)
        tasks = []
        while not self.collect_request_queue.empty():
            tasks.append(await self.collect_request_queue.get())

        # Sort tasks based on AOS time
        tasks.sort(key=lambda x: x[0])

        # Validate tasks
        valid_tasks = []
        for i in range(len(tasks)):
            task_aos_time = tasks[i][1]["parameters"]["aos"]["time"]
            if (i == 0 or (task_aos_time - tasks[i - 1][1]["parameters"]["los"]["time"]) >= self.dispatch_buffer) and (
                task_aos_time > current_time_plus_60
            ):
                valid_tasks.append(tasks[i])
            else:
                await self.send_rejected_collect_response(tasks[i][1])

        # Reinsert valid tasks into the priority queue
        for task in valid_tasks:
            await self.collect_request_queue.put(task)
        logger.info(f"Finished sorting collect request queue")

    async def dispatch_task_to_orchestrator(self, task) -> None:
        """Dispatch the next task from the queue to the orchestrator."""
        await self.orchestrator.orchestrate(task)
        self.last_dispatched_task = task

    async def set_mode(self, mode: str = "survey") -> None:
        """Switch between different modes of operation."""
        self.current_mode = mode
        self.mode_change_event.set()  # Signal mode change
        self.mode_change_event.clear()  # Reset the event for future use
        if mode == "survey":
            await self.clear_queue()
            await self.run_survey()
        elif mode == "inactive":
            await self.clear_queue()
            await self.run_inactive()
        elif mode == "collect_request":
            await self.sort_collect_request_queue()
            await self.run_collect_request()
        else:
            logger.error(f"Unknown mode: {mode}")

    async def run_survey(self):
        """Run survey mode to continuously enqueue and dispatch tasks."""
        logger.info("Running survey mode.")
        while self.current_mode == "survey" and not self.shutdown_event.is_set():

            # Enqueue tasks once the orchestrator is free
            logger.info("Waiting for orchestrator to be idle..")
            await wait_until_first_completed(
                [self.orchestrator_is_ready, self.mode_change_event, self.shutdown_event]
            )
            if self.current_mode != "survey" or self.shutdown_event.is_set():
                return
            logger.info("Enqueuing new tasks..")
            await self.enqueue_tasks_survey()

            # Get the next task from the queue
            self.current_task = await self.task_queue.get()
            logger.info(f"Next task: {self.format_task_details(self.current_task)}")

            # Sleep until AOS (minus slew time) of next task. If orchestrator finishes first, break the sleep.
            sleep_time = (self.current_task["parameters"]["aos"]["time"] - datetime.now(timezone.utc)).total_seconds()
            sleep_time -= 60  # time to slew to AOS
            if sleep_time > 0:
                logger.info(f"Sleeping until (AOS - 60s) for {sleep_time} seconds..")
                await wait_until_first_completed(
                    [self.mode_change_event, self.shutdown_event], [asyncio.sleep(sleep_time)]
                )
            if self.current_mode != "survey" or self.shutdown_event.is_set():
                return

            # Dispatch task to the orchestrator
            logger.info("Dispatching task from queue.")
            await self.dispatch_task_to_orchestrator(self.current_task)
            await asyncio.sleep(3)  # buffer for orchestrator to send out status event

    async def run_collect_request(self):
        """Run collect request mode to dispatch tasks based on their AOS times."""
        logger.info("Running collect request mode.")
        while self.current_mode == "collect_request" and not self.shutdown_event.is_set():
            if self.collect_request_queue.empty():
                await wait_until_first_completed([self.new_task_event, self.shutdown_event, self.mode_change_event])
                self.new_task_event.clear()
                if self.shutdown_event.is_set() or self.current_mode != "collect_request":
                    return
                continue

            next_task = self.collect_request_queue._queue[0]  # Peek at the next task
            self.current_task = next_task[1]
            sleep_time = (
                self.current_task["parameters"]["aos"]["time"] - datetime.now(timezone.utc)
            ).total_seconds() - 60

            while sleep_time > 0:
                logger.info(f"Sleeping until (AOS - 60s) for {sleep_time} seconds..")
                await wait_until_first_completed(
                    [self.new_task_event, self.shutdown_event, self.mode_change_event], [asyncio.sleep(sleep_time)]
                )
                if self.shutdown_event.is_set() or self.current_mode != "collect_request":
                    return
                if self.new_task_event.is_set():
                    self.new_task_event.clear()
                    next_task = self.collect_request_queue._queue[0]  # Peek at the next task
                    self.current_task = next_task[1]
                    sleep_time = (
                        self.current_task["parameters"]["aos"]["time"] - datetime.now(timezone.utc)
                    ).total_seconds() - 60
                else:
                    break

            if self.shutdown_event.is_set() or self.current_mode != "collect_request":
                return

            # Now pop the task from the queue and dispatch it
            next_task = await self.collect_request_queue.get()
            self.current_task = next_task[1]
            logger.info("Dispatching task from queue.")
            await self.dispatch_task_to_orchestrator(self.current_task)
            await asyncio.sleep(3)  # buffer for orchestrator to send out status event

    async def run_inactive(self):
        """Deactivate all scheduling."""
        logger.info("Running inactive mode. No tasks will be dispatched.")
        await wait_until_first_completed([self.shutdown_event, self.mode_change_event])

    async def retrieve_tasks_from_astrodynamics(
        self, start_time: datetime = None, end_time: datetime = None
    ) -> list[Task]:
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

    async def set_orchestrator_status_event(self, status: str):
        """Set the orchestrator status event based on the provided status."""
        if status == "idle":
            self.orchestrator_is_ready.set()
            logger.info("Orchestrator ready event set.")
        elif status == "active":
            self.orchestrator_is_ready.clear()
            logger.info("Orchestrator read event cleared.")

    def format_task_details(self, task) -> dict:
        """Format task details for logging and status reporting."""
        task_details = {}
        if task:
            task_details["sat_id"] = task["parameters"]["sat_id"]
            task_details["aos"] = utc_to_local(task["parameters"]["aos"]["time"]).isoformat()
            task_details["los"] = utc_to_local(task["parameters"]["los"]["time"]).isoformat()
        return task_details

    async def clear_queue(self):
        """Clear the task queue."""
        while not self.task_queue.empty():
            await self.task_queue.get()

    async def send_rejected_collect_response(self, task: Task):
        """Send a rejected collect request response"""
        logger.info(f"Sending rejected collect request response: {self.format_task_details(task)}")
        # TODO: add collect response client