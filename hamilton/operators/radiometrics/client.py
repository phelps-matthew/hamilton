import asyncio
import json
import signal
from typing import Any, Optional

from hamilton.base.messages import Message, MessageHandlerType
from hamilton.common.utils import CustomJSONEncoder
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler
from hamilton.operators.radiometrics.config import RadiometricsClientConfig


class RadiometricsTelemetryHandler(MessageHandler):
    def __init__(self):
        super().__init__(MessageHandlerType.TELEMETRY)

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None):
        return message["payload"]["parameters"]


class RadiometricsClient(AsyncMessageNodeOperator):
    def __init__(
        self,
        config: RadiometricsClientConfig = None,
    ):
        if config is None:
            config = RadiometricsClientConfig()
        handlers = [RadiometricsTelemetryHandler()]
        super().__init__(config, handlers)
        self.routing_key_base = "observatory.radiometrics.command"

    async def _publish_command(self, command: str, parameters: dict, rpc: bool = True) -> dict:
        routing_key = f"{self.routing_key_base}.{command}"
        message = self.msg_generator.generate_command(command, parameters)
        print(routing_key, message)
        if rpc:
            response = await self.publish_rpc_message(routing_key, message)
        else:
            response = await self.publish_message(routing_key, message)
        return response

    async def get_tx_profile(self, sat_id: str) -> dict[str, Any]:
        command = "get_tx_profile"
        parameters = {"sat_id": sat_id}
        return await self._publish_command(command, parameters)

    async def get_downlink_freqs(self, sat_id: str) -> dict[str, Any]:
        command = "get_downlink_freqs"
        parameters = {"sat_id": sat_id}
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
    client = RadiometricsClient()

    try:
        await client.start()

        # Sample ids with 2x freqs, 1x freqs, 0x freqs
        sat_ids = ["25397", "39433", "57186"]

        for sat_id in sat_ids:
            response = await client.get_tx_profile(sat_id)
            print(json.dumps(response, indent=4, cls=CustomJSONEncoder))

        for sat_id in sat_ids:
            response = await client.get_downlink_freqs(sat_id)
            print(json.dumps(response, indent=4, cls=CustomJSONEncoder))

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
