"""Abstract base class for controllers. config.COMMAND_QUEUE and config.STATUS_QUEUE are to implemented by the 
inherited config in the subclass."""

import json
from abc import ABC, abstractmethod
import pika
from hamilton.base.config import GlobalConfig
from hamilton.common.utils import CustomJSONEncoder, CustomJSONDecoder


class BaseController(ABC):

    def __init__(self, config: GlobalConfig):
        self.config = config

        # Set up RabbitMQ connection and channel
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(config.RABBITMQ_SERVER))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=config.COMMAND_QUEUE)
        self.channel.queue_declare(queue=config.LOGGING_QUEUE)

        # Subscribe to the command queue
        self.channel.basic_consume(
            queue=self.config.COMMAND_QUEUE, on_message_callback=self.on_command_received, auto_ack=config.AUTO_ACKNOWLEDGE
        )

    def log_message(self, level, message):
        log_entry = {"service_name": self.__class__.__name__, "level": level, "message": message}
        self.channel.basic_publish(
            exchange="", routing_key=self.config.LOGGING_QUEUE, body=json.dumps(log_entry, cls=CustomJSONEncoder)
        )

    def on_command_received(self, ch, method, properties, body):
        message = json.loads(body, cls=CustomJSONDecoder)
        command = message.get("command")
        parameters = message.get("parameters", {})

        self.log_message("INFO", "Received command: {}".format(body.decode()))
        response = self.process_command(command, parameters)

        if properties.reply_to:
            self.channel.basic_publish(
                exchange="",
                routing_key=properties.reply_to,
                properties=pika.BasicProperties(correlation_id=properties.correlation_id),
                body=json.dumps(response, cls=CustomJSONEncoder),
            )

    @abstractmethod
    def process_command(self, command: str, parameters: str):
        pass

    def publish_status(self, status):
        self.channel.basic_publish(
            exchange="", routing_key=self.config.STATUS_QUEUE, body=json.dumps(status, cls=CustomJSONEncoder)
        )
        self.log_message("INFO", {"Response": status})

    def start(self):
        print(f"Starting {self.__class__.__name__}...")
        self.log_message("INFO", f"Starting {self.__class__.__name__}..")
        self.channel.start_consuming()
