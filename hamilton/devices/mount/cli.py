#!/home/mgp/miniforge3/envs/gr39/bin/python


import argparse
import json
import time
from typing import Any

import pika
from pika.channel import Channel
from pika.spec import Basic

from hamilton.base.message_node import MessageHandler, MessageNode
from hamilton.base.messages import MessageHandlerType
from hamilton.common.utils import CustomJSONDecoder, CustomJSONEncoder
from hamilton.devices.mount.config import MountClientConfig


class MountTelemetryHandler(MessageHandler):
    def __init__(self):
        super().__init__(MessageHandlerType.TELEMETRY)

    def handle_message(self, ch: Channel, method: Basic.Deliver, properties: pika.BasicProperties, body: bytes) -> Any:
        message = json.loads(body, cls=CustomJSONDecoder)
        return message["payload"]["parameters"]


class MountClient:
    def __init__(self, config, handlers: list[MessageHandler]):
        self.node = MessageNode(config, handlers)


if __name__ == "__main__":
    config = MountClientConfig()
    config.name = "MountCLIClient"
    handlers = [MountTelemetryHandler()]
    client = MountClient(config, handlers)

    # Setup argparser
    parser = argparse.ArgumentParser(
        description="Control the mount system using various commands",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", title="Commands", metavar="<command>")

    # Subparser for the 'set' command
    parser_set = subparsers.add_parser("set", help="Set azimuth and elevation")
    parser_set.add_argument("azimuth", type=float, help="Azimuth angle")
    parser_set.add_argument("elevation", type=float, help="Elevation angle")

    # Subparser for the 'status' command
    parser_status = subparsers.add_parser("status", help="Request status")

    # Subparser for the 'stop' command
    parser_stop = subparsers.add_parser("stop", help="Stop the mount controller")

    args = parser.parse_args()

    try:
        client.node.start()
        if args.command:
            command = args.command
            params = {}
            message = client.node.msg_generator.generate_command(command, params)
            if args.command == "set":
                params = {"azimuth": args.azimuth, "elevation": args.elevation}
                message = client.node.msg_generator.generate_command(command, params)
                response = client.node.publish_rpc_message("observatory.device.mount.command.set", message)
            elif args.command == "status":
                response = client.node.publish_rpc_message("observatory.device.mount.command.status", message)
            elif args.command == "stop":
                response = client.node.publish_rpc_message("observatory.device.mount.command.stop", message)

            print("Response:", response)

    finally:
        client.node.stop()