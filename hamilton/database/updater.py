import asyncio
import logging
import signal
from pathlib import Path
from hamilton.database.config import DBUpdaterConfig
from hamilton.message_node.async_message_node_operator import AsyncMessageNodeOperator
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from hamilton.database.setup_db import setup_and_index_db
from hamilton.database.generators.je9pel_generator import JE9PELGenerator
from hamilton.database.generators.satcom_db_generator import SatcomDBGenerator

logger = logging.getLogger(__name__)


class DBUpdater(AsyncMessageNodeOperator):
    def __init__(self, config: DBUpdaterConfig = None):
        if config is None:
            config = DBUpdaterConfig()
        super().__init__(config=config)
        je9pel = JE9PELGenerator(config)
        self.db_generator = SatcomDBGenerator(config, je9pel)
        self.config = config
        self.json_db_path = Path(self.config.json_db_path).expanduser()
        self.routing_key_base = "observatory.database.telemetry"
        self.db_client: AsyncIOMotorClient = None
        self.db: AsyncIOMotorDatabase = None

    async def _setup_and_index_db(self):
        self.db_client, self.db = await setup_and_index_db()

    async def _publish_db_update_telemetry(self, status: str):
        routing_key = f"{self.routing_key_base}.update"
        message = self.msg_generator.generate_telemetry("update", {"status": status})
        await self.publish_message(routing_key, message)

    async def update_database(self):
        # Send telemetry indicating db update started
        logger.info("Updating database...")
        await self._publish_db_update_telemetry("started")

        # Generate new db
        data = self.db_generator.generate_db(use_cache=False)

        # Start a session for the transaction
        # (ensures delete and insert operations are executed as part of single transaction)
        async with await self.db_client.start_session() as session:
            async with session.start_transaction():
                await self.db[self.config.mongo_collection_name].delete_many({}, session=session)
                await self.db[self.config.mongo_collection_name].insert_many(data.values(), session=session)

        # Send telemetry indicating db update finished
        await self._publish_db_update_telemetry("finished")
        logger.info("Database updated successfully")

    async def start(self) -> None:
        await self.node.start()
        await self._setup_and_index_db()

        while not shutdown_event.is_set():
            await self.update_database()

            sleep_task = asyncio.create_task(asyncio.sleep(self.config.UPDATE_INTERVAL))
            shutdown_task = asyncio.create_task(shutdown_event.wait())

            # Wait either for the interval to pass or for the shutdown event to be set
            done, pending = await asyncio.wait([sleep_task, shutdown_task], return_when=asyncio.FIRST_COMPLETED)

            # Cancel any pending tasks (if shutdown event was triggered before sleep finished)
            for task in pending:
                task.cancel()

    async def stop(self) -> None:
        await self.node.stop()
        self.db_client.close()


shutdown_event = asyncio.Event()


def signal_handler():
    shutdown_event.set()


async def main():
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame), signal_handler)

    # Application setup
    controller = DBUpdater()

    try:
        await controller.start()
        await shutdown_event.wait()  # Wait for the shutdown signal

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
