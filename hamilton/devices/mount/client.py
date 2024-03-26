import signal
import asyncio
from typing import Optional

from hamilton.base.message_node import AsyncMessageNode, MessageHandler
from hamilton.base.messages import MessageHandlerType, Message
from hamilton.common.utils import CustomJSONDecoder
from hamilton.devices.mount.config import MountClientConfig


class MountTelemetryHandler(MessageHandler):
    def __init__(self):
        super().__init__(MessageHandlerType.TELEMETRY)

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None):
        return message["payload"]["parameters"]


class MountClient:
    def __init__(
        self,
        config: MountClientConfig = MountClientConfig(),
        handlers: list[MessageHandler] = [MountTelemetryHandler()],
    ):
        self.node = AsyncMessageNode(config, handlers, verbosity=3)

    async def start(self):
        await self.node.start()

    async def stop(self):
        await self.node.stop()

    async def publish_message(self, routing_key: str, message: dict, corr_id: Optional[str] = None):
        return await self.node.publish_message(routing_key, message, corr_id)

    async def publish_rpc_message(self, routing_key: str, message: dict, timeout: int = 10):
        return await self.node.publish_rpc_message(routing_key, message, timeout)


shutdown_event = asyncio.Event()


def signal_handler():
    shutdown_event.set()


async def main():
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame), signal_handler)

    # Application setup
    config = MountClientConfig()
    handlers = [MountTelemetryHandler()]
    client = MountClient(config, handlers)

    try:
        await client.start()
        command = "status"
        parameters = {}
        message = client.node.msg_generator.generate_command(command, parameters)

        # Publish message
        await client.publish_message("observatory.device.mount.command.status", message)
        # Publish RPC message and await response
        response = await client.publish_rpc_message("observatory.device.mount.command.status", message)
        print(response)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
