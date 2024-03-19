import json
import signal

import pika
from pika.channel import Channel
from pika.spec import Basic

from hamilton.base.message_node import MessageHandler, MessageNode
from hamilton.common.utils import CustomJSONDecoder
from hamilton.devices.mount.api import ROT2Prog
from hamilton.devices.mount.config import MountControllerConfig


def sigint_handler(signum, frame):
    print("SIGINT received, shutting down gracefully...")
    controller.node.stop()


class MountCommandHandler(MessageHandler):
    def __init__(self, mount_driver: ROT2Prog):
        super().__init__(message_type="command")
        self.mount: ROT2Prog = mount_driver

    def handle_message(self, ch: Channel, method: Basic.Deliver, properties: pika.BasicProperties, body: bytes) -> Any:
        response = None
        message = json.loads(body, cls=CustomJSONDecoder)
        corr_id = properties.correlation_id
        command = message["payload"]["commandType"]
        parameters = message["payload"]["parameters"]

        if command == "set":
            response = self.mount.set(parameters.get("azimuth"), parameters.get("el"))
        elif command == "status":
            response = self.mount.status()
        elif command == "stop":
            response = self.mount.stop()

        if response:
            az, el = response
            telemetry_msg = self.node_operations.msg_generator.generate_telemetry(
                "azel", {"azimuth": az, "elevation": el}
            )
            self.node_operations.publish_message("observatory.device.mount.telemetry.azel", telemetry_msg, corr_id)

        return response


class MountController:
    def __init__(self, config: MountControllerConfig, handlers: list[MessageHandler]):
        self.node: MessageNode = MessageNode(config, handlers)


if __name__ == "__main__":
    config = MountControllerConfig()
    mount_driver = ROT2Prog(config.DEVICE_ADDRESS)
    handlers = [MountCommandHandler(mount_driver)]
    controller = MountController(config, handlers)

    # Register the SIGINT handler. Allows graceful shutdown on keyboard interrupt
    signal.signal(signal.SIGINT, sigint_handler)

    # Will stay up indefinitely as producer and consumer threads are non-daemon and keep the process alive
    controller.node.start()
