"""
Abstract base class for MessageNode, which represents an entity that consumes and publishes data. This naturally includes clients and controllers.

Design choice: All command responses are published as telemetry. If command producer requires a response, they are to include a correlation_id in
the message properties.
"""

import queue
from abc import ABC, abstractmethod
import json
import logging
import threading
import uuid

import pika
from pika import BlockingConnection
from pika.channel import Channel

from hamilton.base.config import MessageNodeConfig
from hamilton.base.message_generate import MessageGenerator
from hamilton.common.utils import CustomJSONDecoder, CustomJSONEncoder

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class IMessageNodeOperations(ABC):
    """Defines MessageNode interfacing operations"""

    @abstractmethod
    def publish_message(self, routing_key: str, message: dict) -> None:
        pass

    @abstractmethod
    def publish_rpc_message(self, routing_key: str, message: dict) -> dict:
        pass

    @property
    @abstractmethod
    def msg_generator(self) -> MessageGenerator:
        pass


class MessageHandler(ABC):
    def __init__(self, message_type: str = "", serve_as_rpc: bool = False):
        self.message_type = message_type
        self.node_operations: IMessageNodeOperations = None

    def set_node_operations(self, node_operations: IMessageNodeOperations):
        self.node_operations = node_operations

    @abstractmethod
    def handle_message(self, ch, method, properties: pika.BasicProperties, body):
        """Process the received message."""
        pass


class Consumer(threading.Thread):
    def __init__(self, config: MessageNodeConfig, handlers: list[MessageHandler]):
        super().__init__()
        self.config = config
        self.shutdown_event = threading.Event()
        self.responses = {}
        self.responses_lock = threading.Lock()
        self.handlers_map: dict[str, MessageHandler] = self.build_handlers_map(handlers)
        self.connection: BlockingConnection = None
        self.channel: Channel = None

    def run(self):
        try:
            self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.config.rabbitmq_server))
            self.channel = self.connection.channel()
            self.declare_exchanges()
            self.setup_bindings()

            while not self.shutdown_event.is_set():
                self.connection.process_data_events(time_limit=0)  # Check for shutdown flag

            # self.channel.start_consuming()
        except Exception as e:
            logging.error(f"An error occurred in the Consumer: {e}")

        self.channel.stop_consuming()
        self.channel.close()
        self.connection.close()

    def on_message_received(self, ch, method, properties, body):
        if self.shutdown_event.is_set():
            self.channel.stop_consuming()

        message = json.loads(body, cls=CustomJSONDecoder)
        message_type = message.get("messageType")
        logging.info(f"Receieved message of type {message_type} and body {message}")

        # Extract and handle the correlation_id for RPC responses
        corr_id = properties.correlation_id
        event = None
        if corr_id:
            item = self.get_event_response(corr_id)
            if item:
                event = item["event"]
                event.set()
                #self.set_event_response(corr_id, event, message)

        # Pass message to registered handlers
        handlers = self.handlers_map.get(message_type, [])
        if handlers:
            for handler in handlers:
                response = handler.handle_message(ch, method, properties, body)
                if event:
                    self.set_event_response(corr_id, event, response)
        else:
            logging.warning(f"No handlers found for message type: {message_type}")

    def declare_exchanges(self):
        for exchange in self.config.exchanges:
            try:
                if self.channel:
                    self.channel.exchange_declare(
                        exchange=exchange.name,
                        exchange_type=exchange.type,
                        durable=exchange.durable,
                        auto_delete=exchange.auto_delete,
                    )
                logging.info("Exchanges imported and configured successfully.")
            except Exception as e:
                logging.error(f"Failed to declare exchange '{exchange.name}': {e}")

    def setup_bindings(self):
        for binding in self.config.bindings:
            queue_name = f"{binding.exchange}_{self.config.name}"
            try:
                self.channel.queue_declare(queue=queue_name)
                for routing_key in binding.routing_keys:
                    self.channel.queue_bind(exchange=binding.exchange, queue=queue_name, routing_key=routing_key)
                consumer_tag = self.channel.basic_consume(
                    queue=queue_name, on_message_callback=self.on_message_received, auto_ack=True
                )
                logging.info(
                    f"Bindings for queue '{queue_name}' with consumer tag '{consumer_tag}' configured successfully."
                )
            except Exception as e:
                logging.error(f"Failed to setup bindings for queue '{queue_name}': {e}")

    def build_handlers_map(self, handlers) -> dict[str, MessageHandler]:
        """Organizes handlers by message type, allowing multiple handlers per type."""
        handler_map = {}
        for handler in handlers:
            handler_map.setdefault(handler.message_type, []).append(handler)
        return handler_map

    def get_event_response(self, corr_id) -> dict:
        """Retrieve event-response pair based on its correlation ID in a thread-safe manner."""
        with self.responses_lock:
            return self.responses.get(corr_id)

    def set_event_response(self, corr_id, event: threading.Event, response=None) -> None:
        """Set an event-response pair based on its correlation ID in a thread-safe manner."""
        with self.responses_lock:
            self.responses[corr_id] = {"event": event, "response": response}

    def del_event_response(self, corr_id) -> None:
        """Delete an event-response based on its correlation ID in a thread-safe manner."""
        with self.responses_lock:
            if corr_id in self.responses:
                del self.responses[corr_id]

    def stop(self):
        self.shutdown_event.set()


