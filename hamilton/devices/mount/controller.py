import asyncio
import signal

from typing import Any, Optional
from hamilton.base.message_node import AsyncMessageNode, MessageHandler
from hamilton.base.messages import MessageHandlerType, Message
from hamilton.common.utils import CustomJSONDecoder
from hamilton.devices.mount.api import ROT2Prog
from hamilton.devices.mount.config import MountControllerConfig


class MountCommandHandler(MessageHandler):
    def __init__(self, mount_driver: ROT2Prog):
        super().__init__(message_type=MessageHandlerType.COMMAND)
        self.mount: ROT2Prog = mount_driver

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None) -> Any:
        response = None
        print(f"MountCommandHandler: Received message: {message}")
        command = message["payload"]["commandType"]
        parameters = message["payload"]["parameters"]

        if command == "set":
            response = self.mount.set(parameters.get("azimuth"), parameters.get("el"))
        elif command == "status":
            response = self.mount.status()
        elif command == "stop":
            response = self.mount.stop()

        if response:
            az, el = response
            telemetry_msg = self.node_operations.msg_generator.generate_telemetry(
                "azel", {"azimuth": az, "elevation": el}
            )
            await self.node_operations.publish_message(
                "observatory.device.mount.telemetry.azel", telemetry_msg, correlation_id
            )


class MountController:
    def __init__(self, config: MountControllerConfig, handlers: list[MessageHandler]):
        self.node = AsyncMessageNode(config, handlers, verbosity=3)

    async def start(self):
        await self.node.start()

    async def stop(self):
        await self.node.stop()


shutdown_event = asyncio.Event()


def signal_handler():
    shutdown_event.set()


async def main():
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame), signal_handler)

    # Application setup
    config = MountControllerConfig()
    mount_driver = ROT2Prog(config.DEVICE_ADDRESS)
    handlers = [MountCommandHandler(mount_driver)]
    controller = MountController(config, handlers)

    try:
        await controller.start()
        await shutdown_event.wait()  # Wait for the shutdown signal
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
