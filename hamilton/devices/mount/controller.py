import asyncio
import signal
from typing import Optional

from hamilton.base.messages import Message, MessageHandlerType
from hamilton.devices.mount.api import ROT2Prog
from hamilton.devices.mount.config import MountControllerConfig
from hamilton.message_node.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.message_node.interfaces import MessageHandler

class MountCommandHandler(MessageHandler):
    def __init__(self, mount_driver: ROT2Prog):
        super().__init__(message_type=MessageHandlerType.COMMAND)
        self.mount: ROT2Prog = mount_driver

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None) -> None:
        response = None
        command = message["payload"]["commandType"]
        parameters = message["payload"]["parameters"]

        if command == "set":
            response = self.mount.set(parameters.get("azimuth"), parameters.get("elevation"))
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


class MountController(AsyncMessageNodeOperator):
    def __init__(self, config: MountControllerConfig = None, verbosity: int = 1):
        if config is None:
            config = MountControllerConfig()
        mount_driver = ROT2Prog(config.DEVICE_ADDRESS)
        handlers = [MountCommandHandler(mount_driver)]
        super().__init__(config, handlers, verbosity)


shutdown_event = asyncio.Event()


def signal_handler():
    shutdown_event.set()


async def main():
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame), signal_handler)

    # Application setup
    controller = MountController(verbosity=2)

    try:
        await controller.start()
        await shutdown_event.wait()  # Wait for the shutdown signal

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
