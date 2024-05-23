"""
Abstract base class for MessageNode, which represents an entity that consumes and publishes data. This naturally includes clients and controllers.

Design choice: All command responses are published as telemetry. If command producer requires a response, they are to include a correlation_id in
the message properties.

Any I/O operations are to be implemented as async methods. This includes any I/O operations that are not directly related to RabbitMQ, such as
file I/O or network I/O.
"""

import asyncio
import logging
from typing import Any, Callable, Optional

from hamilton.base.config import MessageNodeConfig
from hamilton.base.messages import Message, MessageGenerator
from hamilton.messaging.async_consumer import AsyncConsumer
from hamilton.messaging.async_producer import AsyncProducer
from hamilton.messaging.interfaces import IMessageNodeOperations, MessageHandler
from hamilton.messaging.rpc_manager import RPCManager


logger = logging.getLogger(__name__)


class AsyncMessageNode(IMessageNodeOperations):
    def __init__(self, config: MessageNodeConfig, handlers: list[MessageHandler], shutdown_event: asyncio.Event):
        self.config: MessageNodeConfig = config
        self.rpc_manager: RPCManager = RPCManager()
        self.consumer: AsyncConsumer = AsyncConsumer(config, self.rpc_manager, handlers)
        self.producer: AsyncProducer = AsyncProducer(config, self.rpc_manager, shutdown_event)
        self._msg_generator: MessageGenerator = MessageGenerator(config.name, config.message_version)
        self.startup_hooks: list[Callable[[], None]] = []
        self.shutdown_hooks: list[Callable[[], None]] = []
        self.shutdown_event: asyncio.Event = shutdown_event

        # Link MessageNode to handlers' node operations interface and register external shutdown hooks
        for handler in handlers:
            handler.set_node_operations(self)
            self.startup_hooks.extend(handler.startup_hooks)
            self.shutdown_hooks.extend(handler.shutdown_hooks)

    async def start(self):
        """Starts the consumer and publisher asynchronously."""
        await self.consumer.start_consuming()
        await self.producer.start()
        logger.info("Started the consumer and publisher asynchronously.")
        logger.info("Invoking startup hooks...")
        for hook in self.startup_hooks:
            await hook()
        logger.info(f"{self.config.name} startup complete.")

    async def stop(self):
        """Stops the consumer and publisher asynchronously."""
        logger.info("Invoking shutdown hooks...")
        for hook in self.shutdown_hooks:
            await hook()
        await self.consumer.stop()
        await self.producer.stop()
        logger.info("Stopped the consumer and publisher asynchronously.")
        logger.info(f"{self.config.name} shutdown complete.")

    async def publish_message(self, routing_key: str, message: Message, corr_id: Optional[str] = None):
        """Publishes a message asynchronously."""
        await self.producer.publish(routing_key, message, corr_id)

    async def publish_rpc_message(self, routing_key: str, message: Message, timeout: int = 10) -> Any:
        """Sends an RPC message and waits for the response."""
        return await self.producer.publish_rpc_message(routing_key, message, timeout)

    @property
    def msg_generator(self) -> MessageGenerator:
        return self._msg_generator

    @msg_generator.setter
    def msg_generator(self, value: MessageGenerator) -> None:
        self._msg_generator = value
        logger.info("Updated message generator.")
