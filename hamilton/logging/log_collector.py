import pika
import json
import datetime
from hamilton.logging.config import Config


class LogCollector:
    def __init__(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=Config.RABBITMQ_SERVER))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=Config.LOGGING_QUEUE)

    def on_log_received(self, ch, method, properties, body):
        log_message = json.loads(body)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp} - {log_message['service_name']} - {log_message['level']} - {log_message['message']}\n"

        with open(Config.LOG_FILE, "a") as log_file:
            log_file.write(log_entry)

    def start_consuming(self):
        self.channel.basic_consume(queue=Config.LOGGING_QUEUE, on_message_callback=self.on_log_received, auto_ack=True)
        print("Starting Log Collector...")
        self.channel.start_consuming()


if __name__ == "__main__":
    collector = LogCollector()
    collector.start_consuming()
