import asyncio
import json
import signal
from typing import Optional

from hamilton.base.messages import MessageHandlerType, Message
from hamilton.base.task import TaskGenerator
from hamilton.operators.orchestrator.config import OrchestratorClientConfig
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler
from hamilton.base.task import Task
from hamilton.common.utils import CustomJSONEncoder


class OrchestratorTelemetryHandler(MessageHandler):
    def __init__(self):
        super().__init__(MessageHandlerType.TELEMETRY)

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None):
        return message["payload"]["parameters"]


class OrchestratorClient(AsyncMessageNodeOperator):
    def __init__(self, config: OrchestratorClientConfig = None, shutdown_event: asyncio.Event = None):
        if config is None:
            config = OrchestratorClientConfig()
        handlers = [OrchestratorTelemetryHandler()]
        super().__init__(config, handlers, shutdown_event)
        self.routing_key_base = "observatory.orchestrator.command"

    async def _publish_command(self, command: str, parameters: dict, rpc: bool = True) -> dict:
        routing_key = f"{self.routing_key_base}.{command}"
        message = self.msg_generator.generate_command(command, parameters)
        if rpc:
            response = await self.publish_rpc_message(routing_key, message)
        else:
            response = await self.publish_message(routing_key, message)
        return response

    async def orchestrate(self, task: Task):
        command = "orchestrate"
        parameters = task
        return await self._publish_command(command, parameters, rpc=False)

    async def stop_orchestrating(self):
        command = "stop_orchestrating"
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
    client = OrchestratorClient(shutdown_event=shutdown_event)
    task_generator = TaskGenerator()

    try:
        await client.start()
        await task_generator.start()

        sat_id = "25397"
        task = await task_generator.generate_task(sat_id)
        print(json.dumps(task, cls=CustomJSONEncoder, indent=4))

        response = await client.status()
        print(response)

        if task is not None:
            response = await client.orchestrate(task)
            print(f"Orchestrate response: {response}")

            if input("Stop orchestrating? y/n:") == "y":
                await client.stop_orchestrating()
            else:
                await asyncio.sleep(120)
        else:
            print("Task is None")

        response = await client.stop_orchestrating()
        print(response)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
