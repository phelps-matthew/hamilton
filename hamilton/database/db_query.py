"""Both db_query and db_update acquire and release locks for thread-safe file reading/writing"""

import json
from threading import Lock
from typing import Any

import pika
from pika.channel import Channel
from pika.spec import Basic

from hamilton.base.message_node import MessageHandler, MessageNode
from hamilton.base.messages import MessageHandlerType
from hamilton.common.utils import CustomJSONDecoder
from hamilton.database.config import DBQueryConfig


class DBQueryCommandHandler(MessageHandler):
    def __init__(self, config: DBQueryConfig):
        super().__init__(message_type=MessageHandlerType.COMMAND)
        self.config = config
        self.db_lock = Lock()

    def query_record(self, key) -> dict:
        with self.db_lock:
            with open(self.config.DB_PATH, "r") as file:
                data = json.load(file)
                return data.get(key, {})

    def get_satellite_ids(self) -> list:
        with self.db_lock:
            with open(self.config.DB_PATH, "r") as file:
                data = json.load(file)
                return list(data.keys())

    def get_active_downlink_satellite_ids(self) -> list:
        """Return list of sat ids with at least one JE9PEL active downlink"""
        with self.db_lock:
            with open(self.config.DB_PATH, "r") as file:
                data = json.load(file)
                active_sat_ids = []
                for k, d in data.items():
                    is_active = False
                    if d["je9pel"] is not None:
                        for link in d["je9pel"]["downlink"]:
                            if link["active"]:
                                is_active = True
                    if is_active:
                        active_sat_ids.append(k)
                return active_sat_ids


    def handle_message(self, ch: Channel, method: Basic.Deliver, properties: pika.BasicProperties, body: bytes) -> Any:
        response = None
        message = json.loads(body, cls=CustomJSONDecoder)
        corr_id = properties.correlation_id
        command = message["payload"]["commandType"]
        parameters = message["payload"]["parameters"]
        routing_key_base = "observatory.database.telemetry."
        telemetry_type = None

        if command == "query":
            telemetry_type = "query"
            sat_id = parameters.get("sat_id")
            response = self.query_record(sat_id)
        elif command == "get_satellite_ids":
            telemetry_type = "satellite_ids"
            response = self.get_satellite_ids()
        elif command == "get_active_downlink_satellite_ids":
            telemetry_type = "active_downlink_satellite_ids"
            response = self.get_active_downlink_satellite_ids()

        if response and telemetry_type:
            routing_key = routing_key_base + telemetry_type
            telemetry_msg = self.node_operations.msg_generator.generate_telemetry(telemetry_type, response)
            self.node_operations.publish_message(routing_key, telemetry_msg, corr_id)

        return response

class DBQueryController:
    def __init__(self, config: DBQueryConfig, handlers: list[MessageHandler]):
        self.node: MessageNode = MessageNode(config, handlers, verbosity=3)


if __name__ == "__main__":
    config = DBQueryConfig()
    handlers = [DBQueryCommandHandler(config)]
    controller = DBQueryController(config, handlers)

    # Will stay up indefinitely as producer and consumer threads are non-daemon and keep the process alive
    controller.node.start()