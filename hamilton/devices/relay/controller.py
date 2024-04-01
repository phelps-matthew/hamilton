import asyncio
import signal
from typing import Optional
import logging

from hamilton.base.messages import Message, MessageHandlerType
from hamilton.devices.relay.config import RelayControllerConfig
from hamilton.message_node.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.message_node.interfaces import MessageHandler
from hamilton.devices.relay.api import FTDIBitbangRelay

logger = logging.getLogger(__name__)


class RelayCommandHandler(MessageHandler):
    def __init__(self, relay_driver: FTDIBitbangRelay):
        super().__init__(message_type=MessageHandlerType.COMMAND)
        self.shutdown_hooks = [self.shutdown_relay]
        self.relay = relay_driver
        self.id_map = {"uhf_bias": 1, "vhf_bias": 2, "vhf_pol": 3, "uhf_pol": 4}
        self.routing_key_base = "observatory.device.mount.telemetry"

    async def shutdown_relay(self):
        self.relay.close()

    def parse_state_to_dict(self, state):
        relay_names = ["uhf_bias", "vhf_bias", "vhf_pol", "uhf_pol"]
        state_dict = {}
        for i, name in enumerate(relay_names):
            # Shift the state right by i places and check the least significant bit
            state_dict[name] = "on" if state & (1 << i) else "off"
        return state_dict

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None) -> None:
        response = None
        command = message["payload"]["commandType"]
        parameters = message["payload"]["parameters"]

        if command == "set":
            telemetry_type = None
            id = parameters.get("id")
            state = parameters.get("state")
            if state not in ["on", "off"]:
                logger.warning(f"{state} not in [on, off]")
                return response
            if id not in self.id_map:
                logger.warning(f"{id} not in {list(self.id_map.keys())}")
                return response
            else:
                response = self.relay.set_relay(relay_num=self.id_map[id], state=state)

        elif command == "status":
            telemetry_type = "status"
            raw_response = self.relay.get_relay_state()
            response = self.parse_state_to_dict(raw_response)

        if telemetry_type is not None:
            routing_key = f"{self.routing_key_base}.{telemetry_type}"
            response = {} if response is None else response
            telemetry_msg = self.node_operations.msg_generator.generate_telemetry(telemetry_type, response)
            await self.node_operations.publish_message(routing_key, telemetry_msg, correlation_id)


class RelayController(AsyncMessageNodeOperator):
    def __init__(self, config: RelayControllerConfig = None):
        if config is None:
            config = RelayControllerConfig()
        relay_driver = FTDIBitbangRelay(device_id=config.DEVICE_ID)
        handlers = [RelayCommandHandler(relay_driver)]
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
    controller = RelayController()

    try:
        await controller.start()
        await shutdown_event.wait()  # Wait for the shutdown signal

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
