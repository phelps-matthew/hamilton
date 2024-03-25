"""
Abstract base class for MessageNode, which represents an entity that consumes and publishes data. This naturally includes clients and controllers.

Design choice: All command responses are published as telemetry. If command producer requires a response, they are to include a correlation_id in
the message properties.

See: https://github.com/pika/pika/blob/main/examples/long_running_publisher.py
"""

import json
import logging
import signal
import threading
import uuid
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional, Union

import pika
from pika.channel import Channel
from pika.spec import Basic

from hamilton.base.config import MessageNodeConfig, Publishing
from hamilton.base.messages import Message, MessageGenerator, MessageHandlerType
from hamilton.common.utils import CustomJSONDecoder, CustomJSONEncoder

# Setup basic logging and create a named logger for the this module
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger("message_node")
logger.propagate = False  # Prevent logging from propagating to the root logger

# Adjust the logging level for pika
pika_logger = logging.getLogger("pika")
pika_logger.setLevel(logging.WARNING)


# Surfaces what methods are available to classes that interface with MessageNode instances
class IMessageNodeOperations(ABC):
    """Defines MessageNode interfacing operations"""

    @abstractmethod
    def publish_message(self, routing_key: str, message: Message) -> None:
        pass

    @abstractmethod
    def publish_rpc_message(self, routing_key: str, message: Message) -> Any:
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
    def handle_message(self, ch: Channel, method: Basic.Deliver, properties: pika.BasicProperties, body: bytes) -> Any:
        """Process the received message."""
        pass


class Consumer(threading.Thread):
    def __init__(self, config: MessageNodeConfig, handlers: list[MessageHandler]):
        super().__init__()
        self.config: MessageNodeConfig = config
        self.shutdown_event: threading.Event = threading.Event()
        self.ready_event: threading.Event = threading.Event()
        self.responses: dict[str, Union[threading.Event, Any]] = {}
        self.responses_lock: threading.Lock = threading.Lock()
        self.handlers_map: dict[MessageHandlerType, list[MessageHandler]] = self._build_handlers_map(handlers)
        self.connection: pika.BlockingConnection = None
        self.channel: Channel = None

    def run(self) -> None:
        try:
            self._connect()
            while not self.shutdown_event.is_set():
                self.connection.process_data_events(time_limit=1)  # Check for shutdown flag

        except Exception as e:
            logger.error(f"An error occurred in the Consumer: {e}")
        self._cleanup()

    def _on_message_received(
        self, ch: Channel, method: Basic.Deliver, properties: pika.BasicProperties, body: bytes
    ) -> None:
        message = json.loads(body, cls=CustomJSONDecoder)
        message_type = MessageHandlerType(message.get("messageType"))
        logger.debug(f"Receieved message of type {message_type} and body {message}")

        # Extract and handle the correlation_id for RPC responses
        corr_id = properties.correlation_id
        event = None
        if corr_id:
            item = self.get_event_response(corr_id)
            if item:
                event = item.get("event", None)
                if not event:
                    logger.warning(f"No event associated with correlation id `{corr_id}")

        # Pass message to registered handlers and trigger response for RPC requests
        handlers = self.handlers_map.get(message_type, [])
        if handlers:
            for handler in handlers:
                response = handler.handle_message(ch, method, properties, body)
                if corr_id and event:
                    self.set_event_response(corr_id, event, response)
                    event.set()
        else:
            logger.warning(f"No handlers found for message type: {message_type}")

    def _connect(self):
        """Establishes the RabbitMQ connection and channel, and declares exchanges."""
        try:
            logger.info("Establishing Consumer connection")
            self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.config.rabbitmq_server))
            self.channel = self.connection.channel()
            self._declare_exchanges()
            self._setup_bindings()
            logger.info(
                f"Consumer connection established: connection: {self.connection.is_open}, channel: {self.channel.is_open}"
            )
            if not self.ready_event.is_set():
                self.ready_event.set()
        except Exception as e:
            logging.error(f"Failed to establish connection or channel: {e}")

    def _cleanup(self) -> None:
        if self.channel:
            self.channel.stop_consuming()
            if self.channel.is_open:
                self.channel.close()
        if self.connection and self.connection.is_open:
            self.connection.close()

    def _declare_exchanges(self) -> None:
        for exchange in self.config.exchanges:
            try:
                if self.channel:
                    self.channel.exchange_declare(
                        exchange=exchange.name,
                        exchange_type=exchange.type,
                        durable=exchange.durable,
                        auto_delete=exchange.auto_delete,
                    )
                logger.info("Exchanges imported and configured successfully.")
            except Exception as e:
                logger.error(f"Failed to declare exchange '{exchange.name}': {e}")

    def _setup_bindings(self) -> None:
        for binding in self.config.bindings:
            queue_name = f"{binding.exchange}_{self.config.name}"
            try:
                self.channel.queue_declare(queue=queue_name)
                for routing_key in binding.routing_keys:
                    self.channel.queue_bind(exchange=binding.exchange, queue=queue_name, routing_key=routing_key)
                consumer_tag = self.channel.basic_consume(
                    queue=queue_name, on_message_callback=self._on_message_received, auto_ack=True
                )
                logger.info(
                    f"Bindings for queue '{queue_name}' with consumer tag '{consumer_tag}' configured successfully."
                )
            except Exception as e:
                logger.error(f"Failed to setup bindings for queue '{queue_name}': {e}")

    def _build_handlers_map(self, handlers: list[MessageHandler]) -> dict[MessageHandlerType, list[MessageHandler]]:
        """Organizes handlers by message type, allowing multiple handlers per type."""
        handler_map = {}
        for handler in handlers:
            # If the handler is for 'all' message types, add it to all types except 'ALL'
            if handler.message_type == MessageHandlerType.ALL:
                for message_type in MessageHandlerType:
                    if message_type != MessageHandlerType.ALL:
                        handler_map.setdefault(message_type, []).append(handler)
            else:
                # Add handler to its specific message type
                handler_map.setdefault(handler.message_type, []).append(handler)

        return handler_map

    def get_event_response(self, corr_id: str) -> dict[str, Union[threading.Event, Any]]:
        """Retrieve event-response pair based on its correlation ID in a thread-safe manner."""
        with self.responses_lock:
            return self.responses.get(corr_id)

    def set_event_response(self, corr_id: str, event: threading.Event, response: Any = None) -> None:
        """Set an event-response pair based on its correlation ID in a thread-safe manner."""
        with self.responses_lock:
            self.responses[corr_id] = {"event": event, "response": response}

    def del_event_response(self, corr_id: str) -> None:
        """Delete an event-response based on its correlation ID in a thread-safe manner."""
        with self.responses_lock:
            if corr_id in self.responses:
                del self.responses[corr_id]

    def stop(self) -> None:
        self.ready_event.clear()
        self.shutdown_event.set()


