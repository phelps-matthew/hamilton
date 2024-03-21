import json
from typing import Any

import pika
from pika.channel import Channel
from pika.spec import Basic

from hamilton.base.message_node import MessageHandler, MessageNode
from hamilton.base.messages import MessageHandlerType
from hamilton.common.utils import CustomJSONDecoder
from hamilton.astrodynamics.api import SpaceObjectTracker
from hamilton.astrodynamics.config import AstrodynamicsControllerConfig


class AstrodynamicsCommandHandler(MessageHandler):
    def __init__(self, so_tracker: SpaceObjectTracker):
        super().__init__(message_type=MessageHandlerType.COMMAND)
        self.so_tracker = so_tracker

    def handle_message(self, ch: Channel, method: Basic.Deliver, properties: pika.BasicProperties, body: bytes) -> Any:
        response = None
        message = json.loads(body, cls=CustomJSONDecoder)
        corr_id = properties.correlation_id
        command = message["payload"]["commandType"]
        parameters = message["payload"]["parameters"]
        routing_key_base = "observatory.astrodynamics.telemetry."
        telemetry_type = None

        if command == "get_kinematic_state":
            telemetry_type = "kinematic_state"
            sat_id = parameters.get("sat_id")
            time = parameters.get("time", None)
            response = self.so_tracker.get_kinematic_state(sat_id, time)

        elif command == "get_kinematic_aos_los":
            telemetry_type = "aos_los"
            sat_id = parameters.get("sat_id")
            time = parameters.get("time")
            delta_t = parameters.get("delta_t")
            response = self.so_tracker.get_aos_los(sat_id, time, delta_t)

        elif command == "get_interpolated_orbit":
            telemetry_type = "interpolated_orbit"
            sat_id = parameters.get("sat_id")
            aos = parameters.get("aos")
            los = parameters.get("los")
            response = self.so_tracker.get_interpolated_orbit(sat_id, aos, los)

        elif command == "precompute_orbit":
            sat_id = parameters.get("sat_id")
            response = self.so_tracker.precompute_orbit(sat_id)

        if response and telemetry_type:
            routing_key = routing_key_base + telemetry_type
            telemetry_msg = self.node_operations.msg_generator.generate_telemetry(telemetry_type, response)
            self.node_operations.publish_message(routing_key, telemetry_msg, corr_id)

        return response


class AstrodynamicsController:
    def __init__(self, config: AstrodynamicsControllerConfig, handlers: list[MessageHandler]):
        self.node: MessageNode = MessageNode(config, handlers, verbosity=3)


if __name__ == "__main__":
    config = AstrodynamicsControllerConfig()
    so_tracker = SpaceObjectTracker(config=config)
    handlers = [AstrodynamicsCommandHandler(so_tracker)]
    controller = AstrodynamicsController(config, handlers)

    # Will stay up indefinitely as producer and consumer threads are non-daemon and keep the process alive
    controller.node.start()
