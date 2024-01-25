import json
import pika
from hamilton.devices.mount.driver import ROT2Prog


class MountController:
    def __init__(self, config):
        self.config = config
        self.mount = ROT2Prog(config.DEVICE_ADDRESS)  # Initialize the ROT2Prog instance

        # Set up RabbitMQ connection and channel
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(config.RABBITMQ_SERVER))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=config.COMMAND_QUEUE)
        self.channel.queue_declare(queue=config.LOGGING_QUEUE)

        # Subscribe to the command queue
        self.channel.basic_consume(
            queue=self.config.COMMAND_QUEUE, on_message_callback=self.on_command_received, auto_ack=True
        )

    def log_message(self, level, message):
        log_entry = {"service_name": "MountController", "level": level, "message": message}
        self.channel.basic_publish(exchange="", routing_key=self.config.LOGGING_QUEUE, body=json.dumps(log_entry))

    def on_command_received(self, ch, method, properties, body):
        message = json.loads(body)
        command = message.get("command")
        parameters = message.get("parameters", {})

        self.log_message("INFO", "Received command: {}".format(body.decode()))

        response = None

        # Process the command
        if command == "set":
            az = parameters.get("azimuth")
            el = parameters.get("elevation")
            response = self.mount.set(az, el)
        elif command == "status":
            response = self.mount.status()
        elif command == "stop":
            response = self.mount.stop()

        self.publish_status(response)

        # Check if 'reply_to' property is set
        # Allow sending of direct responses to clients that explicitly request it by setting the reply_to and 
        # correlation_id properties in their messages
        if properties.reply_to:
            self.channel.basic_publish(
                exchange="",
                routing_key=properties.reply_to,
                properties=pika.BasicProperties(correlation_id=properties.correlation_id),
                body=json.dumps(response),
            )

    def publish_status(self, status):
        self.channel.basic_publish(exchange="", routing_key=self.config.STATUS_QUEUE, body=json.dumps(status))
        self.log_message("INFO", f"Mount position: {status}")

    def start(self):
        print("Starting MountController...")
        self.log_message("INFO", "MountController starting")
        self.channel.start_consuming()


if __name__ == "__main__":
    from hamilton.devices.mount.config import Config

    controller = MountController(config=Config)
    controller.start()
