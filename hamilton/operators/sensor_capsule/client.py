import asyncio
import signal
from typing import Optional
from datetime import datetime
from pathlib import Path
import json

from hamilton.base.messages import MessageHandlerType, Message
from hamilton.operators.sensor_capsule.config import SensorCapsuleClientConfig
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler
from hamilton.base.task import Task
from hamilton.common.utils import CustomJSONEncoder


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

    async def _publish_command(self, command: str, parameters: dict, rpc: bool = True, timeout: int = 10) -> dict:
        routing_key = f"{self.routing_key_base}.{command}"
        message = self.msg_generator.generate_command(command, parameters)
        if rpc:
            response = await self.publish_rpc_message(routing_key, message, timeout=timeout)
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
        return await self._publish_command(command, parameters, rpc=True)

    async def generate_collect_requests(
        self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ):
        command = "generate_collect_requests"
        parameters = {
            "start_time": start_time.isoformat() if start_time else None,
            "end_time": end_time.isoformat() if end_time else None,
        }
        return await self._publish_command(command, parameters, rpc=True, timeout=30)


def write_collect_requests(collect_request_list: list):
    collect_request_dir = Path(f"~/hamilton/sensor-capsule/collect_request_batch").expanduser()
    if collect_request_dir.exists() and collect_request_dir.is_dir():
        for file in collect_request_dir.iterdir():
            if file.is_file():
                file.unlink()
    collect_request_dir.mkdir(parents=True, exist_ok=True)

    for collect_request in collect_request_list:
        collect_request["createdAt"] = collect_request["createdAt"].strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        collect_request["startTime"] = collect_request["startTime"].strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        collect_request["endTime"] = collect_request["endTime"].strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        with open(collect_request_dir / f"{collect_request['id']}.json", "w") as f:
            json.dump(collect_request, f, cls=CustomJSONEncoder, indent=2)


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

        start_time = None
        end_time = None

        response = await client.generate_collect_requests(start_time, end_time)
        print(json.dumps(response, indent=2, cls=CustomJSONEncoder))
        write_collect_requests(response)

        # response = await client.post_collect_response({"sat_id": "25397"})
        # print(response)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
