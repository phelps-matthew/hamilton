import json
import time
from typing import Any

import pika
from pika.channel import Channel
from pika.spec import Basic

from hamilton.base.message_node import MessageHandler, MessageNode
from hamilton.base.messages import MessageHandlerType
from hamilton.common.utils import CustomJSONDecoder
from hamilton.devices.relay.config import RelayClientConfig


class RelayTelemetryHandler(MessageHandler):
    def __init__(self):
        super().__init__(MessageHandlerType.TELEMETRY)

    def handle_message(self, ch: Channel, method: Basic.Deliver, properties: pika.BasicProperties, body: bytes) -> Any:
        message = json.loads(body, cls=CustomJSONDecoder)
        return message["payload"]["parameters"]


class RelayClient:
    def __init__(
        self,
        config: RelayClientConfig  = RelayClientConfig(),
        handlers: list[MessageHandler] = [RelayTelemetryHandler()],
    ):
        self.node = MessageNode(config, handlers, verbosity=0)


if __name__ == "__main__":
    client = RelayClient()
    try:
        client.node.start()
        command = "status"
        parameters = {}
        message = client.node.msg_generator.generate_command(command, parameters)
        response = client.node.publish_message("observatory.device.relay.command.status", message)
        print(response)
        response = client.node.publish_rpc_message("observatory.device.relay.command.status", message)
        print(response)

    finally:
        client.node.stop()
