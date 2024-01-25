import json
import pika
from threading import Lock


class DBQueryService:
    def __init__(self, config):
        self.config = config
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(config.RABBITMQ_SERVER))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=config.DB_QUERY_QUEUE)
        self.channel.queue_declare(queue=config.LOGGING_QUEUE)
        self.db_lock = Lock()  # For thread-safe file access

    def log_message(self, level, message):
        log_entry = {"service_name": "DBQueryService", "level": level, "message": message}
        self.channel.basic_publish(exchange="", routing_key=self.config.LOGGING_QUEUE, body=json.dumps(log_entry))

    def load_data(self, key):
        with self.db_lock:
            with open(self.config.DATABASE_PATH, "r") as file:
                data = json.load(file)
                return data.get(key, {})

    def on_request(self, ch, method, properties, body):
        key = body.decode()
        self.log_message("INFO", f"Received query for key: {key}")

        response_data = self.load_data(key)
        response_body = json.dumps(response_data)

        ch.basic_publish(
            exchange="",
            routing_key=properties.reply_to,
            properties=pika.BasicProperties(correlation_id=properties.correlation_id),
            body=response_body,
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)

    def start(self):
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue=self.config.DB_QUERY_QUEUE, on_message_callback=self.on_request)
        self.log_message("INFO", "Awaiting RPC requests for database queries")
        self.channel.start_consuming()


if __name__ == "__main__":
    from hamilton.database.config import Config

    query_service = DBQueryService(Config)
    query_service.start()
