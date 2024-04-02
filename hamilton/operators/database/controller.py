from typing import Optional
import asyncio
import signal

from hamilton.base.messages import Message, MessageHandlerType
from hamilton.messaging.interfaces import MessageHandler
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.operators.database.config import DBControllerConfig
from motor.motor_asyncio import AsyncIOMotorClient
from hamilton.operators.database.setup_db import setup_and_index_db


class DBControllerCommandHandler(MessageHandler):
    def __init__(self, config: DBControllerConfig):
        super().__init__(message_type=MessageHandlerType.COMMAND)
        self.config = config
        self.db_client = AsyncIOMotorClient(self.config.mongo_uri)
        self.db = self.db_client[self.config.mongo_db_name]
        self.startup_hooks = [self._setup_and_index_db]
        self.shutdown_hooks = [self._stop_db_client]
        self.routing_key_base = "observatory.database.telemetry"

    async def _setup_and_index_db(self):
        self.db_client, self.db = await setup_and_index_db()

    async def _stop_db_client(self):
        self.db_client.close()

    async def query_record(self, key) -> dict:
        return await self.db[self.config.mongo_collection_name].find_one({"norad_cat_id": int(key)})

    async def get_satellite_ids(self) -> list:
        ids = await self.db[self.config.mongo_collection_name].distinct("norad_cat_id")
        return [str(id) for id in ids]

    async def get_active_downlink_satellite_ids(self) -> list:
        cursor = self.db[self.config.mongo_collection_name].find(
            {"je9pel.downlink.active": True},  # Query for active downlinks in JE9PEL data
            {"norad_cat_id": 1, "_id": 0},  # Projection
        )
        ids = [str(doc["norad_cat_id"]) async for doc in cursor]
        return ids

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None) -> None:
        response = None
        telemetry_type = None
        command = message["payload"]["commandType"]
        parameters = message["payload"]["parameters"]

        if command == "query_record":
            telemetry_type = "record"
            sat_id = parameters.get("sat_id")
            response = await self.query_record(sat_id)
        elif command == "get_satellite_ids":
            telemetry_type = "satellite_ids"
            response = await self.get_satellite_ids()
        elif command == "get_active_downlink_satellite_ids":
            telemetry_type = "satellite_ids"
            response = await self.get_active_downlink_satellite_ids()

        if telemetry_type:
            routing_key = f"{self.routing_key_base}.{telemetry_type}"
            response = {} if response is None else response
            telemetry_msg = self.node_operations.msg_generator.generate_telemetry(telemetry_type, response)
            await self.node_operations.publish_message(routing_key, telemetry_msg, correlation_id)


class DBController(AsyncMessageNodeOperator):
    def __init__(self, config: DBControllerConfig = None):
        if config is None:
            config = DBControllerConfig()
        handlers = [DBControllerCommandHandler(config)]
        super().__init__(config, handlers)


shutdown_event = asyncio.Event()


def signal_handler():
    shutdown_event.set()


async def main():
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame), signal_handler)

    # Application setup
    controller = DBController()

    try:
        await controller.start()
        await shutdown_event.wait()  # Wait for the shutdown signal

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
