import asyncio
import signal
from typing import Optional
from hamilton.base.messages import Message, MessageHandlerType
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler
from hamilton.operators.scheduler.api import Scheduler
from hamilton.operators.scheduler.config import SchedulerControllerConfig


class SchedulerCommandHandler(MessageHandler):
    def __init__(self, scheduler: Scheduler):
        super().__init__(message_type=MessageHandlerType.COMMAND)
        self.scheduler: Scheduler = scheduler
        self.startup_hooks = [self._start_scheduler]
        self.shutdown_hooks = [self._stop_scheduler]
        self.routing_key_base = "observatory.scheduler.telemetry"

    async def _start_scheduler(self):
        await self.scheduler.start()

    async def _stop_scheduler(self):
        await self.scheduler.stop()

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None) -> None:
        response = None
        command = message["payload"]["commandType"]
        parameters = message["payload"]["parameters"]

        if command == "set_mode":
            telemetry_type = None
            mode = parameters.get("mode")
            await self.scheduler.set_mode(mode=mode)

        if command == "stop_scheduling":
            telemetry_type = None
            await self.scheduler.stop_scheduling()

        elif command == "status":
            telemetry_type = "status"
            response = await self.scheduler.status()

        if telemetry_type is not None:
            routing_key = f"{self.routing_key_base}.{telemetry_type}"
            telemetry_msg = self.node_operations.msg_generator.generate_telemetry(telemetry_type, response)
            await self.node_operations.publish_message(routing_key, telemetry_msg, correlation_id)


class OrchestratorStatusEventHandler(MessageHandler):
    def __init__(self, scheduler: Scheduler):
        super().__init__(message_type=MessageHandlerType.TELEMETRY)
        self.scheduler: Scheduler = scheduler

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None) -> None:
        telemetry_type = message["payload"]["telemetryType"]
        parameters = message["payload"]["parameters"]

        if telemetry_type == "status_event":
            status = parameters.get("status")
            await self.scheduler.set_orchestrator_status_event(status=status)


class SchedulerController(AsyncMessageNodeOperator):
    def __init__(self, config: SchedulerControllerConfig = None, shutdown_event: asyncio.Event = None):
        if config is None:
            config = SchedulerControllerConfig()
        self.scheduler = Scheduler()
        handlers = [SchedulerCommandHandler(self.scheduler)]
        super().__init__(config, handlers, shutdown_event)

    async def run(self):
        await self.scheduler.enqueue_tasks()


shutdown_event = asyncio.Event()


def signal_handler():
    shutdown_event.set()


async def main():
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame), signal_handler)

    # Application setup
    controller = SchedulerController(shutdown_event=shutdown_event)

    try:
        await controller.start()
        run_task = asyncio.create_task(controller.run())
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        done, pending = await asyncio.wait([run_task, shutdown_task], return_when=asyncio.FIRST_COMPLETED)

        for task in pending:
            task.cancel()

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
