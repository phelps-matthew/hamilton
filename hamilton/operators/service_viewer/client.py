import asyncio
import signal
from typing import Optional

from hamilton.base.messages import MessageHandlerType, Message
from hamilton.operators.service_viewer.config import ServiceViewerClientConfig
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler


class ServiceViewerTelemetryHandler(MessageHandler):
    def __init__(self):
        super().__init__(MessageHandlerType.TELEMETRY)

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None):
        return message["payload"]["parameters"]


class ServiceViewerClient(AsyncMessageNodeOperator):
    def __init__(self, config: ServiceViewerClientConfig = None):
        if config is None:
            config = ServiceViewerClientConfig()
        handlers = [ServiceViewerTelemetryHandler()]
        super().__init__(config, handlers)
        self.routing_key_base = "observatory.service_viewer.command"

    async def _publish_command(self, command: str, parameters: dict, rpc: bool = True) -> dict:
        routing_key = f"{self.routing_key_base}.{command}"
        message = self.msg_generator.generate_command(command, parameters)
        if rpc:
            response = await self.publish_rpc_message(routing_key, message)
        else:
            response = await self.publish_message(routing_key, message)
        return response

    async def status(self, service: str = None):
        command = "status"
        parameters = {"service": service}
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
    client = ServiceViewerClient()

    try:
        await client.start()

        response = await client.status()
        print(response)

        response = await client.status("hamilton-mount-controller")
        print(response)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())

