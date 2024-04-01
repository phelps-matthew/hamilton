import asyncio
import signal
from typing import Optional

from hamilton.base.messages import Message, MessageHandlerType
from hamilton.message_node.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.message_node.interfaces import MessageHandler
from hamilton.astrodynamics.api import SpaceObjectTracker
from hamilton.astrodynamics.config import AstrodynamicsControllerConfig


class AstrodynamicsCommandHandler(MessageHandler):
    def __init__(self, so_tracker: SpaceObjectTracker):
        super().__init__(message_type=MessageHandlerType.COMMAND)
        self.so_tracker = so_tracker
        self.routing_key_base = "observatory.astrodynamics.telemetry"


    async def handle_message(self, message: Message, correlation_id: Optional[str] = None) -> None:
        response = None
        telemetry_type = None
        command = message["payload"]["commandType"]
        parameters = message["payload"]["parameters"]

        if command == "get_kinematic_state":
            telemetry_type = "kinematic_state"
            sat_id = parameters.get("sat_id")
            time = parameters.get("time", None)
            response = self.so_tracker.get_kinematic_state(sat_id, time)

        elif command == "get_kinematic_aos_los":
            telemetry_type = "aos_los"
            sat_id = parameters.get("sat_id")
            time = parameters.get("time")
            delta_t = parameters.get("delta_t")
            response = self.so_tracker.get_aos_los(sat_id, time, delta_t)

        elif command == "get_interpolated_orbit":
            telemetry_type = "interpolated_orbit"
            sat_id = parameters.get("sat_id")
            aos = parameters.get("aos")
            los = parameters.get("los")
            response = self.so_tracker.get_interpolated_orbit(sat_id, aos, los)

        elif command == "precompute_orbit":
            sat_id = parameters.get("sat_id")
            response = self.so_tracker.precompute_orbit(sat_id)

        if telemetry_type:
            routing_key = f"{self.routing_key_base}.{telemetry_type}"
            response = {} if response is None else response
            telemetry_msg = self.node_operations.msg_generator.generate_telemetry(telemetry_type, response)
            await self.node_operations.publish_message(routing_key, telemetry_msg, correlation_id)

        return response




class AstrodynamicsController(AsyncMessageNodeOperator):
    def __init__(self, config: AstrodynamicsControllerConfig = None, verbosity: int = 1):
        if config is None:
            config = AstrodynamicsControllerConfig()
        so_tracker = SpaceObjectTracker(config=config)
        handlers = [AstrodynamicsCommandHandler(so_tracker)]
        super().__init__(config, handlers, verbosity)




shutdown_event = asyncio.Event()


def signal_handler():
    shutdown_event.set()


async def main():
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame), signal_handler)

    # Application setup
    controller = AstrodynamicsController(verbosity=2)

    try:
        await controller.start()
        await shutdown_event.wait()  # Wait for the shutdown signal

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())