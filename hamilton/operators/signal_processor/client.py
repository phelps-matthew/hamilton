import asyncio
import signal
from typing import Optional

from hamilton.base.messages import MessageHandlerType, Message
from hamilton.operators.signal_processor.config import SignalProcessorClientConfig
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler


class SignalProcessorTelemetryHandler(MessageHandler):
    def __init__(self):
        super().__init__(MessageHandlerType.TELEMETRY)

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None):
        return message["payload"]["parameters"]


class SignalProcessorClient(AsyncMessageNodeOperator):
    def __init__(self, config: SignalProcessorClientConfig = None, shutdown_event: asyncio.Event = None):
        if config is None:
            config = SignalProcessorClientConfig()
        handlers = [SignalProcessorTelemetryHandler()]
        super().__init__(config, handlers, shutdown_event)
        self.routing_key_base = "observatory.signal_processor.command"

    async def _publish_command(self, command: str, parameters: dict, rpc: bool = True, timeout: int = 10) -> dict:
        routing_key = f"{self.routing_key_base}.{command}"
        message = self.msg_generator.generate_command(command, parameters)
        if rpc:
            response = await self.publish_rpc_message(routing_key, message, timeout=timeout)
        else:
            response = await self.publish_message(routing_key, message)
        return response

    async def generate_psds(self, parameters: dict = {}):
        command = "generate_psds"
        return await self._publish_command(command, parameters, rpc=False)

    async def generate_spectrograms(self, parameters: dict = {}):
        command = "generate_spectrograms"
        return await self._publish_command(command, parameters, rpc=False)

shutdown_event = asyncio.Event()


def signal_handler():
    shutdown_event.set()


async def main():
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame), signal_handler)

    # Application setup
    client = SignalProcessorClient(shutdown_event=shutdown_event)

    try:
        await client.start()
        print("Generating PSDS")
        await client.generate_psds()
        print("Generating Spectrograms")
        await client.generate_spectrograms()

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
