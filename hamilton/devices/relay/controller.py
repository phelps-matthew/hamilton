import json
from typing import Any
import logging

import pika
from pika.channel import Channel
from pika.spec import Basic

from hamilton.base.message_node import MessageHandler, MessageNode
from hamilton.base.messages import MessageHandlerType
from hamilton.common.utils import CustomJSONDecoder
from hamilton.devices.relay.api import FTDIBitbangRelay
from hamilton.devices.relay.config import RelayControllerConfig

# Setup basic logging and create a named logger for the this module
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger("relay_controller")


class RelayCommandHandler(MessageHandler):
    def __init__(self, relay_driver: FTDIBitbangRelay):
        super().__init__(message_type=MessageHandlerType.COMMAND)
        self.shutdown_hooks = [self.shutdown_relay]
        self.relay = relay_driver
        self.id_map = {"uhf_bias": 1, "vhf_bias": 2, "vhf_pol": 3, "uhf_pol": 4}

    def shutdown_relay(self):
        self.relay.close()

    def parse_state_to_dict(self, state):
        relay_names = ["uhf_bias", "vhf_bias", "vhf_pol", "uhf_pol"]
        state_dict = {}
        for i, name in enumerate(relay_names):
            # Shift the state right by i places and check the least significant bit
            state_dict[name] = "on" if state & (1 << i) else "off"
        return state_dict

    def handle_message(self, ch: Channel, method: Basic.Deliver, properties: pika.BasicProperties, body: bytes) -> Any:
        response = None
        message = json.loads(body, cls=CustomJSONDecoder)
        corr_id = properties.correlation_id
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
            self.node_operations.publish_message("observatory.device.relay.telemetry.status", telemetry_msg, corr_id)

        return response


class RelayController:
    def __init__(self, config: RelayControllerConfig, handlers: list[MessageHandler]):
        self.node: MessageNode = MessageNode(config, handlers, verbosity=3)


if __name__ == "__main__":
    config = RelayControllerConfig()
    relay_driver = FTDIBitbangRelay(device_id=config.DEVICE_ID, verbosity=2)
    handlers = [RelayCommandHandler(relay_driver)]
    controller = RelayController(config, handlers)

    # Will stay up indefinitely as producer and consumer threads are non-daemon and keep the process alive
    controller.node.start()
