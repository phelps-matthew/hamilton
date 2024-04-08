
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
        self.config = self.node_operations.config
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

        if command == "add_target":
            telemetry_type = None
            if not self.scheduler.is_running:
                await self.scheduler.add_target(parameters)

        elif command == "remove_target":
            telemetry_type = None
            if not self.scheduler.is_running:
                await self.scheduler.remove_target(parameters)

        elif command == "force_refresh":
            telemetry_type = None
            if not self.scheduler.is_running:
                await self.scheduler.force_refresh()

        elif command == "stop":
            telemetry_type = None
            await self.scheduler.stop_scheduling()

        elif command == "status":
            telemetry_type = "status"
            response = await self.scheduler.status()

        if telemetry_type is not None:
            routing_key = f"{self.routing_key_base}.{telemetry_type}"
            telemetry_msg = self.node_operations.msg_generator.generate_telemetry(telemetry_type, response)
            await self.node_operations.publish_message(routing_key, telemetry_msg, correlation_id)


class SchedulerController(AsyncMessageNodeOperator):
    def __init__(self, config: SchedulerControllerConfig = None, shutdown_event: asyncio.Event = None):
        if config is None:
            config = SchedulerControllerConfig()
        scheduler = Scheduler()
        handlers = [SchedulerCommandHandler(scheduler)]
        super().__init__(config, handlers, shutdown_event)


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
        await shutdown_event.wait()  # Wait for the shutdown signal

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())

