import asyncio
import signal
from typing import Optional
from hamilton.base.messages import Message, MessageHandlerType
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler
from hamilton.operators.sensor_capsule.api import SensorCapsule
from hamilton.operators.sensor_capsule.config import SensorCapsuleControllerConfig


class SensorCapsuleCommandHandler(MessageHandler):
    def __init__(self, sensor_capsule: SensorCapsule):
        super().__init__(message_type=MessageHandlerType.COMMAND)
        self.sensor_capsule: SensorCapsule = sensor_capsule
        self.startup_hooks = [self._start]
        self.shutdown_hooks = [self._stop]
        self.routing_key_base = "observatory.sensor_capsule.telemetry"

    async def _start(self):
        await self.sensor_capsule.start()

    async def _stop(self):
        await self.sensor_capsule.stop()

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None) -> None:
        response = None
        command = message["payload"]["commandType"]
        parameters = message["payload"]["parameters"]

        if command == "post_collect_response":
            telemetry_type = None
            await self.sensor_capsule.post_spout_collect_response(parameters)

        if command == "status":
            telemetry_type = "status"
            response = await self.sensor_capsule.status()

        if telemetry_type is not None:
            routing_key = f"{self.routing_key_base}.{telemetry_type}"
            telemetry_msg = self.node_operations.msg_generator.generate_telemetry(telemetry_type, response)
            await self.node_operations.publish_message(routing_key, telemetry_msg, correlation_id)


class SensorCapsuleController(AsyncMessageNodeOperator):
    def __init__(self, config: SensorCapsuleControllerConfig = None, shutdown_event: asyncio.Event = None):
        if config is None:
            config = SensorCapsuleControllerConfig()
        self.sensor_capsule = SensorCapsule(config, shutdown_event)
        handlers = [SensorCapsuleCommandHandler(self.sensor_capsule)]
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
    controller = SensorCapsuleController(shutdown_event=shutdown_event)

    try:
        await controller.start()
        await controller.sensor_capsule.poll_bolt_collect_request()
        await shutdown_event.wait()  # Wait for the shutdown signal

    except Exception as e:
        print(f"An unexpected error occurred in the controller: {e}")

    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
