"""
Abstract base class for MessageNode, which represents an entity that consumes and publishes data. This naturally includes clients and controllers.

Design choice: All command responses are published as telemetry. If command producer requires a response, they are to include a correlation_id in
the message properties.

Any I/O operations are to be implemented as async methods. This includes any I/O operations that are not directly related to RabbitMQ, such as
file I/O or network I/O.
"""

import logging
from typing import Any, Callable, Optional

from hamilton.base.config import MessageNodeConfig
from hamilton.base.messages import Message, MessageGenerator
from hamilton.message_node.async_consumer import AsyncConsumer
from hamilton.message_node.async_producer import AsyncProducer
from hamilton.message_node.interfaces import IMessageNodeOperations, MessageHandler
from hamilton.message_node.rpc_manager import RPCManager


# Setup basic logging and create a named logger for the this module
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger("message_node")
logger.propagate = False  # Prevent logging from propagating to the root logger

# Adjust the logging level for aio_pika
aio_pika_logger = logging.getLogger("aio_pika")
aio_pika_logger.setLevel(logging.WARNING)


class AsyncMessageNode(IMessageNodeOperations):
    def __init__(self, config: MessageNodeConfig, handlers: list[MessageHandler], verbosity: int = 0):
        self.config: MessageNodeConfig = config
        self.rpc_manager: RPCManager = RPCManager()
        self.consumer: AsyncConsumer = AsyncConsumer(config, self.rpc_manager, handlers)
        self.publisher: AsyncProducer = AsyncProducer(config, self.rpc_manager)
        self._msg_generator: MessageGenerator = MessageGenerator(config.name, config.message_version)
        self.shutdown_hooks: list[Callable[[], None]] = []

        # Link MessageNode to handlers' node operations interface and register external shutdown hooks
        for handler in handlers:
            handler.set_node_operations(self)
            self.shutdown_hooks.extend(handler.shutdown_hooks)

        if verbosity > 0:
            logger.setLevel(logging.INFO)
            logger.propagate = True
            logger.info("Setting logger level to INFO")
        if verbosity > 1:
            aio_pika_logger.setLevel(logging.INFO)
            logger.info("Setting pika logger level to INFO")
        if verbosity > 2:
            logger.setLevel(logging.DEBUG)
            logger.info("Setting logger level to DEBUG")
        if verbosity > 3:
            aio_pika_logger.setLevel(logging.DEBUG)
            logger.info("Setting pika logger level to DEBUG")

    async def start(self):
        """Starts the consumer and publisher asynchronously."""
        await self.consumer.start_consuming()
        logger.info("Started the consumer and publisher asynchronously.")

    async def stop(self):
        """Stops the consumer and publisher asynchronously."""
        await self.consumer.stop()
        await self.publisher.stop()
        logger.info("Stopped the consumer and publisher asynchronously.")

    async def publish_message(self, routing_key: str, message: Message, corr_id: Optional[str] = None):
        """Publishes a message asynchronously."""
        await self.publisher.publish(routing_key, message, corr_id)

    async def publish_rpc_message(self, routing_key: str, message: Message, timeout: int = 10) -> Any:
        """Sends an RPC message and waits for the response."""
        return await self.publisher.publish_rpc_message(routing_key, message, timeout)

    @property
    def msg_generator(self) -> MessageGenerator:
        return self._msg_generator

    @msg_generator.setter
    def msg_generator(self, value: MessageGenerator) -> None:
        self._msg_generator = value
        logger.info("Updated message generator.")
