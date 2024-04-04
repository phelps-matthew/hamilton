import asyncio
import signal
from typing import Optional

from hamilton.base.messages import MessageHandlerType, Message
from hamilton.operators.mount.config import MountClientConfig
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler


class MountTelemetryHandler(MessageHandler):
    def __init__(self):
        super().__init__(MessageHandlerType.TELEMETRY)

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None):
        return message["payload"]["parameters"]


class MountClient(AsyncMessageNodeOperator):
    def __init__(self, config: MountClientConfig = None):
        if config is None:
            config = MountClientConfig()
        handlers = [MountTelemetryHandler()]
        super().__init__(config, handlers)
        self.routing_key_base = "observatory.mount.command"

    async def _publish_command(self, command: str, parameters: dict, rpc: bool = True) -> dict:
        routing_key = f"{self.routing_key_base}.{command}"
        message = self.msg_generator.generate_command(command, parameters)
        if rpc:
            response = await self.publish_rpc_message(routing_key, message)
        else:
            response = await self.publish_message(routing_key, message)
        return response

    async def status(self):
        command = "status"
        parameters = {}
        return await self._publish_command(command, parameters)

    async def set(self, az, el, rpc=True):
        command = "set"
        parameters = {"azimuth": az, "elevation": el}
        return await self._publish_command(command, parameters, rpc)

    async def stop_rotor(self, rpc=True):
        command = "stop"
        parameters = {}
        return await self._publish_command(command, parameters, rpc)


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

        response = await client.status()
        print(response)

        response = await client.stop_rotor()
        print(response)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
