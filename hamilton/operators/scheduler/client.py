"""
hamilton-scheduler enqueue --sat_id xxx --preempt
"""

import asyncio
import signal
from typing import Optional
import json

from hamilton.base.messages import MessageHandlerType, Message
from hamilton.operators.scheduler.config import SchedulerClientConfig
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler
from hamilton.base.task import Task
from hamilton.common.utils import CustomJSONEncoder


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

    async def stop_scheduling(self):
        command = "stop_scheduling"
        parameters = {}
        return await self._publish_command(command, parameters, rpc=False)

    async def set_mode(self, mode: str):
        """
        Args: mode: [survey, standby, inactive, collect_request]
        """
        command = "set_mode"
        parameters = {"mode": mode}
        return await self._publish_command(command, parameters, rpc=False)

    async def status(self):
        command = "status"
        parameters = {}
        return await self._publish_command(command, parameters, rpc=True)

    async def enqueue_collect_request(self, task: Task):
        """Enqueue a collect request to the scheduler."""
        command = "enqueue_collect_request"
        parameters = {"task": task}
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
    client = SchedulerClient(shutdown_event=shutdown_event)

    try:
        await client.start()

        response = await client.status()
        json.dumps(response, indent=4, cls=CustomJSONEncoder)

        response = await client.set_mode("inactive")
        print(response)

        response = await client.set_mode("standby")
        print(response)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())


