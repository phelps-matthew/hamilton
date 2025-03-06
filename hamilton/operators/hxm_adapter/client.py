import asyncio
import signal
from typing import Optional
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json

from hamilton.base.messages import MessageHandlerType, Message
from hamilton.operators.hxm_adapter.config import HXMAdapterClientConfig
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler
from hamilton.base.task import Task
from hamilton.common.utils import CustomJSONEncoder


class HXMAdapterTelemetryHandler(MessageHandler):
    def __init__(self):
        super().__init__(MessageHandlerType.TELEMETRY)

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None):
        return message["payload"]["parameters"]


class HXMAdapterClient(AsyncMessageNodeOperator):
    def __init__(self, config: HXMAdapterClientConfig = None, shutdown_event: asyncio.Event = None):
        if config is None:
            config = HXMAdapterClientConfig()
        handlers = [HXMAdapterTelemetryHandler()]
        super().__init__(config, handlers, shutdown_event)
        self.routing_key_base = "observatory.hxm_adapter.command"

    async def _publish_command(self, command: str, parameters: dict, rpc: bool = True, timeout: int = 10) -> dict:
        routing_key = f"{self.routing_key_base}.{command}"
        message = self.msg_generator.generate_command(command, parameters)
        if rpc:
            response = await self.publish_rpc_message(routing_key, message, timeout=timeout)
        else:
            response = await self.publish_message(routing_key, message)
        return response

    async def post_collect_response(self, collect_response: dict):
        """Submit a collect response to HXM."""
        command = "post_collect_response"
        parameters = collect_response
        return await self._publish_command(command, parameters, rpc=False)

    async def status(self):
        """Get the current status of the HXM adapter."""
        command = "status"
        parameters = {}
        return await self._publish_command(command, parameters, rpc=True)

    async def generate_collect_requests(
        self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ):
        """Generate collect requests for the given time range."""
        command = "generate_collect_requests"
        parameters = {
            "start_time": start_time.isoformat() if start_time else None,
            "end_time": end_time.isoformat() if end_time else None,
        }
        return await self._publish_command(command, parameters, rpc=True, timeout=30)


def write_collect_requests(collect_request_list: list):
    """Write collect requests to JSON files."""
    collect_request_dir = Path("~/hamilton/hxm_adapter/collect_request_batch").expanduser()
    if collect_request_dir.exists() and collect_request_dir.is_dir():
        for file in collect_request_dir.iterdir():
            if file.is_file():
                file.unlink()
    collect_request_dir.mkdir(parents=True, exist_ok=True)

    for collect_request in collect_request_list:
        # Handle datetime objects if present
        if isinstance(collect_request.get("createdAt"), datetime):
            collect_request["createdAt"] = collect_request["createdAt"].strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        if isinstance(collect_request.get("startTime"), datetime):
            collect_request["startTime"] = collect_request["startTime"].strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        if isinstance(collect_request.get("endTime"), datetime):
            collect_request["endTime"] = collect_request["endTime"].strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
            
        with open(collect_request_dir / f"{collect_request['id']}.json", "w") as f:
            json.dump(collect_request, f, cls=CustomJSONEncoder, indent=2)
    
    return collect_request_dir


shutdown_event = asyncio.Event()


def signal_handler():
    shutdown_event.set()


async def main():
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame), signal_handler)

    # Application setup
    client = HXMAdapterClient(shutdown_event=shutdown_event)

    try:
        await client.start()

        # Get current status
        status = await client.status()
        print("Current status:")
        print(json.dumps(status, indent=2, cls=CustomJSONEncoder))

        # Generate collect requests
        print("\nGenerating collect requests...")
        start_time = None
        end_time = None
        collect_requests = await client.generate_collect_requests(start_time, end_time)
        print(f"Generated {len(collect_requests)} collect requests")
        
        # Write collect requests to files
        output_dir = write_collect_requests(collect_requests)
        print(f"Collect requests written to {output_dir}")

        # Example of submitting a collect response
        # collect_response = {
        #     "modelType": "CollectResponseAccepted",
        #     "classificationMarking": "U",
        #     "source": "hamilton-x-machina",
        #     "origin": "TEST-ORIGIN",
        #     "collect_request": {"id": "test-id"},
        #     "actualStartDateTime": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        #     "actualEndDateTime": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat().replace('+00:00', 'Z'),
        #     "notes": "Test response"
        # }
        # await client.post_collect_response(collect_response)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
