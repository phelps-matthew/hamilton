import json
from datetime import datetime
from typing import Any, Optional

import pika
from pika.channel import Channel
from pika.spec import Basic

from hamilton.astrodynamics.config import AstrodynamicsClientConfig
from hamilton.base.message_node import MessageHandler, MessageNode
from hamilton.base.messages import MessageHandlerType
from hamilton.common.utils import CustomJSONDecoder


class AstrodynamicsTelemetryHandler(MessageHandler):
    def __init__(self):
        super().__init__(MessageHandlerType.TELEMETRY)

    def handle_message(self, ch: Channel, method: Basic.Deliver, properties: pika.BasicProperties, body: bytes) -> Any:
        message = json.loads(body, cls=CustomJSONDecoder)
        return message["payload"]["parameters"]


class AstrodynamicsClient:
    def __init__(
        self,
        config: AstrodynamicsClientConfig = AstrodynamicsClientConfig(),
        handlers: list[MessageHandler] = [AstrodynamicsTelemetryHandler()],
    ):
        self.node: MessageNode = MessageNode(config, handlers, verbosity=0)
        self.base_routing_key: str = "observatory.astrodynamics.command."

    def publish_message(self, command: str, parameters: dict[str, Any], rpc: bool = True):
        response = None
        routing_key = self.base_routing_key + command
        message = self.node.msg_generator.generate_command(command, parameters)
        if rpc:
            response = self.node.publish_rpc_message(routing_key, message)
        else:
            self.node.publish_message(routing_key, message)
        return response

    def get_kinematic_state(self, sat_id: str, time: Optional[datetime] = None) -> dict[str, Any]:
        command = "get_kinematic_state"
        parameters = {"sat_id": sat_id, "time": time}
        response = self.publish_message(command, parameters, rpc=True)
        return response

    def get_aos_los(self, sat_id: str, time: Optional[datetime] = None, delta_t: int = 12) -> dict[int, list[datetime]]:
        command = "get_aos_los"
        parameters = {"sat_id": sat_id, "time": time, "delta_t": delta_t}
        response = self.publish_message(command, parameters, rpc=True)
        return response

    def get_interpolated_orbit(self, sat_id: str, aos: datetime, los: datetime) -> dict[str, list]:
        command = "get_interpolated_orbit"
        parameters = {"sat_id": sat_id, "aos": aos, "los": los}
        response = self.publish_message(command, parameters, rpc=True)
        return response

    def precompute_orbit(self, sat_id: str) -> None:
        command = "precompute_orbit"
        parameters = {"sat_id": sat_id}
        response = self.publish_message(command, parameters, rpc=False)
        return response


if __name__ == "__main__":
    client = AstrodynamicsClient()
    try:
        client.node.start()

        sat_id = "39446"

        response = client.get_kinematic_state(sat_id=sat_id)
        print(response)

        response = client.get_aos_los(sat_id=sat_id)
        print(response)

        response = client.get_interpolated_orbit(sat_id=sat_id)
        print(response)

        response = client.precompute_orbit(sat_id=sat_id)
        print(response)

    finally:
        client.node.stop()
