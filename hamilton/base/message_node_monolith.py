"""
Abstract base class for MessageNode, which represents an entity that consumes and publishes data. This naturally includes clients and controllers.

Design choice: All command responses are published as telemetry. If command producer requires a response, they are to include a correlation_id in
the message properties.
"""

import abc
import json
import logging
import signal
import threading
import uuid

import pika
from pika import BlockingConnection

from hamilton.base.config import MessageNodeConfig
from hamilton.base.message_generate import MessageGenerator
from hamilton.common.utils import CustomJSONDecoder, CustomJSONEncoder

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class MessageNode(abc.ABC):

    def __init__(self, config: MessageNodeConfig):
        self.config = config
        self.msg_generator = MessageGenerator(config.name, config.message_version)
        self.connection: BlockingConnection = None
        self.publish_channel = None
        self.consume_channel = None
        self.publishing_map = {}  # Hashmap of routing keys to Publishing objects
        self.responses = {}  # Maps correlation IDs to RPC responses
        self.responses_lock = threading.Lock()  # Ensures thread-safe operations on responses
        self.consumer_thread = threading.Thread(target=self.consume_messages, daemon=False)
        self.consumer_tags = {}  # Used to gracefully stop each consumer during shutdown

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def setup_exchanges(self):
        for exchange in self.config.exchanges:
            try:
                self.publish_channel.exchange_declare(
                    exchange=exchange.name,
                    exchange_type=exchange.type,
                    durable=exchange.durable,
                    auto_delete=exchange.auto_delete,
                )
                logging.info("Exchanges imported and configured successfully.")
            except Exception as e:
                logging.error(f"Failed to declare exchange '{exchange.name}': {e}")

    def setup_publishings(self):
        """Builds a hashmap of routing keys to Publishing objects for quick lookup."""
        for publishing in self.config.publishings:
            for routing_key in publishing.routing_keys:
                self.publishing_map[routing_key] = publishing
        logging.info("Publishing map built successfully.")

    def setup_bindings(self):
        for binding in self.config.bindings:
            queue_name = f"{binding.exchange}_{self.config.name}"
            try:
                self.consume_channel.queue_declare(queue=queue_name)
                for routing_key in binding.routing_keys:
                    self.consume_channel.queue_bind(
                        exchange=binding.exchange, queue=queue_name, routing_key=routing_key
                    )
                # Save the consumer tag for each queue
                consumer_tag = self.consume_channel.basic_consume(
                    queue=queue_name, on_message_callback=self.on_message_received, auto_ack=True
                )
                if self.consumer_tags.get(queue_name) is not None:
                    logging.error(f"More than one Binding references the same exchange")
                else:
                    self.consumer_tags[queue_name] = consumer_tag
                logging.info(f"Bindings for queue '{queue_name}' with consumer tag '{consumer_tag}' configured successfully.")
            except Exception as e:
                logging.error(f"Failed to setup bindings for queue '{queue_name}': {e}")

    def connect(self):
        """Connect to RabbitMQ and set up connections, channels, exchanges, bindings, and publishings"""
        try:
            self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.config.rabbitmq_server))
            self.publish_channel = self.connection.channel()
            self.consume_channel = self.connection.channel()
            self.setup_exchanges()
            self.setup_publishings()
            self.setup_bindings()
        except pika.exceptions.AMQPConnectionError as e:
            logging.error(f"Failed to connect to RabbitMQ server: {e}")
            raise
        except Exception as e:
            logging.error(f"An unexpected error occurred during MessageNode initialization: {e}")
            raise

    def consume_messages(self):
        """
        This method is designed to be run in a separate thread (`self.consumer_thread`).
        It continuously consumes messages from the configured queues and processes them
        using the appropriate handler based on the message type or routing key.
        """
        try:
            self.consume_channel.start_consuming()
        except Exception as e:
            logging.error(f"An error occurred while consuming messages: {e}")

    def start(self):
        logging.info(f"Starting {self.config.name}...")
        self.connect()
        logging.info(f"Starting consumer thread..")
        self.consumer_thread.start()

    def close_connection(self):
        logging.info("Closing channels...")
        if self.consume_channel:
            self.consume_channel.close()
        if self.publish_channel:
            self.publish_channel.close()
        if self.connection:
            logging.info("Closing connection...")
            self.connection.close()

    def signal_handler(self, signum, frame):
        logging.info("Signal received, shutting down...")
        self.shutdown()

    def shutdown(self):
        logging.info("Initiating graceful shutdown...")
        try:
            for queue_name, consumer_tag in self.consumer_tags.items():
                if self.consume_channel:
                    logging.info(f"Cancelling consumption for queue '{queue_name}'...")
                    self.consume_channel.basic_cancel(consumer_tag)
        except Exception as e:
            logging.error(f"Error cancelling consumption: {e}")

        try:
            if self.consumer_thread.is_alive():
                logging.info("Waiting for consumer thread to finish...")
                self.consumer_thread.join()
        except Exception as e:
            logging.error(f"Error joining consumer thread: {e}")

        self.close_connection()

    def publish_message(self, routing_key: str, message, corr_id=None):
        """Publish a message with routing_key to the destination exchange."""
        publishing = self.publishing_map.get(routing_key)

        if not publishing:
            logging.error(f"No publishing configuration found for routing key '{routing_key}'. Message not sent.")
            return

        try:
            self.publish_channel.basic_publish(
                exchange=publishing.exchange,
                routing_key=routing_key,
                properties=pika.BasicProperties(correlation_id=corr_id),
                body=json.dumps(message, cls=CustomJSONEncoder),
            )
            logging.info(f"Message published to exchange '{publishing.exchange}' with routing key '{routing_key}'.")
        except Exception as e:
            logging.error(f"Failed to publish message with routing key '{routing_key}': {e}")

    def publish_rpc_message(self, routing_key: str, message, timeout=10):
        """Publish a message with routing_key to the destination exchange, and receive response of matching correlation id (blocking)."""
        publishing = self.publishing_map.get(routing_key)

        if not publishing:
            logging.error(f"No publishing configuration found for routing key '{routing_key}'. Message not sent.")
            return

        corr_id = str(uuid.uuid4())
        response_event = threading.Event()
        self.responses[corr_id] = {"event": response_event, "response": None}

        self.publish_channel.basic_publish(
            exchange=publishing.exchange,
            routing_key=routing_key,
            properties=pika.BasicProperties(correlation_id=corr_id),
            body=json.dumps(message, cls=CustomJSONEncoder),
        )
        logging.info(f"RPC message published with corr_id: {corr_id}")

        # Wait for the response or timeout
        event_triggered = response_event.wait(timeout=timeout)

        response = None
        if event_triggered:
            # Response received before timeout
            with self.responses_lock:
                response = self.responses[corr_id]["response"]

        # Cleanup
        with self.responses_lock:
            del self.responses[corr_id]

        return response

    def on_message_received(self, ch, method, properties, body):
        # Attempt to decode the message body
        try:
            message = json.loads(body, cls=CustomJSONDecoder)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to decode message: {e}")
            return

        logging.info(f"@@@@@@@@Message Received, succesfully decoded json")
        # Extract and handle the correlation_id for RPC responses
        corr_id = properties.correlation_id
        if corr_id and corr_id in self.responses:
            with self.responses_lock:
                self.responses[corr_id]["response"] = message
                self.responses[corr_id]["event"].set()
            return

        # Route message based on type or other criteria
        logging.info(f"@@@@@@MESSAGE {type(message)} {message}")
        logging.info(f"@@@@@@@@MESSAGE {message.get('messageType')}")

        message_type = message.get("messageType")
        if message_type == "command":
            self.on_command_received(ch, method, properties, body)
        elif message_type == "event":
            self.on_event_received(ch, method, properties, body)
        elif message_type == "telemetry":
            self.on_telemetry_received(ch, method, properties, body)
        else:
            logging.warning(f"Received unhandled message type: {message_type}")

    @abc.abstractmethod
    def on_command_received(self, ch, method, properties, body):
        raise NotImplementedError("Subclasses must implement this method to handle incoming messages.")

    @abc.abstractmethod
    def on_event_received(self, ch, method, properties, body):
        raise NotImplementedError("Subclasses must implement this method to handle incoming messages.")

    @abc.abstractmethod
    def on_telemetry_received(self, ch, method, properties, body):
        raise NotImplementedError("Subclasses must implement this method to handle incoming messages.")
