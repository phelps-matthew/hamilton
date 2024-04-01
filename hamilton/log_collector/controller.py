import asyncio
import json
import logging
import signal
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from hamilton.base.messages import Message, MessageHandlerType
from hamilton.common.utils import CustomJSONEncoder
from hamilton.log_collector.config import LogCollectorConfig
from hamilton.message_node.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.message_node.interfaces import MessageHandler

class LogHandler(MessageHandler):
    """Writes all messages to log file paths based on message type and source hierarchy"""

    def __init__(self, config: LogCollectorConfig):
        super().__init__(message_type=MessageHandlerType.ALL)
        self.config: LogCollectorConfig = config
        self.root_log_dir = Path(config.root_log_dir).expanduser()
        self.max_log_size: int = config.max_log_size
        self.backup_count: int = config.backup_count
        self.loggers = {}  # Cache loggers based on path

    async def get_logger(self, log_path: Path) -> logging.Logger:
        if log_path not in self.loggers:
            # Ensure directory exists
            log_path.parent.mkdir(parents=True, exist_ok=True)

            # Create a logger
            logger = logging.getLogger(str(log_path))
            logger.setLevel(logging.INFO)

            # Add rotating file handler
            handler = RotatingFileHandler(filename=log_path, maxBytes=self.max_log_size, backupCount=self.backup_count)
            formatter = logging.Formatter("%(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)

            # Avoid propagating messages to the root logger
            logger.propagate = False
            self.loggers[log_path] = logger

        return self.loggers[log_path]

    async def write_message(self, message: str, log_path: Path) -> None:
        logger = await self.get_logger(log_path)
        logger.info(message)

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None) -> None:
        message_type = message["messageType"]
        source = message["source"]
        message_out = json.dumps(message, cls=CustomJSONEncoder)

        # Paths for log files
        all_log_path = self.root_log_dir / "all.log"
        type_log_path = self.root_log_dir / f"{message_type}.log"
        source_all_log_path = self.root_log_dir / source.lower() / "all.log"
        source_type_log_path = self.root_log_dir / source.lower() / f"{message_type}.log"

        # Write messages
        await self.write_message(message_out, all_log_path)
        await self.write_message(message_out, type_log_path)
        await self.write_message(message_out, source_all_log_path)
        await self.write_message(message_out, source_type_log_path)

class LogCollector(AsyncMessageNodeOperator):
    def __init__(self, config: LogCollectorConfig = None):
        if config is None:
            config = LogCollectorConfig()
        handlers = [LogHandler(config)]
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
    controller = LogCollector()

    try:
        await controller.start()
        await shutdown_event.wait()  # Wait for the shutdown signal

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await controller.stop()

if __name__ == "__main__":
    asyncio.run(main())
