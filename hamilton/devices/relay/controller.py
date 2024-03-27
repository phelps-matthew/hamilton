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
            raw_response = self.relay.get_relay_state()
            response = self.parse_state_to_dict(raw_response)

        if response:
            telemetry_msg = self.node_operations.msg_generator.generate_telemetry("status", response)
            await self.node_operations.publish_message(
                "observatory.device.relay.telemetry.status", telemetry_msg, correlation_id
            )

        return response


class RelayController(AsyncMessageNodeOperator):
    def __init__(self, config: RelayControllerConfig = None, verbosity: int = 1):
        if config is None:
            config = RelayControllerConfig()
        relay_driver = FTDIBitbangRelay(device_id=config.DEVICE_ID, verbosity=verbosity)
        handlers = [RelayCommandHandler(relay_driver)]
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
    controller = RelayController(verbosity=2)

    try:
        await controller.start()
        await shutdown_event.wait()  # Wait for the shutdown signal

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
