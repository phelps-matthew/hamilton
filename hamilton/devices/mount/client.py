import asyncio
import signal
from typing import Optional

from hamilton.base.messages import MessageHandlerType, Message
from hamilton.devices.mount.config import MountClientConfig
from hamilton.message_node.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.message_node.interfaces import MessageHandler


class MountTelemetryHandler(MessageHandler):
    def __init__(self):
        super().__init__(MessageHandlerType.TELEMETRY)

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None):
        return message["payload"]["parameters"]


class MountClient(AsyncMessageNodeOperator):
    def __init__(self, config=None):
        if config is None:
            config = MountClientConfig()
        handlers = [MountTelemetryHandler()]
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
    client = MountClient()

    try:
        await client.start()
        command = "status"
        parameters = {}
        message = client.msg_generator.generate_command(command, parameters)

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
