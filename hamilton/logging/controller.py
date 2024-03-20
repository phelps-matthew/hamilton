import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pika
from pika.channel import Channel
from pika.spec import Basic

from hamilton.base.message_node import MessageHandler, MessageNode
from hamilton.base.messages import MessageHandlerType
from hamilton.common.utils import CustomJSONDecoder, CustomJSONEncoder
from hamilton.logging.config import LogCollectorConfig


class LogHandler(MessageHandler):
    """Writes all messages to log file paths based on message type and source hierarchy"""

    def __init__(self, config: LogCollectorConfig):
        super().__init__(message_type=MessageHandlerType.ALL)
        self.config: LogCollectorConfig = config
        self.root_log_dir = Path(config.root_log_dir).expanduser()
        self.max_log_size: int = config.max_log_size
        self.backup_count: int = config.backup_count
        self.loggers = {}  # Cache loggers based on path

    def get_logger(self, log_path: Path) -> logging.Logger:
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

    def write_message(self, message: str, log_path: Path) -> None:
        logger = self.get_logger(log_path)
        logger.info(message)

    def handle_message(self, ch: Channel, method: Basic.Deliver, properties: pika.BasicProperties, body: bytes) -> None:
        message = json.loads(body, cls=CustomJSONDecoder)
        message_type = message["messageType"]
        source = message["source"]
        message_out = json.dumps(message, cls=CustomJSONEncoder)

        # Paths for log files
        all_log_path = self.root_log_dir / "all.log"
        type_log_path = self.root_log_dir / f"{message_type}.log"
        source_all_log_path = self.root_log_dir / source.lower() / "all.log"
        source_type_log_path = self.root_log_dir / source.lower() / f"{message_type}.log"

        # Write messages
        self.write_message(message_out, all_log_path)
        self.write_message(message_out, type_log_path)
        self.write_message(message_out, source_all_log_path)
        self.write_message(message_out, source_type_log_path)


class LogCollector:
    def __init__(self, config: LogCollectorConfig, handlers: list[MessageHandler]):
        self.node: MessageNode = MessageNode(config, handlers, verbosity=2)


if __name__ == "__main__":
    config = LogCollectorConfig()
    handlers = [LogHandler(config)]
    controller = LogCollector(config, handlers)

    # Will stay up indefinitely as producer and consumer threads are non-daemon and keep the process alive
    controller.node.start()
