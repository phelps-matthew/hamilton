"""Both db_query and db_update acquire and release locks for thread-safe file reading/writing"""

import json
import pika
from threading import Lock
from hamilton.database.config import Config


class DBQueryService:
    def __init__(self, config: Config):
        self.config = config
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(config.RABBITMQ_SERVER))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=config.DB_QUERY_COMMAND_QUEUE)
        self.channel.queue_declare(queue=config.LOGGING_QUEUE)
        self.db_lock = Lock()

        # Subscribe to the command queue
        self.channel.basic_consume(queue=self.config.DB_QUERY_COMMAND_QUEUE, on_message_callback=self.on_request)

    def log_message(self, level, message):
        log_entry = {"service_name": "DBQueryService", "level": level, "message": message}
        self.channel.basic_publish(exchange="", routing_key=self.config.LOGGING_QUEUE, body=json.dumps(log_entry))

    def load_data(self, key) -> dict:
        with self.db_lock:
            with open(self.config.DB_PATH, "r") as file:
                data = json.load(file)
                return data.get(key, {})

    def on_request(self, ch, method, properties, body):
        message = json.loads(body)
        command = message.get("command")
        parameters = message.get("parameters", {})

        self.log_message("INFO", f"Received command: {message}")

        response = None

        # Process the command
        if command == "query":
            sat_id = parameters.get("sat_id")
            response = self.load_data(sat_id)

        ch.basic_publish(
            exchange="",
            routing_key=properties.reply_to,
            properties=pika.BasicProperties(correlation_id=properties.correlation_id),
            body=json.dumps(response),
        )
        # without acknowledgement the message will be requeued
        ch.basic_ack(delivery_tag=method.delivery_tag)

    def start(self):
        print("Starting DBQueryService...")
        self.log_message("INFO", "Starting DBQueryService...")
        # self.channel.basic_qos(prefetch_count=1)
        # self.channel.basic_consume(queue=self.config.DB_QUERY_QUEUE, on_message_callback=self.on_request)
        self.log_message("INFO", "Awaiting RPC requests for database queries")
        self.channel.start_consuming()


if __name__ == "__main__":
    query_service = DBQueryService(Config)
    query_service.start()
