import asyncio
import signal
from typing import Optional

from hamilton.base.messages import Message, MessageHandlerType
from hamilton.operators.signal_processor.api import SignalProcessor
from hamilton.operators.signal_processor.config import SignalProcessorControllerConfig
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler
import logging

logger = logging.getLogger(__name__)


class SignalProcessorCommandHandler(MessageHandler):
    def __init__(self, signal_processor: SignalProcessor):
        super().__init__(message_type=MessageHandlerType.COMMAND)
        self.signal_processor: SignalProcessor = signal_processor
        self.routing_key_base = "observatory.signal_processor.telemetry"

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None) -> None:
        response = None
        command = message["payload"]["commandType"]
        parameters = message["payload"]["parameters"]

        if command == "generate_psds":
            telemetry_type = "status"
            await self.signal_processor.plot_psds(**parameters)
            response = {"psd_status": "complete"}

        elif command == "generate_spectrograms":
            telemetry_type = "status"
            await self.signal_processor.plot_spectrograms(*parameters)
            response = {"spectrogram_status": "complete"}

        elif command == "generate_panels":
            telemetry_type = "status"
            await self.signal_processor.plot_panels(*parameters)
            response = {"panel_status": "complete"}

        if telemetry_type is not None:
            routing_key = f"{self.routing_key_base}.{telemetry_type}"
            telemetry_msg = self.node_operations.msg_generator.generate_telemetry(telemetry_type, response)
            await self.node_operations.publish_message(routing_key, telemetry_msg, correlation_id)


class SignalProcessorController(AsyncMessageNodeOperator):
    def __init__(self, config: SignalProcessorControllerConfig = None, shutdown_event: asyncio.Event = None):
        if config is None:
            config = SignalProcessorControllerConfig()
        signal_processor = SignalProcessor(config)
        handlers = [SignalProcessorCommandHandler(signal_processor)]
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
    controller = SignalProcessorController(shutdown_event=shutdown_event)

    try:
        await controller.start()
        await shutdown_event.wait()  # Wait for the shutdown signal

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