class Publisher(threading.Thread):
    def __init__(self, config: MessageNodeConfig):
        super().__init__()
        self.config: MessageNodeConfig = config
        self.publish_hashmap: dict[str, Publishing] = {}
        self.shutdown_event: threading.Event = threading.Event()
        self.ready_event: threading.Event = threading.Event()
        self.connection: pika.BlockingConnection = None
        self.channel: Channel = None
        self.logger = logger
        self._build_publish_hashmap()

    def _build_publish_hashmap(self) -> None:
        """Builds a hashmap of routing keys to Publishing objects for quick lookup."""
        for publishing in self.config.publishings:
            for routing_key in publishing.routing_keys:
                self.publish_hashmap[routing_key] = publishing
        logger.info("Publishing map built successfully.")

    def run(self) -> None:
        try:
            self._connect()
            # Process data events to handle heartbeats and connection maintenance
            while not self.shutdown_event.is_set():
                # Check and process data events for a maximum of 1 sec before returning control
                # to loop.
                self.connection.process_data_events(time_limit=1)

        except Exception as e:
            logger.error(f"An error occurred in the Producer: {e}")

        self._cleanup()

    def _declare_exchanges(self) -> None:
        for exchange in self.config.exchanges:
            try:
                if self.channel:
                    self.channel.exchange_declare(
                        exchange=exchange.name,
                        exchange_type=exchange.type,
                        durable=exchange.durable,
                        auto_delete=exchange.auto_delete,
                    )
                logger.info("Publisher Exchanges imported and configured successfully.")
            except Exception as e:
                logger.error(f"Failed to declare exchange '{exchange.name}': {e}")

    def _connect(self):
        """Establishes the RabbitMQ connection and channel, and declares exchanges."""
        try:
            logger.info("Establishing Publisher connection")
            self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.config.rabbitmq_server))
            self.channel = self.connection.channel()
            self._declare_exchanges()
            logger.info(
                f"Publisher connection established: connection: {self.connection.is_open}, channel: {self.channel.is_open}"
            )
            if not self.ready_event.is_set():
                self.ready_event.set()
        except Exception as e:
            logging.error(f"Failed to establish connection or channel: {e}")

    def _cleanup(self) -> None:
        if self.channel:
            self.channel.stop_consuming()
            if self.channel.is_open:
                self.channel.close()
        if self.connection and self.connection.is_open:
            self.connection.close()

    def _publish(self, item):
        exchange, routing_key, properties, body = item
        self.channel.basic_publish(exchange=exchange, routing_key=routing_key, properties=properties, body=body)

    def publish(self, routing_key: str, message: Message, corr_id=None) -> None:
        publishing = self.publish_hashmap.get(routing_key)
        properties = pika.BasicProperties(correlation_id=corr_id)
        body = json.dumps(message, cls=CustomJSONEncoder)
        if not publishing:
            logger.error(f"No publishing configuration found for routing key '{routing_key}'. Message not sent.")
            return
        exchange = publishing.exchange
        if not self.channel:
            logging.error("Channel is not available. Unable to publish.")
        if self.channel and not self.channel.is_open:
            logging.error("Channel is not open. Unable to publish.")
            return
        try:
            item = exchange, routing_key, properties, body
            self.connection.add_callback_threadsafe(lambda: self._publish(item))
            logger.debug(f"Message published to exchange '{exchange}' with routing key '{routing_key}'.")
        except Exception as e:
            logger.error(f"Failed to publish message to exchange '{exchange}' with routing key '{routing_key}': {e}")

    def stop(self) -> None:
        self.ready_event.clear()
        self.shutdown_event.set()


