import json
import pika
from hamilton.radiometrics.config import Config
from hamilton.radiometrics.api import Radiometrics
from hamilton.common.utils import CustomJSONEncoder


class RadiometricsController:
    def __init__(self, config: Config, radiometrics: Radiometrics):
        self.config = config
        self.radiometrics = radiometrics

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
        log_entry = {"service_name": self.__class__.__name__, "level": level, "message": message}
        self.channel.basic_publish(
            exchange="", routing_key=self.config.LOGGING_QUEUE, body=json.dumps(log_entry, cls=CustomJSONEncoder)
        )

    def on_command_received(self, ch, method, properties, body):
        message = json.loads(body)
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

    def process_command(self, command: str, parameters: str):
        response = None
        if command == "get_tx_profile":
            sat_id = parameters.get("sat_id")
            response = self.radiometrics.get_tx_profile(sat_id)
        elif command == "get_downlink_freqs":
            sat_id = parameters.get("sat_id")
            response = self.radiometrics.get_downlink_freqs(sat_id)

        return response

    def publish_status(self, status):
        self.channel.basic_publish(
            exchange="", routing_key=self.config.STATUS_QUEUE, body=json.dumps(status, cls=CustomJSONEncoder)
        )
        self.log_message("INFO", {"Response": status})

    def start(self):
        print(f"Starting {self.__class__.__name__}...")
        self.log_message("INFO", f"Starting {self.__class__.__name__}..")
        self.channel.start_consuming()


if __name__ == "__main__":
    radiometrics = Radiometrics(config=Config)
    controller = RadiometricsController(config=Config, radiometrics=radiometrics)
    controller.start()