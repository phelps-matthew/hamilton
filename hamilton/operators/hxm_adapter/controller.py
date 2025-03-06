import asyncio
import signal
from typing import Optional
from hamilton.base.messages import Message, MessageHandlerType
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler
from hamilton.operators.hxm_adapter.api import HXMAdapter
from hamilton.operators.hxm_adapter.config import HXMAdapterControllerConfig


class HXMAdapterCommandHandler(MessageHandler):
    def __init__(self, hxm_adapter: HXMAdapter):
        super().__init__(message_type=MessageHandlerType.COMMAND)
        self.hxm_adapter: HXMAdapter = hxm_adapter
        self.startup_hooks = [self._start]
        self.shutdown_hooks = [self._stop]
        self.routing_key_base = "observatory.hxm_adapter.telemetry"

    async def _start(self):
        await self.hxm_adapter.start()

    async def _stop(self):
        await self.hxm_adapter.stop()

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None) -> None:
        response = None
        command = message["payload"]["commandType"]
        parameters = message["payload"]["parameters"]

        if command == "post_collect_response":
            telemetry_type = None
            await self.hxm_adapter.submit_collect_response(parameters)

        if command == "status":
            telemetry_type = "status"
            response = await self.hxm_adapter.status()

        if command == "generate_collect_requests":
            telemetry_type = "collect_request_list"
            response = await self.hxm_adapter.generate_collect_requests(parameters.get("start_time"), parameters.get("end_time"))

        if telemetry_type is not None:
            routing_key = f"{self.routing_key_base}.{telemetry_type}"
            telemetry_msg = self.node_operations.msg_generator.generate_telemetry(telemetry_type, response)
            await self.node_operations.publish_message(routing_key, telemetry_msg, correlation_id)


class HXMAdapterController(AsyncMessageNodeOperator):
    def __init__(self, config: HXMAdapterControllerConfig = None, shutdown_event: asyncio.Event = None):
        if config is None:
            config = HXMAdapterControllerConfig()
        self.hxm_adapter = HXMAdapter(config, shutdown_event)
        handlers = [HXMAdapterCommandHandler(self.hxm_adapter)]
        super().__init__(config, handlers, shutdown_event)


shutdown_event = asyncio.Event()


def signal_handler():
    shutdown_event.set()


async def main():
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame), signal_handler)

    # Application setup
    controller = HXMAdapterController(shutdown_event=shutdown_event)

    try:
        await controller.start()
        await controller.hxm_adapter.poll_hxm_collect_request()
        await shutdown_event.wait()  # Wait for the shutdown signal

    except Exception as e:
        print(f"An unexpected error occurred in the controller: {e}")

    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
