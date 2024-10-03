import asyncio
import signal
from typing import Optional
from hamilton.base.messages import Message, MessageHandlerType
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler
from hamilton.operators.orchestrator.api import Orchestrator
from hamilton.operators.orchestrator.config import OrchestatorControllerConfig
import logging

logger = logging.getLogger(__name__)


class OrchestratorCommandHandler(MessageHandler):
    def __init__(self, config: OrchestatorControllerConfig, orchestrator: Orchestrator):
        super().__init__(message_type=MessageHandlerType.COMMAND)
        self.config = config
        self.orchestrator: Orchestrator = orchestrator
        self.startup_hooks = [self._start_orchestrator]
        self.shutdown_hooks = [self._stop_orchestrator]
        self.routing_key_base = "observatory.orchestrator.telemetry"

    async def _start_orchestrator(self):
        await self.orchestrator.start()

    async def _stop_orchestrator(self):
        await self.orchestrator.stop()

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None) -> None:
        response = None
        command = message["payload"]["commandType"]
        parameters = message["payload"]["parameters"]

        if command == "orchestrate":
            telemetry_type = None
            if not self.orchestrator.is_running:
                await self.orchestrator.set_task(parameters)
                await self.orchestrator.orchestrate()
            else:
                logger.warning("Orchestrator is already running")

        elif command == "stop_orchestrating":
            telemetry_type = None
            await self.orchestrator.stop_orchestrating()

        elif command == "status":
            telemetry_type = "status"
            response = await self.orchestrator.status()

        if telemetry_type is not None:
            routing_key = f"{self.routing_key_base}.{telemetry_type}"
            telemetry_msg = self.node_operations.msg_generator.generate_telemetry(telemetry_type, response)
            await self.node_operations.publish_message(routing_key, telemetry_msg, correlation_id)


class OrchestratorController(AsyncMessageNodeOperator):
    def __init__(self, config: OrchestatorControllerConfig = None, shutdown_event: asyncio.Event = None):
        if config is None:
            config = OrchestatorControllerConfig()
        orchestrator = Orchestrator()
        handlers = [OrchestratorCommandHandler(config, orchestrator)]
        super().__init__(config, handlers, shutdown_event)
        orchestrator.set_node_operations(self.node)

shutdown_event = asyncio.Event()


def signal_handler():
    shutdown_event.set()


async def main():
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame), signal_handler)

    # Application setup
    controller = OrchestratorController(shutdown_event=shutdown_event)

    try:
        await controller.start()
        await shutdown_event.wait()  # Wait for the shutdown signal

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
