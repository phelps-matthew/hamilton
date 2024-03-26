"""
Abstract base class for MessageNode, which represents an entity that consumes and publishes data. This naturally includes clients and controllers.

Design choice: All command responses are published as telemetry. If command producer requires a response, they are to include a correlation_id in
the message properties.
"""

import json
import logging
import uuid
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

import asyncio
import aio_pika
from aio_pika import ExchangeType, Message as AioPikaMessage
from aio_pika import IncomingMessage

from hamilton.base.config import MessageNodeConfig, Publishing
from hamilton.base.messages import Message, MessageGenerator, MessageHandlerType
from hamilton.common.utils import CustomJSONDecoder, CustomJSONEncoder

# Setup basic logging and create a named logger for the this module
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger("message_node")
logger.propagate = False  # Prevent logging from propagating to the root logger

# Adjust the logging level for aio_pika
aio_pika_logger = logging.getLogger("aio_pika")
aio_pika_logger.setLevel(logging.WARNING)


# Surfaces what methods are available to classes that interface with MessageNode instances
class IMessageNodeOperations(ABC):
    """Defines MessageNode interfacing operations"""

    @abstractmethod
    def publish_message(self, routing_key: str, message: Message, corr_id: Optional[str] = None) -> None:
        pass

    @abstractmethod
    def publish_rpc_message(self, routing_key: str, message: Message, timeout: int = 10) -> Any:
        pass

    @property
    @abstractmethod
    def msg_generator(self) -> MessageGenerator:
        pass


# TODO: Configure default message handler for RPC responses based on `serve_as_rpc` arg
class MessageHandler(ABC):
    def __init__(self, message_type: MessageHandlerType = MessageHandlerType.ALL, serve_as_rpc: bool = False):
        self.message_type: MessageHandlerType = message_type
        self.node_operations: IMessageNodeOperations = None
        self.shutdown_hooks: list[Callable[[], None]] = []

    def set_node_operations(self, node_operations: IMessageNodeOperations) -> None:
        self.node_operations = node_operations

    @abstractmethod
    async def handle_message(self, message: dict, correlation_id: Optional[str] = None) -> Any:
        """Process the received message."""
        raise NotImplementedError


class RPCManager:
    def __init__(self):
        self.rpc_events: dict[str, asyncio.Future] = {}

    def create_future_for_rpc(self, correlation_id: str) -> asyncio.Future:
        """Creates a future for an RPC call identified by the given correlation ID."""
        if correlation_id in self.rpc_events:
            raise ValueError(f"Correlation ID {correlation_id} already in use.")
        future = asyncio.get_event_loop().create_future()
        self.rpc_events[correlation_id] = future
        return future

    def handle_incoming_message(self, message: Message, correlation_id: str):
        """Handles incoming messages by checking if they correspond to any waiting RPC calls."""
        if correlation_id and correlation_id in self.rpc_events:
            future = self.rpc_events.pop(correlation_id, None)
            if future and not future.done():
                future.set_result(message)

    def cleanup(self, correlation_id: str):
        """Cleans up any resources associated with a given correlation ID, if necessary."""
        self.rpc_events.pop(correlation_id, None)


class AsyncConsumer:
    def __init__(self, config: MessageNodeConfig, rpc_manager: RPCManager, handlers: list[MessageHandler] = []):
        self.config: MessageNodeConfig = config
        self.connection: aio_pika.Connection = None
        self.channel: aio_pika.Channel = None
        self.rpc_manager: RPCManager = rpc_manager
        self.handlers = handlers
        self.handlers_map: dict[MessageHandlerType, list[MessageHandler]] = {}

    async def _connect(self):
        self.connection = await aio_pika.connect_robust(self.config.rabbitmq_server)
        self.channel = await self.connection.channel()

    async def _declare_exchanges(self):
        for exchange in self.config.exchanges:
            logger.info(f"Declaring exchange: {exchange.name}")
            await self.channel.declare_exchange(
                exchange.name,
                aio_pika.ExchangeType(exchange.type),
                durable=exchange.durable,
                auto_delete=exchange.auto_delete,
            )
            logger.debug(f"Exchange {exchange.name} declared successfully.")

    async def _setup_bindings(self):
        for binding in self.config.bindings:
            queue_name = f"{binding.exchange}_{self.config.name}"
            queue = await self.channel.declare_queue(queue_name)
            logger.info(f"Declared queue: {queue_name}")
            for routing_key in binding.routing_keys:
                await queue.bind(binding.exchange, routing_key)
                logger.debug(
                    f"Bound queue: {queue_name} to exchange: {binding.exchange} with routing key: {routing_key}"
                )

    async def start_consuming(self):
        logger.info("Starting consuming...")
        await self._connect()
        logger.debug("Connection established.")
        await self._build_handlers_map()
        logger.debug(f"Handlers map built.")
        await self._declare_exchanges()
        logger.debug("Exchanges declared.")
        await self._setup_bindings()
        logger.debug("Bindings setup.")
        # Setup consumer
        queue_name = f"{self.config.bindings[0].exchange}_{self.config.name}"
        queue = await self.channel.get_queue(queue_name)
        logger.debug(f"Queue {queue_name} obtained.")
        await queue.consume(self._on_message_received)
        logger.info("Consumer setup complete.")

    async def _on_message_received(self, message: IncomingMessage):
        # Performs message acknowledgement
        async with message.process():
            message_body = json.loads(message.body.decode(), cls=CustomJSONDecoder)
            try:
                message_type = MessageHandlerType(message_body.get("messageType"))
            except ValueError:
                logger.error(f"Invalid message type: {message_body.get('messageType')}")
            handlers = self.handlers_map.get(message_type, [])
            correlation_id = message.correlation_id
            logger.debug(f"Consumer: Received message with correlation id: {correlation_id} and type: {message_type}")
        if handlers:
            for handler in handlers:
                response = await handler.handle_message(message_body, correlation_id)
                if correlation_id:
                    self.rpc_manager.handle_incoming_message(response, correlation_id)
        else:
            logger.warning(f"No handlers found for message type: {message_type}")

    async def _build_handlers_map(self):
        """Organizes handlers by message type, allowing multiple handlers per type."""
        for handler in self.handlers:
            # If the handler is for 'all' message types, add it to all types except 'ALL'
            if handler.message_type == MessageHandlerType.ALL:
                for message_type in MessageHandlerType:
                    if message_type != MessageHandlerType.ALL:
                        self.handlers_map.setdefault(message_type, []).append(handler)
            else:
                # Add handler to its specific message type
                self.handlers_map.setdefault(handler.message_type, []).append(handler)

    async def stop(self):
        logger.info("Stopping consumer...")
        if self.channel:
            await self.channel.close()
        if self.connection:
            await self.connection.close()
        logger.info("Consumer stopped successfully.")


