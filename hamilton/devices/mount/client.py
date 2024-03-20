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
        payload = message["payload"]
        return message


class MountClient:
    def __init__(self, config, handlers: list[MessageHandler]):
        self.node = MessageNode(config, handlers)


if __name__ == "__main__":
    config = MountClientConfig()
    handlers = [MountTelemetryHandler()]
    client = MountClient(config, handlers)
    try:
        client.node.start()
        time.sleep(1)
        command = "status"
        parameters = {}
        message = client.node.msg_generator.generate_command(command, parameters)
        response = client.node.publish_message("observatory.device.mount.command.status", message)
        print(response)
        response = client.node.publish_rpc_message("observatory.device.mount.command.status", message)
        print(response)

    finally:
        client.node.stop()
