import json
import pika
import uuid
import sys
from hamilton.database.config import Config


class DBQueryClient:
    def __init__(self, config: Config):
        self.config = config
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(config.RABBITMQ_SERVER))
        self.channel = self.connection.channel()

        self.callback_queue = self.channel.queue_declare(queue="", exclusive=True).method.queue

        self.channel.basic_consume(queue=self.callback_queue, on_message_callback=self.on_response, auto_ack=True)

        self.response = None
        self.corr_id = None

    def on_response(self, ch, method, properties, body):
        if self.corr_id == properties.correlation_id:
            self.response = body

    def query(self, key):
        message = {"command": "query", "parameters": {"sat_id": key}}
        self.response = None
        self.corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange="",
            routing_key=self.config.DB_QUERY_COMMAND_QUEUE,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=json.dumps(message),
        )
        while self.response is None:
            self.connection.process_data_events()
        return json.loads(self.response)


if __name__ == "__main__":
    from pprint import pprint

    query_client = DBQueryClient(Config)
    key = sys.argv[1] if len(sys.argv) > 1 else "default_key"
    pprint(f"Requesting data for key: {key}")
    response = query_client.query(key)
    pprint(f"Response: {response}")