class MessageNode(IMessageNodeOperations):

    def __init__(self, config: MessageNodeConfig, handlers: list[MessageHandler] = [], verbosity: int = 0):
        self.config: MessageNodeConfig = config
        self._msg_generator: MessageGenerator = MessageGenerator(config.name, config.message_version)
        self.shutdown_hooks: list[Callable[[], None]] = []

        # Link MessageNode to handlers' node operations interface and register external shutdown hooks
        for handler in handlers:
            handler.set_node_operations(self)
            self.shutdown_hooks.extend(handler.shutdown_hooks)

        if verbosity > 0:
            logger.setLevel(logging.INFO)
            logger.propagate = True
        if verbosity > 1:
            pika_logger.setLevel(logging.INFO)
        if verbosity > 2:
            logger.setLevel(logging.DEBUG)
        if verbosity > 3:
            pika_logger.setLevel(logging.DEBUG)

        self.consumer: Consumer = Consumer(config, handlers)
        self.publisher: Publisher = Publisher(config)

    # Required form for IMessageNodeOperations
    @property
    def msg_generator(self) -> MessageGenerator:
        return self._msg_generator

    # Required form for IMessageNodeOperations
    @msg_generator.setter
    def msg_generator(self, value: MessageGenerator) -> None:
        self._msg_generator = value

    def signal_handler(self, signum, frame):
        logging.info("SIGINT received, initiating shutdown...")
        self.stop()

    def start(self) -> None:
        """Intialize MessageNode and signal handler, and start consumer and producer threads."""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        logger.info(f"Starting {self.config.name}...")
        logger.info(f"Starting Consumer..")
        self.consumer.start()
        logger.info(f"Starting Publisher..")
        self.publisher.start()
        self.consumer.ready_event.wait()
        self.publisher.ready_event.wait()

    def stop(self) -> None:
        """Stop RMQ consumption and join consumer and producer threads."""
        try:
            logger.info("Invoking shutdown hooks...")
            for hook in self.shutdown_hooks:
                hook()
            logger.info("Stopping Consumer...")
            self.consumer.stop()
            self.consumer.join()
            logger.info("Stopping Publisher...")
            self.publisher.stop()
            self.publisher.join()
        except Exception as e:
            logger.error(f"An error occurred during shutdown: {e}")
        finally:
            logger.info(f"{self.config.name} shutdown complete.")

    def publish_message(self, routing_key: str, message: Message, corr_id: Optional[str] = None) -> None:
        """Publish a message with routing_key to the associated destination exchange."""
        self.publisher.publish(routing_key, message, corr_id)

    def publish_rpc_message(self, routing_key: str, message: Message, timeout: int = 10) -> Any:
        """Publish a message with routing_key and correlation id to the associated destination exchange,
        and receive response of matching correlation id (blocking)."""
        corr_id = str(uuid.uuid4())
        response_event = threading.Event()
        self.consumer.set_event_response(corr_id, response_event, None)
        self.publisher.publish(routing_key, message, corr_id)
        logger.info(f"RPC message sent to publish queue with corr_id: {corr_id}")

        # Wait for the response or timeout
        event_triggered = response_event.wait(timeout=timeout)

        response = None
        if event_triggered:
            # Response received before timeout
            item = self.consumer.get_event_response(corr_id)
            response = item["response"]

        # Cleanup, even if timeout
        self.consumer.del_event_response(corr_id)

        return response