class AsyncPublisher:
    def __init__(self, config: MessageNodeConfig, rpc_manager: RPCManager):
        self.config: MessageNodeConfig = config
        self.publish_hashmap: dict[str, Publishing] = {}
        self.connection: aio_pika.Connection = None
        self.channel: aio_pika.Channel = None
        self.rpc_manager: RPCManager = rpc_manager
        self.loop = asyncio.get_running_loop()

    async def _build_publish_hashmap(self) -> dict:
        """Builds a hashmap of routing keys to Publishing objects for quick lookup."""
        publish_hashmap = {}
        for publishing in self.config.publishings:
            for routing_key in publishing.routing_keys:
                publish_hashmap[routing_key] = publishing
        logger.info("Publishing map built successfully.")
        return publish_hashmap

    async def _connect(self):
        """Establishes the RabbitMQ connection and channel, and declares exchanges."""
        self.connection = await aio_pika.connect_robust(self.config.rabbitmq_server)
        self.channel = await self.connection.channel()
        self.publish_hashmap = await self._build_publish_hashmap()
        await self._declare_exchanges()

    async def _declare_exchanges(self):
        """Declares necessary exchanges."""
        for exchange in self.config.exchanges:
            try:
                await self.channel.declare_exchange(
                    exchange.name,
                    ExchangeType(exchange.type),
                    durable=exchange.durable,
                    auto_delete=exchange.auto_delete,
                )
                logger.info(f"Exchange '{exchange.name}' declared successfully.")
            except Exception as e:
                logger.error(f"Failed to declare exchange '{exchange.name}': {e}")

    async def publish(self, routing_key: str, message: Message, corr_id: Optional[str] = None):
        """Publishes a message asynchronously."""
        if not self.connection or not self.channel:
            await self._connect()

        publishing = self.publish_hashmap.get(routing_key)
        if not publishing:
            logger.error(f"No publishing configuration found for routing key '{routing_key}'. Message not sent.")
            return

        exchange_name = publishing.exchange
        body = json.dumps(message, cls=CustomJSONEncoder).encode("utf-8")

        try:
            exchange = await self.channel.get_exchange(exchange_name)
            await exchange.publish(
                AioPikaMessage(body=body, content_type="application/json", correlation_id=corr_id),
                routing_key=routing_key,
            )
            logger.debug(f"Message published to exchange '{exchange}' with routing key '{routing_key}'.")
        except Exception as e:
            logger.error(f"Failed to publish message to exchange '{exchange}' with routing key '{routing_key}': {e}")

    async def publish_rpc_message(self, routing_key: str, message: dict, timeout: int = 10) -> Any:
        if not self.connection or not self.channel:
            await self._connect()
            logger.info("Connection and channel established successfully.")

        # Ensure the message generator is used to add necessary fields like correlation_id
        corr_id = str(uuid.uuid4())
        future = self.rpc_manager.create_future_for_rpc(corr_id)
        logger.debug(f"Future created for RPC with correlation id: {corr_id}")

        # Publish the message as usual
        await self.publish(routing_key, message, corr_id)
        logger.info(f"Message published to exchange with routing key: {routing_key}")

        try:
            # Wait for the response or timeout
            response = await asyncio.wait_for(future, timeout)
            logger.info("Response received successfully.")
            return response
        except asyncio.TimeoutError:
            logger.error(f"RPC call timed out after {timeout} seconds.")
            return None
        finally:
            self.rpc_manager.cleanup(corr_id)
            logger.debug("RPC call cleanup completed.")

    async def stop(self):
        """Closes the connection."""
        logger.info("Stopping the publisher...")
        if self.channel:
            await self.channel.close()
        if self.connection:
            await self.connection.close()
        logger.info("Publisher stopped successfully.")


class AsyncMessageNode(IMessageNodeOperations):
    def __init__(self, config: MessageNodeConfig, handlers: list[MessageHandler], verbosity: int = 0):
        self.config: MessageNodeConfig = config
        self.rpc_manager: RPCManager = RPCManager()
        self.consumer: AsyncConsumer = AsyncConsumer(config, self.rpc_manager, handlers)
        self.publisher: AsyncPublisher = AsyncPublisher(config, self.rpc_manager)
        self.loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
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
        logger.info("Started the Consumer and publisher asynchronously.")

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