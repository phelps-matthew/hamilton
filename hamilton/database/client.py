import asyncio
import signal
from typing import Optional

from hamilton.base.messages import MessageHandlerType, Message
from hamilton.database.config import DBClientConfig
from hamilton.message_node.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.message_node.interfaces import MessageHandler


class DBQueryTelemetryHandler(MessageHandler):
    def __init__(self):
        super().__init__(MessageHandlerType.TELEMETRY)

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None):
        return message["payload"]["parameters"]


class DBQueryClient(AsyncMessageNodeOperator):
    def __init__(self, config=None, verbosity=0):
        if config is None:
            config = DBClientConfig()
        handlers = [DBQueryTelemetryHandler()]
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
    client = DBQueryClient(verbosity=1)

    try:
        await client.start()

        command = "query"
        parameters = {"sat_id": "33499"}
        message = client.msg_generator.generate_command(command, parameters)
        response = await client.publish_rpc_message("observatory.database.command.query_record", message)
        print(f"Response: {response}")

        command = "get_satellite_ids"
        parameters = {}
        message = client.msg_generator.generate_command(command, parameters)
        response = await client.publish_rpc_message("observatory.database.command.get_satellite_ids", message)
        print(f"Response: {response}")

        command = "get_active_downlink_satellite_ids"
        parameters = {}
        message = client.msg_generator.generate_command(command, parameters)
        response = await client.publish_rpc_message(
            "observatory.database.command.get_active_downlink_satellite_ids", message
        )
        print(f"Response: {response}")
        print(f"Response Items: {len(response)}")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
