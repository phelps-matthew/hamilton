"""
1) Astrodynamics: Precompute orbit (for computing mount path?)
2) Radiometrics: Get downlink tx frequency
3) Precompute mount path direction. 
4) Position mount to ready position. (Preposition)
5) When elevation limits aren't violated, start tracking until end of pass. Signal tracking. Start recording.
6) Stop recording. Position mount to home. (Post position) Signal non-active.
"""

import asyncio
from hamilton.operators.orchestrator.operator import Operator


class Orchestrator:
    def __init__(self, operator: Operator):
        self.operator: Operator = operator
        self.task_queue = asyncio.Queue()
        self.shutdown_event = asyncio.Event()
        self.current_task = None
        self.processed_tasks_count = 0

    async def start(self):
        """Start the orchestrator."""
        self.shutdown_event.clear()
        asyncio.create_task(self._run())

    async def _run(self):
        """Main loop to process tasks."""
        while not self.shutdown_event.is_set():
            try:
                task_parameters = await self.task_queue.get()
                self.current_task = asyncio.create_task(self.process_task(task_parameters))
                await self.current_task
            except asyncio.CancelledError:
                # Handle task cancellation gracefully
                pass
            finally:
                self.task_queue.task_done()
                self.current_task = None
                self.processed_tasks_count += 1

    async def process_task(self, parameters: dict):
        """Process a single task."""
        print(f"Processing task with parameters: {parameters}")
        await asyncio.sleep(1)  # Simulate task processing

    async def enqueue_task(self, parameters):
        """Add tasks to the queue."""
        await self.task_queue.put(parameters)

    async def stop(self):
        """Immediately stop the orchestrator, cancelling any ongoing task."""
        self.shutdown_event.set()
        if self.current_task:
            self.current_task.cancel()
            await self.current_task

    async def soft_stop(self):
        """Allow the current task to finish before stopping."""
        self.shutdown_event.set()

    def status(self):
        """Return the current status of the Orchestrator."""
        if self.shutdown_event.is_set():
            status = "stopped"
        elif self.current_task and not self.current_task.done():
            status = "running"
        else:
            status = "idle"
        return {
            "status": status,
            "tasks_in_queue": self.task_queue.qsize(),
            "tasks_processed": self.processed_tasks_count,
        }
