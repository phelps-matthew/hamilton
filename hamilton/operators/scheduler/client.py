"""
hamilton-scheduler enqueue --sat_id xxx --preempt
"""

import asyncio
import signal
from typing import Optional

from hamilton.base.messages import MessageHandlerType, Message
from hamilton.operators.scheduler.config import SchedulerClientConfig
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler
from hamilton.base.task import Task


class OrchestratorTelemetryHandler(MessageHandler):
    def __init__(self):
        super().__init__(MessageHandlerType.TELEMETRY)

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None):
        return message["payload"]["parameters"]


class SchedulerClient(AsyncMessageNodeOperator):
    def __init__(self, config: SchedulerClientConfig = None, shutdown_event: asyncio.Event = None):
        if config is None:
            config = SchedulerClientConfig()
        handlers = [OrchestratorTelemetryHandler()]
        super().__init__(config, handlers, shutdown_event)
        self.routing_key_base = "observatory.scheduler.command"

    async def _publish_command(self, command: str, parameters: dict, rpc: bool = True) -> dict:
        routing_key = f"{self.routing_key_base}.{command}"
        message = self.msg_generator.generate_command(command, parameters)
        if rpc:
            response = await self.publish_rpc_message(routing_key, message)
        else:
            response = await self.publish_message(routing_key, message)
        return response

    async def add_target(self, sat_id: str):
        command = "add_target"
        parameters = sat_id
        return await self._publish_command(command, parameters, rpc=False)

    async def remove_target(self, sat_id: str):
        command = "remove_target"
        parameters = sat_id
        return await self._publish_command(command, parameters, rpc=False)

    async def force_refresh(self):
        command = "force_refresh"
        parameters = {}
        return await self._publish_command(command, parameters, rpc=False)

    async def stop(self):
        command = "stop"
        parameters = {}
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
    client = SchedulerClient(shutdown_event=shutdown_event)

    try:
        await client.start()

        response = await client.status()
        print(response)

        response = await client.stop()
        print(response)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())


