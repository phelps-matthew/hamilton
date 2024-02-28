import json
import pika
import uuid
import logging
import abc
from hamilton.base.config import MessageNodeConfig

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MessageNode(abc):

    def __init__(self, config: MessageNodeConfig):
        self.config = config
        self.publishing_map = {}  # Hashmap of routing keys to Publishing objects
        try:
            self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=config.rabbitmq_server))
            self.channel = self.connection.channel()
            self.setup_exchanges()
            self.setup_bindings()
            self.setup_publishings()
        except pika.exceptions.AMQPConnectionError as e:
            logging.error(f"Failed to connect to RabbitMQ server: {e}")
            raise
        except Exception as e:
            logging.error(f"An unexpected error occurred during MessageNode initialization: {e}")
            raise

    def setup_exchanges(self):
        for exchange in self.config.exchanges:
            try:
                self.channel.exchange_declare(
                    exchange=exchange.name,
                    exchange_type=exchange.type,
                    durable=exchange.durable,
                    auto_delete=exchange.auto_delete,
                )
            except Exception as e:
                logging.error(f"Failed to declare exchange '{exchange.name}': {e}")

    def setup_bindings(self):
        for binding in self.config.bindings:
            queue_name = f"{binding.exchange}_{self.config.name}"
            try:
                self.channel.queue_declare(queue=queue_name)
                for routing_key in binding.routing_keys:
                    self.channel.queue_bind(exchange=binding.exchange, queue=queue_name, routing_key=routing_key)
                self.channel.basic_consume(
                    queue=queue_name, on_message_callback=self.on_message_received, auto_ack=True
                )
            except Exception as e:
                logging.error(f"Failed to setup bindings for queue '{queue_name}': {e}")

    def setup_publishings(self):
        """Builds a hashmap of routing keys to Publishing objects for quick lookup."""
        for publishing in self.config.publishings:
            for routing_key in publishing.routing_keys:
                self.publishing_map[routing_key] = publishing
        logging.info("Publishing map built successfully.")

    def publish_message(self, routing_key, message):
        """Publish a message using the routing key to find the corresponding Publishing object."""
        publishing = self.publishing_map.get(routing_key)

        if not publishing:
            logging.error(f"No publishing configuration found for routing key '{routing_key}'. Message not sent.")
            return

        try:
            if publishing.rpc:
                result = self.channel.queue_declare(queue="", exclusive=True)
                callback_queue = result.method.queue
                corr_id = str(uuid.uuid4())
                self.channel.basic_publish(
                    exchange=publishing.exchange,
                    routing_key=routing_key,
                    properties=pika.BasicProperties(reply_to=callback_queue, correlation_id=corr_id),
                    body=json.dumps(message),
                )
                logging.info(
                    f"RPC message published to exchange '{publishing.exchange}' with routing key '{routing_key}'. Waiting for response..."
                )
            else:
                self.channel.basic_publish(
                    exchange=publishing.exchange, routing_key=routing_key, body=json.dumps(message)
                )
                logging.info(f"Message published to exchange '{publishing.exchange}' with routing key '{routing_key}'.")
        except Exception as e:
            logging.error(f"Failed to publish message with routing key '{routing_key}': {e}")

    @abc.abstractmethod
    def on_message_received(self, ch, method, properties, body):
        """Process incoming messages. Must be implemented by subclasses."""
        pass
