import asyncio

import signal
from typing import Optional

from hamilton.base.messages import Message, MessageHandlerType
from hamilton.operators.radiometrics.api import Radiometrics
from hamilton.operators.radiometrics.config import RadiometricsControllerConfig
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler
from hamilton.operators.database.client import DBClient


class RadiometricsCommandHandler(MessageHandler):
    def __init__(self, radiometrics: Radiometrics, database: DBClient):
        super().__init__(message_type=MessageHandlerType.COMMAND)
        self.radiometrics: Radiometrics = radiometrics
        self.db = database
        self.startup_hooks = [self._start_db]
        self.routing_key_base = "observatory.radiometrics.telemetry"

    async def _start_db(self):
        await self.db.start()

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None) -> None:
        response = None
        telemetry_type = None
        command = message["payload"]["commandType"]
        parameters = message["payload"]["parameters"]

        if command == "get_tx_profile":
            telemetry_type = "tx_profile"
            sat_id = parameters.get("sat_id")
            response = await self.radiometrics.get_tx_profile(sat_id)

        elif command == "get_downlink_freqs":
            sat_id = parameters.get("sat_id")
            telemetry_type = "downlink_freqs"
            response = await self.radiometrics.get_downlink_freqs(sat_id)

        if telemetry_type is not None:
            routing_key = f"{self.routing_key_base}.{telemetry_type}"
            response = {} if response is None else response
            telemetry_msg = self.node_operations.msg_generator.generate_telemetry(telemetry_type, response)
            await self.node_operations.publish_message(routing_key, telemetry_msg, correlation_id)


class RadiometricsController(AsyncMessageNodeOperator):
    def __init__(self, config: RadiometricsControllerConfig = None):
        if config is None:
            config = RadiometricsControllerConfig()
        self.db = DBClient()
        radiometrics = Radiometrics(config=config, database=self.db)
        handlers = [RadiometricsCommandHandler(radiometrics, self.db)]
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
    controller = RadiometricsController()

    try:
        await controller.start()
        await shutdown_event.wait()  # Wait for the shutdown signal

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())

