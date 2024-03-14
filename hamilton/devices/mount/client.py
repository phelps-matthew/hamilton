from hamilton.base.message_node import MessageNode, MessageHandler
from hamilton.devices.mount.config import MountClientConfig
from hamilton.common.utils import CustomJSONDecoder
import json


class MountTelemetryHandler(MessageHandler):
    def __init__(self):
        super().__init__("telemetry")

    def handle_message(self, ch, method, properties, body):
        message = json.loads(body, cls=CustomJSONDecoder)
        payload = message["payload"]
        print(f"Telemetry Received. payload: {payload}")


class MountClient:
    def __init__(self, config, handlers: list[MessageHandler]):
        self.node = MessageNode(config, handlers)


if __name__ == "__main__":
    config = MountClientConfig()
    handlers = [MountTelemetryHandler()]
    client = MountClient(config, handlers)
    try:
        client.node.start()
        import time
        time.sleep(4)
        command = "status"
        parameters = {}
        message = client.node.msg_generator.generate_command(command, parameters)
        print("-" * 10)
        print(message)
        print("-" * 10)
        response = client.node.publish_message("observatory.device.mount.command.status", message)
        print("-" * 10)
        print(response)
        print("-" * 10)
        response = client.node.publish_rpc_message("observatory.device.mount.command.status", message)
        print("-" * 10)
        print(f"response: {response}, response type: {type(response)}")
        print("-" * 10)



    finally:
        client.node.stop()
