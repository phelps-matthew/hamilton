import asyncio
import signal
from typing import Optional

from hamilton.base.messages import MessageHandlerType, Message
from hamilton.database.config import DBClientConfig
from hamilton.message_node.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.message_node.interfaces import MessageHandler


class DBTelemetryHandler(MessageHandler):
    def __init__(self):
        super().__init__(MessageHandlerType.TELEMETRY)

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None):
        return message["payload"]["parameters"]


class DBClient(AsyncMessageNodeOperator):
    def __init__(self, config=None):
        if config is None:
            config = DBClientConfig()
        handlers = [DBTelemetryHandler()]
        super().__init__(config, handlers)
        self.routing_key_base = "observatory.database.command"

    async def _publish_command(self, command: str, parameters: dict) -> dict:
        routing_key = f"{self.routing_key_base}.{command}"
        message = self.msg_generator.generate_command(command, parameters)
        response = await self.publish_rpc_message(routing_key, message)
        return response

    async def query_record(self, sat_id: str) -> dict:
        command = "query_record"
        parameters = {"sat_id": sat_id}
        return await self._publish_command(command, parameters)

    async def get_satellite_ids(self) -> list:
        command = "get_satellite_ids"
        parameters = {}
        return await self._publish_command(command, parameters)

    async def get_active_downlink_satellite_ids(self) -> list:
        command = "get_active_downlink_satellite_ids"
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
    client = DBClient()

    try:
        await client.start()

        response = await client.query_record(sat_id="33499")
        print(f"Response: {response}")

        response = await client.get_satellite_ids()
        print(f"Response: {response}")

        response = await client.get_active_downlink_satellite_ids()
        print(f"Response: {response}")
        print(f"Response Items: {len(response)}")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
