import asyncio
import signal
from datetime import datetime, timedelta
from typing import Any, Optional

from hamilton.astrodynamics.config import AstrodynamicsClientConfig
from hamilton.base.messages import Message, MessageHandlerType
from hamilton.message_node.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.message_node.interfaces import MessageHandler


class AstrodynamicsTelemetryHandler(MessageHandler):
    def __init__(self):
        super().__init__(MessageHandlerType.TELEMETRY)

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None):
        return message["payload"]["parameters"]


class AstrodynamicsClient(AsyncMessageNodeOperator):
    def __init__(
        self,
        config: AstrodynamicsClientConfig = None,
    ):
        if config is None:
            config = AstrodynamicsClientConfig()
        handlers = [AstrodynamicsTelemetryHandler()]
        super().__init__(config, handlers)
        self.routing_key_base = "observatory.astrodynamics.command"

    async def _publish_command(self, command: str, parameters: dict, rpc: bool = True) -> dict:
        routing_key = f"{self.routing_key_base}.{command}"
        message = self.msg_generator.generate_command(command, parameters)
        if rpc:
            response = await self.publish_rpc_message(routing_key, message)
        else:
            response = await self.publish_message(routing_key, message)
        return response

    async def get_kinematic_state(self, sat_id: str, time: Optional[datetime] = None) -> dict[str, Any]:
        command = "get_kinematic_state"
        parameters = {"sat_id": sat_id, "time": time}
        return await self._publish_command(command, parameters)

    async def get_aos_los(
        self, sat_id: str, time: Optional[datetime] = None, delta_t: int = 12
    ) -> dict[int, list[datetime]]:
        command = "get_aos_los"
        parameters = {"sat_id": sat_id, "time": time, "delta_t": delta_t}
        return await self._publish_command(command, parameters)

    async def get_interpolated_orbit(self, sat_id: str, aos: datetime, los: datetime) -> dict[str, list]:
        command = "get_interpolated_orbit"
        parameters = {"sat_id": sat_id, "aos": aos, "los": los}
        return await self._publish_command(command, parameters)

    async def precompute_orbit(self, sat_id: str) -> None:
        command = "precompute_orbit"
        parameters = {"sat_id": sat_id}
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
    client = AstrodynamicsClient()

    try:
        await client.start()

        sat_id = "39446"
        response = await client.get_kinematic_state(sat_id=sat_id)
        print(response)

        response = await client.get_aos_los(sat_id=sat_id)
        print(response)

        aos = datetime.now()
        los = aos + timedelta(hours=1)
        response = await client.get_interpolated_orbit(sat_id=sat_id, aos=aos, los=los)
        print(response)

        response = await client.precompute_orbit(sat_id=sat_id)
        print(response)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
