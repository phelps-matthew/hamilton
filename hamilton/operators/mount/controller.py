import asyncio
import signal
from typing import Optional

from hamilton.base.messages import Message, MessageHandlerType
from hamilton.operators.mount.api import ROT2Prog
from hamilton.operators.mount.config import MountControllerConfig
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler


class MountCommandHandler(MessageHandler):
    def __init__(self, mount_driver: ROT2Prog):
        super().__init__(message_type=MessageHandlerType.COMMAND)
        self.mount: ROT2Prog = mount_driver
        self.shutdown_hooks = [self.stop_rotor]
        self.routing_key_base = "observatory.mount.telemetry"

    async def stop_rotor(self):
        self.mount.stop()

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None) -> None:
        response = None
        command = message["payload"]["commandType"]
        parameters = message["payload"]["parameters"]

        if command == "set":
            telemetry_type = "azel"
            response = self.mount.set(parameters.get("azimuth"), parameters.get("elevation"))

        elif command == "status":
            telemetry_type = "azel"
            response = self.mount.status()

        elif command == "stop":
            telemetry_type = None
            response = self.mount.stop()

        if telemetry_type is not None:
            routing_key = f"{self.routing_key_base}.{telemetry_type}"
            az, el = response
            telemetry_msg = self.node_operations.msg_generator.generate_telemetry(
                "azel", {"azimuth": az, "elevation": el}
            )
            await self.node_operations.publish_message(routing_key, telemetry_msg, correlation_id)


class MountController(AsyncMessageNodeOperator):
    def __init__(self, config: MountControllerConfig = None, shutdown_event: asyncio.Event = None):
        if config is None:
            config = MountControllerConfig()
        mount_driver = ROT2Prog(config.DEVICE_ADDRESS)
        handlers = [MountCommandHandler(mount_driver)]
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
    controller = MountController(shutdown_event=shutdown_event)

    try:
        await controller.start()
        await shutdown_event.wait()  # Wait for the shutdown signal

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
