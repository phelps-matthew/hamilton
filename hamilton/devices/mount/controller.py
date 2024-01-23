import json
import pika
from hamilton.devices.mount.driver import ROT2Prog
from hamilton.devices.mount.config import Config


class MountController:
    def __init__(self, rabbitmq_server, command_queue, status_queue, logging_queue):
        self.mount = ROT2Prog("/dev/usbttymd01")  # Initialize the ROT2Prog instance
        self.command_queue = command_queue
        self.status_queue = status_queue
        self.logging_queue = logging_queue

        # Set up RabbitMQ connection and channel
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(rabbitmq_server))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.command_queue)

        # Subscribe to the command queue
        self.channel.basic_consume(
            queue=self.command_queue, on_message_callback=self.on_command_received, auto_ack=True
        )

    def log_message(self, level, message):
        log_entry = {"service_name": "MountController", "level": level, "message": message}
        self.channel.basic_publish(exchange="", routing_key=self.logging_queue, body=json.dumps(log_entry))

    def on_command_received(self, ch, method, properties, body):
        message = json.loads(body)
        command = message.get("command")
        parameters = message.get("parameters", {})

        self.log_message("INFO", "Received command: {}".format(body.decode()))

        # Process the command
        if command == "set":
            az = parameters.get("azimuth")
            el = parameters.get("elevation")
            self.mount.set(az, el)
        elif command == "status":
            status = self.mount.status()
            self.publish_status(status)

    def publish_status(self, status):
        self.channel.basic_publish(exchange="", routing_key=self.status_queue, body=json.dumps(status))

    def start(self):
        self.log_message("INFO", "MountController starting")
        self.channel.start_consuming()


if __name__ == "__main__":
    controller = MountController(
        rabbitmq_server=Config.RABBITMQ_SERVER,
        command_queue="mount_commands",
        status_queue="mount_status",
        logging_queue="logging_queue",
    )
    controller.start()
