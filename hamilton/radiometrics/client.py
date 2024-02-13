import json
import pika
import uuid
from hamilton.radiometrics.config import Config


class RadiometricsClient:
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

    def send_command(self, command, parameters={}):
        message = {"command": command, "parameters": parameters}
        self.response = None
        self.corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange="",
            routing_key=self.config.COMMAND_QUEUE,
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
    client = RadiometricsClient(Config)

    # Sample ids with 2x freqs, 1x freqs, 0x freqs
    sat_ids = ["25397", "39433", "57186"]

    for sat_id in sat_ids:
        command = "get_tx_profile"
        parameters = {"sat_id": sat_id}
        tx_profile = client.send_command(command, parameters)
        print(json.dumps(tx_profile, indent=4))

    for sat_id in sat_ids:
        command = "get_downlink_freqs"
        parameters = {"sat_id": sat_id}
        freqs = client.send_command(command, parameters)
        print(json.dumps(freqs, indent=4))