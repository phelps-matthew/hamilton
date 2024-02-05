"""Includes ability to query server for individual status, but this may not be necessary. Bash script simpler here."""
import subprocess
import pika
import json
import time
import threading
from hamilton.service_manager.config import Config


class ServiceViewer:
    def __init__(self, config):
        self.config = config
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=config.RABBITMQ_SERVER))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=config.STATUS_QUEUE)
        self.channel.queue_declare(queue=config.COMMAND_QUEUE)
        self.services = config.SERVICES
        self.continue_running = True

        # Subscribe to the command queue
        self.channel.basic_consume(
            queue=self.config.COMMAND_QUEUE, on_message_callback=self.on_command_received, auto_ack=True
        )

    def log_message(self, level, message):
        log_entry = {"service_name": "ServiceViewer", "level": level, "message": message}
        self.channel.basic_publish(exchange="", routing_key=self.config.LOGGING_QUEUE, body=json.dumps(log_entry))

    def on_command_received(self, ch, method, properties, body):
        message = json.loads(body)
        command = message.get("command")
        parameters = message.get("parameters", {})
        self.log_message("INFO", f"Received command: {command}")

        if command == "status":
            service_name = parameters.get("service")
            if service_name:
                status = self.get_detailed_service_status(service_name)
            else:
                status = {service: self.get_detailed_service_status(service) for service in self.services}

            response = json.dumps({"status": status})
            if properties.reply_to:
                self.channel.basic_publish(
                    exchange="",
                    routing_key=properties.reply_to,
                    properties=pika.BasicProperties(correlation_id=properties.correlation_id),
                    body=response,
                )

    def publish_status(self):
        for service in self.services:
            status = self.get_service_status(service)
            self.channel.basic_publish(exchange="", routing_key=self.config.STATUS_QUEUE, body=json.dumps(status))
            self.log_message("INFO", status)

    def get_service_status(self, service_name):
        result = subprocess.run(["systemctl", "is-active", service_name], stdout=subprocess.PIPE)
        status = result.stdout.decode("utf-8").strip()
        return {"service_name": service_name, "status": status}

    def get_detailed_service_status(self, service_name):
        result = subprocess.run(
            ["sudo", "systemctl", "status", service_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return result.stdout.decode("utf-8") + result.stderr.decode("utf-8")

    def start(self):
        print("Starting Systemd Status Publisher...")
        self.log_message("INFO", "Starting Systemd Status Publisher...")

        while self.continue_running:
            self.publish_status()
            self.channel.connection.process_data_events(time_limit=self.config.STATUS_UPDATE_INTERVAL)


if __name__ == "__main__":
    service_viewer = ServiceViewer(Config)
    service_viewer.start()
