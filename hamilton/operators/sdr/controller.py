import asyncio
import signal
from typing import Optional

from hamilton.base.messages import Message, MessageHandlerType
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler
from hamilton.operators.relay.client import RelayClient
from hamilton.operators.sdr.api import SDRSigMFRecord
from hamilton.operators.sdr.config import SDRControllerConfig


class SDRCommandHandler(MessageHandler):
    def __init__(self, recorder: SDRSigMFRecord, relay: RelayClient):
        super().__init__(message_type=MessageHandlerType.COMMAND)
        self.recorder: SDRSigMFRecord = recorder
        self.relay: RelayClient = relay
        self.startup_hooks = [self._start_relay]
        self.shutdown_hooks = [self._stop_devices]
        self.routing_key_base = "observatory.sdr.telemetry"

    async def _start_relay(self):
        await self.relay.start()

    async def _stop_devices(self):
        await self.recorder.stop_record()
        await self.relay.stop()

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None) -> None:
        response = None
        command = message["payload"]["commandType"]
        parameters = message["payload"]["parameters"]

        if command == "status":
            telemetry_type = "status"

        elif command == "start_record":
            telemetry_type = "status"
            self.recorder.update_parameters(parameters)
            await self.recorder.start_record()

        elif command == "stop_record":
            telemetry_type = "status"
            await self.recorder.stop_record()

        if telemetry_type is not None:
            response = self.recorder.get_status()
            routing_key = f"{self.routing_key_base}.{telemetry_type}"
            telemetry_msg = self.node_operations.msg_generator.generate_telemetry(telemetry_type, response)
            await self.node_operations.publish_message(routing_key, telemetry_msg, correlation_id)


class SDRController(AsyncMessageNodeOperator):
    def __init__(self, config: SDRControllerConfig = None):
        if config is None:
            config = SDRControllerConfig()
        relay = RelayClient()
        recorder = SDRSigMFRecord(config=config, relay_client=relay)
        handlers = [SDRCommandHandler(recorder, relay)]
        super().__init__(config, handlers)


shutdown_event = asyncio.Event()


def signal_handler():
    shutdown_event.set()


async def main():
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame), signal_handler)

    # Application setup
    controller = SDRController()

    try:
        await controller.start()
        await shutdown_event.wait()  # Wait for the shutdown signal

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
