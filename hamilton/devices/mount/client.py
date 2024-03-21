import json
import time
from typing import Any

import pika
from pika.channel import Channel
from pika.spec import Basic

from hamilton.base.message_node import MessageHandler, MessageNode
from hamilton.base.messages import MessageHandlerType
from hamilton.common.utils import CustomJSONDecoder
from hamilton.devices.mount.config import MountClientConfig


class MountTelemetryHandler(MessageHandler):
    def __init__(self):
        super().__init__(MessageHandlerType.TELEMETRY)

    def handle_message(self, ch: Channel, method: Basic.Deliver, properties: pika.BasicProperties, body: bytes) -> Any:
        message = json.loads(body, cls=CustomJSONDecoder)
        return message["payload"]["parameters"]


class MountClient:
    def __init__(
        self,
        config: MountClientConfig = MountClientConfig(),
        handlers: list[MessageHandler] = [MountTelemetryHandler()],
    ):
        self.node = MessageNode(config, handlers)


if __name__ == "__main__":
    client = MountClient()
    try:
        client.node.start()
        command = "status"
        parameters = {}
        message = client.node.msg_generator.generate_command(command, parameters)
        response = client.node.publish_message("observatory.device.mount.command.status", message)
        print(response)
        response = client.node.publish_rpc_message("observatory.device.mount.command.status", message)
        print(response)

    finally:
        client.node.stop()
