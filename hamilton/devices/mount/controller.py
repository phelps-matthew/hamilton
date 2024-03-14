from hamilton.base.message_node import MessageNode, MessageHandler
from hamilton.devices.mount.api import ROT2Prog
from hamilton.devices.mount.config import MountControllerConfig
from hamilton.common.utils import CustomJSONDecoder
import threading
import json


class MountCommandHandler(MessageHandler):
    def __init__(self, mount_driver: ROT2Prog):
        super().__init__(message_type="command")
        self.mount = mount_driver

    def handle_message(self, ch, method, properties, body):
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
    def __init__(self, config, handlers: list[MessageHandler]):
        self.node = MessageNode(config, handlers)


if __name__ == "__main__":
    config = MountControllerConfig()
    mount_driver = ROT2Prog(config.DEVICE_ADDRESS)
    handlers = [MountCommandHandler(mount_driver)]
    controller = MountController(config, handlers)

    controller.node.start()
    import time
    time.sleep(5)
    # Blocks the main thread indefinitely until a SIGINT or SIGTERM is received.
    # threading.Event().wait()