class Publisher(threading.Thread):
    def __init__(self, config: MessageNodeConfig):
        super().__init__()
        self.config = config
        self.publish_hashmap = {}
        self.publish_queue = queue.Queue()
        self.shutdown_event = threading.Event()
        self.build_publish_hashmap()
        self.connection: BlockingConnection = None
        self.channel: Channel = None

    def run(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.config.rabbitmq_server))
        self.channel = self.connection.channel()
        self.declare_exchanges()

        while not self.shutdown_event.is_set():
            # Block until an item is available. This is effectively event-driven.
            item = self.publish_queue.get()
            if item is None:
                # Shutdown signal received, exit the loop
                logging.info("Shutdown signal received in `publish_queue`, stopping publisher.")
                break

            exchange, routing_key, properties, body = item
            try:
                self.channel.basic_publish(
                    exchange=exchange,
                    routing_key=routing_key,
                    properties=properties,
                    body=body,
                )
                logging.info(f"Message published to exchange '{exchange}' with routing key '{routing_key}'.")
            except Exception as e:
                logging.error(
                    f"Failed to publish message to exchange '{exchange}' with routing key '{routing_key}': {e}"
                )
            finally:
                self.publish_queue.task_done()

        self.channel.close()
        self.connection.close()

    def publish(self, routing_key, message, corr_id=None):
        publishing = self.publish_hashmap.get(routing_key)
        properties = pika.BasicProperties(correlation_id=corr_id)
        body = json.dumps(message, cls=CustomJSONEncoder)
        if not publishing:
            logging.error(f"No publishing configuration found for routing key '{routing_key}'. Message not sent.")
            return
        self.publish_queue.put((publishing.exchange, routing_key, properties, body))

    def declare_exchanges(self):
        for exchange in self.config.exchanges:
            try:
                if self.channel:
                    self.channel.exchange_declare(
                        exchange=exchange.name,
                        exchange_type=exchange.type,
                        durable=exchange.durable,
                        auto_delete=exchange.auto_delete,
                    )
                logging.info("Exchanges imported and configured successfully.")
            except Exception as e:
                logging.error(f"Failed to declare exchange '{exchange.name}': {e}")

    def build_publish_hashmap(self):
        """Builds a hashmap of routing keys to Publishing objects for quick lookup."""
        for publishing in self.config.publishings:
            for routing_key in publishing.routing_keys:
                self.publish_hashmap[routing_key] = publishing
        logging.info("Publishing map built successfully.")

    def stop(self):
        self.shutdown_event.set()
        self.publish_queue.put(None)  # Unblock the `get()` in `publish_queue`


class MessageNode(IMessageNodeOperations):

    def __init__(self, config: MessageNodeConfig, handlers: list[MessageHandler] = []):
        self.config = config
        self._msg_generator = MessageGenerator(config.name, config.message_version)
        for handler in handlers:
            handler.set_node_operations(self)
        self.consumer = Consumer(config, handlers)
        self.publisher = Publisher(config)

    @property
    def msg_generator(self) -> MessageGenerator:
        return self._msg_generator

    @msg_generator.setter
    def msg_generator(self, value: MessageGenerator):
        self._msg_generator = value

    def signal_handler(self, signum, frame):
        logging.info("SIGINT received, initiating shutdown...")
        self.stop()

    def start(self):
        #signal.signal(signal.SIGINT, self.signal_handler)
        logging.info(f"Starting {self.config.name}...")
        logging.info(f"Starting Consumer..")
        self.consumer.start()
        logging.info(f"Starting Publisher..")
        self.publisher.start()

    def stop(self):
        try:
            logging.info("Stopping Consumer...")
            self.consumer.stop()
            self.consumer.join()
            logging.info("Stopping Publisher...")
            self.publisher.stop()
            self.publisher.join()
        except Exception as e:
            logging.error(f"An error occurred during shutdown: {e}")
        finally:
            logging.info(f"{self.config.name} shutdown complete.")

    def publish_message(self, routing_key: str, message, corr_id=None):
        """Publish a message with routing_key to the destination exchange."""
        self.publisher.publish(routing_key, message, corr_id)

    def publish_rpc_message(self, routing_key: str, message, timeout=10):
        """Publish a message with routing_key to the destination exchange, and receive response of matching correlation id (blocking)."""
        corr_id = str(uuid.uuid4())
        response_event = threading.Event()
        self.consumer.set_event_response(corr_id, response_event, None)
        self.publisher.publish(routing_key, message, corr_id)
        logging.info(f"RPC message sent to publish queue with corr_id: {corr_id}")

        # Wait for the response or timeout
        event_triggered = response_event.wait(timeout=timeout)

        response = None
        if event_triggered:
            # Response received before timeout
            _, response = self.consumer.get_event_response(corr_id)

        # Cleanup, even if timeout
        self.consumer.del_event_response(corr_id)

        return response
