"""Both controller and updater acquire and release locks for thread-safe file reading/writing"""

import json
from threading import Lock
from typing import Optional
import asyncio
import signal

from hamilton.base.messages import Message, MessageHandlerType
from hamilton.message_node.interfaces import MessageHandler
from hamilton.message_node.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.database.config import DBControllerConfig


class DBControllerCommandHandler(MessageHandler):
    def __init__(self, config: DBControllerConfig):
        super().__init__(message_type=MessageHandlerType.COMMAND)
        self.config = config
        self.db_lock = Lock()

    async def query_record(self, key) -> dict:
        with self.db_lock:
            with open(self.config.DB_PATH, "r") as file:
                data = json.load(file)
                return data.get(key, {})

    async def get_satellite_ids(self) -> list:
        with self.db_lock:
            with open(self.config.DB_PATH, "r") as file:
                data = json.load(file)
                return list(data.keys())

    async def get_active_downlink_satellite_ids(self) -> list:
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

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None) -> None:
        response = None
        command = message["payload"]["commandType"]
        parameters = message["payload"]["parameters"]
        routing_key_base = "observatory.database.telemetry."
        telemetry_type = None

        if command == "query":
            telemetry_type = "record"
            sat_id = parameters.get("sat_id")
            response = await self.query_record(sat_id)
        elif command == "get_satellite_ids":
            telemetry_type = "satellite_ids"
            response = await self.get_satellite_ids()
        elif command == "get_active_downlink_satellite_ids":
            telemetry_type = "satellite_ids"
            response = await self.get_active_downlink_satellite_ids()

        if response and telemetry_type:
            routing_key = routing_key_base + telemetry_type
            telemetry_msg = self.node_operations.msg_generator.generate_telemetry(telemetry_type, response)
            await self.node_operations.publish_message(routing_key, telemetry_msg, correlation_id)


class DBController(AsyncMessageNodeOperator):
    def __init__(self, config: DBControllerConfig = None, verbosity: int = 1):
        if config is None:
            config = DBControllerConfig()
        handlers = [DBControllerCommandHandler(config)]
        super().__init__(config, handlers, verbosity)


shutdown_event = asyncio.Event()


def signal_handler():
    shutdown_event.set()


async def main():
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame), signal_handler)

    # Application setup
    controller = DBController(verbosity=3)

    try:
        await controller.start()
        await shutdown_event.wait()  # Wait for the shutdown signal

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
