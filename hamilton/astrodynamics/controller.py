import json
import pika
from hamilton.astrodynamics.config import Config
from hamilton.astrodynamics.api import SpaceObjectTracker
from hamilton.common.utils import CustomJSONEncoder


class AstrodynamicsController:
    def __init__(self, config: Config, so_tracker: SpaceObjectTracker):
        self.config = config
        self.so_tracker = so_tracker

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
        self.publish_status(response)

        if properties.reply_to:
            self.channel.basic_publish(
                exchange="",
                routing_key=properties.reply_to,
                properties=pika.BasicProperties(correlation_id=properties.correlation_id),
                body=json.dumps(response, cls=CustomJSONEncoder),
            )

    def process_command(self, command: str, parameters: str):
        response = None
        if command == "get_kinematic_state":
            sat_id = parameters.get("sat_id")
            time = parameters.get("time", None)
            response = self.so_tracker.get_kinematic_state(sat_id, time)
        elif command == "get_kinematic_aos_los":
            sat_id = parameters.get("sat_id")
            time = parameters.get("time", None)
            response = self.so_tracker.get_aos_los(sat_id, time)
        elif command == "get_interpolated_orbit":
            sat_id = parameters.get("sat_id")
            aos = parameters.get("aos")
            los = parameters.get("los")
            response = self.so_tracker.get_interpolated_orbit(sat_id, aos, los)
        elif command == "precompute_orbit":
            sat_id = parameters.get("sat_id")
            response = self.so_tracker.precompute_orbit(sat_id)

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
    so_tracker = SpaceObjectTracker(config=Config)
    controller = AstrodynamicsController(config=Config, so_tracker=so_tracker)
    controller.start()