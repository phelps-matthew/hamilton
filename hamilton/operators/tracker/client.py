import asyncio
import signal
from typing import Optional

from hamilton.base.messages import MessageHandlerType, Message
from hamilton.operators.tracker.config import TrackerClientConfig
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler
from hamilton.base.task import Task, TaskGenerator


class TrackerTelemetryHandler(MessageHandler):
    def __init__(self):
        super().__init__(MessageHandlerType.TELEMETRY)

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None):
        return message["payload"]["parameters"]


class TrackerClient(AsyncMessageNodeOperator):
    def __init__(self, config: TrackerClientConfig = None, shutdown_event: asyncio.Event = None):
        if config is None:
            config = TrackerClientConfig()
        handlers = [TrackerTelemetryHandler()]
        super().__init__(config, handlers, shutdown_event)
        self.routing_key_base = "observatory.tracker.command"

    async def _publish_command(self, command: str, parameters: dict, rpc: bool = True, timeout: int = 10) -> dict:
        routing_key = f"{self.routing_key_base}.{command}"
        message = self.msg_generator.generate_command(command, parameters)
        if rpc:
            response = await self.publish_rpc_message(routing_key, message, timeout=timeout)
        else:
            response = await self.publish_message(routing_key, message)
        return response

    async def start_tracking(self, task: Task):
        command = "start_tracking"
        parameters = task
        return await self._publish_command(command, parameters, rpc=False)

    async def slew_to_aos(self, task: Task):
        command = "slew_to_aos"
        parameters = task
        return await self._publish_command(command, parameters, rpc=True, timeout=120)

    async def slew_to_home(self):
        command = "slew_to_home"
        parameters = {}
        return await self._publish_command(command, parameters, rpc=True, timeout=120)

    async def stop_tracking(self):
        command = "stop_tracking"
        parameters = {}
        return await self._publish_command(command, parameters, rpc=True)

    async def status(self):
        command = "status"
        parameters = {}
        return await self._publish_command(command, parameters, rpc=True)


shutdown_event = asyncio.Event()


def signal_handler():
    shutdown_event.set()


async def main():
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame), signal_handler)

    # Application setup
    client = TrackerClient(shutdown_event=shutdown_event)
    task_generator = TaskGenerator()

    try:
        await client.start()
        await task_generator.start()

        sat_id = "98932"
        task = await task_generator.generate_task(sat_id)

        response = await client.status()
        print(f"Status response: {response}")

        response = await client.slew_to_home()
        print(f"Slew to home response: {response}")

        if task is not None:
            response = await client.slew_to_aos(task)
            print(f"Slew to AOS response: {response}")

            print("starting tracking")
            await client.start_tracking(task)
            response = await client.status()
            print(f"Status while tracking response: {response}")

            await asyncio.sleep(5)
            await client.stop_tracking()
            response = await client.status()
            print(f"After stop tracking response: {response}")
            await asyncio.sleep(1)
            response = await client.status()
            print(f"After stop tracking response 2: {response}")

            response = await client.slew_to_home()
            print(f"Slew to home response: {response}")

            #if input("Stop tracking? y/n:") == "y":
            #    await client.stop_tracking()
            #else:
            #    await asyncio.sleep(60)
        else:
            print("Task is None")

        response = await client.status()
        print(f"Status response: {response}")

        response = await client.stop_tracking()
        print(f"Stop response: {response}")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
