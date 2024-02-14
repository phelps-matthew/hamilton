"""Abstract base class for clients associated with BaseController. config.COMMAND_QUEUE is to implemented by the 
inherited config in the subclass."""

import json
from abc import ABC
import uuid
import pika
from hamilton.base.config import GlobalConfig
from hamilton.common.utils import CustomJSONDecoder, CustomJSONEncoder


class BaseClient(ABC):
    def __init__(self, config: GlobalConfig):
        self.config = config
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(config.RABBITMQ_SERVER))
        self.channel = self.connection.channel()
        self.callback_queue = self.channel.queue_declare(queue="", exclusive=True).method.queue
        self.channel.basic_consume(
            queue=self.callback_queue, on_message_callback=self.on_response, auto_ack=config.AUTO_ACKNOWLEDGE
        )
        self.response = None
        self.corr_id = None

    def on_response(self, ch, method, properties, body):
        if self.corr_id == properties.correlation_id:
            self.response = body

    def send_command(self, command, parameters={}):
        message = {"command": command, "parameters": parameters}
        self.response = None
        self.corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange="",
            routing_key=self.config.COMMAND_QUEUE,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=json.dumps(message, cls=CustomJSONEncoder),
        )
        while self.response is None:
            self.connection.process_data_events()
        return json.loads(self.response, cls=CustomJSONDecoder)
