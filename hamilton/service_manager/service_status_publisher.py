import subprocess
import pika
import json
import time
from hamilton.service_manager.config import Config


class ServiceStatusPublisher:
    def __init__(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=Config.RABBITMQ_SERVER))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=Config.STATUS_QUEUE)
        self.services = Config.SERVICES

    def log_message(self, level, message):
        log_entry = {"service_name": "SystemStatusPublisher", "level": level, "message": message}
        self.channel.basic_publish(exchange="", routing_key=Config.LOGGING_QUEUE, body=json.dumps(log_entry))

    def publish_status(self):
        while True:
            for service in self.services:
                status = self.get_service_status(service)
                self.channel.basic_publish(exchange="", routing_key=Config.STATUS_QUEUE, body=json.dumps(status))
            time.sleep(Config.STATUS_UPDATE_INTERVAL)

    def get_service_status(self, service_name):
        result = subprocess.run(["systemctl", "is-active", service_name], stdout=subprocess.PIPE)
        status = result.stdout.decode("utf-8").strip()
        return {"service_name": service_name, "status": status}

    def start(self):
        self.log_message("INFO", "Starting Systemd Status Publisher...")
        #print("Starting Systemd Status Publisher...")
        self.publish_status()


if __name__ == "__main__":
    status_publisher = ServiceStatusPublisher()
    status_publisher.start()
