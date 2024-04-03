
import asyncio
import signal
from typing import Optional
from hamilton.base.messages import Message, MessageHandlerType
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler
from hamilton.operators.orchestrator.manager import OrchestratorManager
from hamilton.operators.orchestrator.config import OrchestatorControllerConfig


class OrchestratorCommandHandler(MessageHandler):
    def __init__(self, manager: OrchestratorManager):
        super().__init__(message_type=MessageHandlerType.COMMAND)
        self.config = self.node_operations.config
        self.manager: OrchestratorManager = manager
        self.startup_hooks = [self._start_manager]
        self.shutdown_hooks = [self._stop_manager]
        self.routing_key_base = "observatory.orchestrator.telemetry"

    async def _start_manager(self):
        await self.manager.start()

    async def _stop_manager(self):
        await self.manager.stop()

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None) -> None:
        response = None
        command = message["payload"]["commandType"]
        parameters = message["payload"]["parameters"]

        if command == "enqueue_task":
            await self.manager.enqueue_task(self.manager.process_task, parameters)

        elif command == "stop":
            await self.manager.stop()

        elif command == "status":
            telemetry_type = "status"
            response = await self.manager.status()

        if telemetry_type is not None:
            routing_key = f"{self.routing_key_base}.{telemetry_type}"
            telemetry_msg = self.node_operations.msg_generator.generate_telemetry(telemetry_type, response)
            await self.node_operations.publish_message(routing_key, telemetry_msg, correlation_id)


class OrchestratorController(AsyncMessageNodeOperator):
    def __init__(self, config: OrchestatorControllerConfig = None):
        if config is None:
            config = OrchestatorControllerConfig()
        manager = OrchestratorManager()
        handlers = [OrchestratorCommandHandler(manager)]
        super().__init__(config, handlers)


shutdown_event = asyncio.Event()


def signal_handler():
    shutdown_event.set()


async def main():
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame), signal_handler)

    # Application setup
    controller = OrchestratorController()

    try:
        await controller.start()
        await shutdown_event.wait()  # Wait for the shutdown signal

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
