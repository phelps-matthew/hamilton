import asyncio
import signal
from typing import Optional

from hamilton.base.messages import MessageHandlerType, Message
from hamilton.operators.sensor_capsule.config import SensorCapsuleClientConfig
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler
from hamilton.base.task import Task


class SensorCapsuleTelemetryHandler(MessageHandler):
    def __init__(self):
        super().__init__(MessageHandlerType.TELEMETRY)

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None):
        return message["payload"]["parameters"]


class SensorCapsuleClient(AsyncMessageNodeOperator):
    def __init__(self, config: SensorCapsuleClientConfig = None, shutdown_event: asyncio.Event = None):
        if config is None:
            config = SensorCapsuleClientConfig()
        handlers = [SensorCapsuleTelemetryHandler()]
        super().__init__(config, handlers, shutdown_event)
        self.routing_key_base = "observatory.sensor_capsule.command"

    async def _publish_command(self, command: str, parameters: dict, rpc: bool = True) -> dict:
        routing_key = f"{self.routing_key_base}.{command}"
        message = self.msg_generator.generate_command(command, parameters)
        if rpc:
            response = await self.publish_rpc_message(routing_key, message)
        else:
            response = await self.publish_message(routing_key, message)
        return response

    async def post_collect_response(self, task: Task):
        command = "post_collect_response"
        parameters = task
        return await self._publish_command(command, parameters, rpc=False)

    async def status(self):
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
    client = SensorCapsuleClient(shutdown_event=shutdown_event)

    try:
        await client.start()

        response = await client.status()
        print(response)

        response = await client.post_collect_response({"sat_id": "25397"})
        print(response)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())