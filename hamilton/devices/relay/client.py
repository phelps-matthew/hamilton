import signal
import asyncio
from typing import Optional

from hamilton.message_node.interfaces import MessageHandler
from hamilton.message_node.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.base.messages import MessageHandlerType, Message
from hamilton.devices.relay.config import RelayClientConfig


class RelayTelemetryHandler(MessageHandler):
    def __init__(self):
        super().__init__(MessageHandlerType.TELEMETRY)

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None):
        return message["payload"]["parameters"]


class RelayClient(AsyncMessageNodeOperator):
    def __init__(self, config: RelayClientConfig = None):
        if config is None:
            config = RelayClientConfig()
        handlers = [RelayTelemetryHandler()]
        super().__init__(config, handlers)
        self.routing_key_base = "observatory.device.relay.command"

    async def _publish_command(self, command: str, parameters: dict, rpc: bool = True) -> dict:
        routing_key = f"{self.routing_key_base}.{command}"
        message = self.msg_generator.generate_command(command, parameters)
        if rpc:
            response = await self.publish_rpc_message(routing_key, message)
        else:
            response = await self.publish_message(routing_key, message)
        return response

    async def set(self, id: str, state: str) -> dict:
        """
        Set relay state.

        Args:
        - id (str): The relay ID. Possible values are "uhf_bias", "vhf_bias", "vhf_pol", "uhf_pol".
        - state (str): The desired state of the relay. Possible values are "on", "off".
        """
        command = "set"
        parameters = {"id": id, "state": state}
        return await self._publish_command(command, parameters, rpc=False)

    async def status(self) -> dict:
        """Query relay status"""
        command = "status"
        parameters = {}
        return await self._publish_command(command, parameters)


shutdown_event = asyncio.Event()


def signal_handler():
    shutdown_event.set()


async def main():
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame), signal_handler)

    # Application setup
    client = RelayClient()

    try:
        await client.start()

        response = await client.status()
        print(response)

        parameters = {"id": "uhf_bias", "state": "on"}
        response = await client.set(**parameters)
        print(response)

        response = await client.status()
        print(response)

        parameters = {"id": "uhf_bias", "state": "off"}
        response = await client.set(**parameters)
        print(response)

        response = await client.status()
        print(response)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
