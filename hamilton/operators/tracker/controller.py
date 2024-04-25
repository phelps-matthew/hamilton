import asyncio
import signal
from typing import Optional

from hamilton.base.messages import Message, MessageHandlerType
from hamilton.operators.tracker.api import Tracker
from hamilton.operators.tracker.config import TrackerControllerConfig
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler
import logging

logger = logging.getLogger(__name__)


class TrackerCommandHandler(MessageHandler):
    def __init__(self, tracker: Tracker):
        super().__init__(message_type=MessageHandlerType.COMMAND)
        self.tracker: Tracker = tracker
        self.startup_hooks = [self._start_tracker]
        self.shutdown_hooks = [self._stop_tracker]
        self.routing_key_base = "observatory.tracker.telemetry"

    async def _start_tracker(self):
        await self.tracker.start()

    async def _stop_tracker(self):
        await self.tracker.stop()

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None) -> None:
        response = None
        command = message["payload"]["commandType"]
        parameters = message["payload"]["parameters"]

        if command == "start_tracking":
            telemetry_type = None
            await self.tracker.setup_task(parameters)
            await self.tracker.track()

        elif command == "slew_to_home":
            telemetry_type = "status"
            await self.tracker.slew_to_home()
            response = {}

        elif command == "slew_to_aos":
            telemetry_type = "status"
            await self.tracker.setup_task(parameters)
            await self.tracker.slew_to_aos()
            response = {}

        elif command == "stop_tracking":
            telemetry_type = "status"
            await self.tracker.stop_tracking()
            response = {}

        elif command == "status":
            telemetry_type = "status"
            response = await self.tracker.status()

        if telemetry_type is not None:
            routing_key = f"{self.routing_key_base}.{telemetry_type}"
            telemetry_msg = self.node_operations.msg_generator.generate_telemetry(telemetry_type, response)
            await self.node_operations.publish_message(routing_key, telemetry_msg, correlation_id)


class TrackerController(AsyncMessageNodeOperator):
    def __init__(self, config: TrackerControllerConfig = None, shutdown_event: asyncio.Event = None):
        if config is None:
            config = TrackerControllerConfig()
        tracker = Tracker(config)
        handlers = [TrackerCommandHandler(tracker)]
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
    controller = TrackerController(shutdown_event=shutdown_event)

    try:
        await controller.start()
        await shutdown_event.wait()  # Wait for the shutdown signal

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
