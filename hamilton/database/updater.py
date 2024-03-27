"""Both controller and updater acquire and release locks for thread-safe file reading/writing"""
import asyncio
import logging
import signal
from pathlib import Path
from filelock import Timeout, FileLock
from hamilton.database.config import DBUpdaterConfig
from hamilton.database.generators.je9pel_generator import JE9PELGenerator
from hamilton.database.generators.satcom_db_generator import SatcomDBGenerator
from hamilton.message_node.async_message_node_operator import AsyncMessageNodeOperator


logger = logging.getLogger(__name__)


class DBUpdater(AsyncMessageNodeOperator):
    def __init__(self, config: DBUpdaterConfig = None, verbosity: int = 1):
        if config is None:
            config = DBUpdaterConfig()
        super().__init__(config=config, verbosity=verbosity)
        je9pel = JE9PELGenerator(DBUpdaterConfig)
        self.db_generator = SatcomDBGenerator(DBUpdaterConfig, je9pel)
        self.config = config
        lock_path = Path(config.root_log_dir).expanduser() / "db.lock"
        self.lock = FileLock(lock_path)
        self.routing_key_base = "observatory.database.telemetry."

    async def update_database(self):
        try:
            with self.lock.acquire(timeout=10):
                logger.info("Updating database...")
                routing_key = self.routing_key_base + "update"
                message = self.msg_generator.generate_telemetry("update", {"status": "started"})
                await self.publish_message(routing_key, message)
                self.db_generator.generate_db(use_cache=False)
                logger.info("Database updated successfully")
                message = self.msg_generator.generate_telemetry("update", {"status": "finished"})
                await self.publish_message(routing_key, message)
        except Timeout:
            logger.error("Could not acquire the database lock within the timeout period.")
        except Exception as e:
            logger.error(f"Database update failed: {str(e)}")

    async def start(self) -> None:
        await self.node.start()
        while True:
            await self.update_database()
            await asyncio.sleep(self.config.UPDATE_INTERVAL)


shutdown_event = asyncio.Event()


def signal_handler():
    shutdown_event.set()


async def main():
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame), signal_handler)

    # Application setup
    controller = DBUpdater(verbosity=3)

    try:
        await controller.start()
        await shutdown_event.wait()  # Wait for the shutdown signal

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
