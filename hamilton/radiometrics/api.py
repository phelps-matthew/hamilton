"""
Form radoimetrics assocaited with space objects. 

For now this will be RF quantities like transmitter, downlink frequency,
polarization, modulation, etc.
"""

import pika
import json
import uuid

from hamilton.radiometrics.config import Config
from hamilton.common.utils import CustomJSONEncoder


class Radiometrics:
    def __init__(self, config: Config):
        self.config = config

        # DB query init
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.config.RABBITMQ_SERVER))
        self.channel = self.connection.channel()
        result = self.channel.queue_declare(queue="", exclusive=True)
        self.callback_queue = result.method.queue
        self.channel.basic_consume(queue=self.callback_queue, on_message_callback=self._db_on_response, auto_ack=True)
        self.response = None
        self.corr_id = None

    def _db_on_response(self, ch, method, properties, body):
        if self.corr_id == properties.correlation_id:
            self.response = json.loads(body)

    def _db_send_command(self, command, parameters = {}) -> dict:
        message = {"command": command, "parameters": parameters}
        self.response = None
        self.corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange="",
            routing_key=self.config.DB_COMMAND_QUEUE,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=json.dumps(message, cls=CustomJSONEncoder),
        )

        while self.response is None:
            self.connection.process_data_events()

        return self.response

    def get_tx_profile(self, sat_id:str) -> dict:
        command = "query"
        parameters = {"sat_id": sat_id}
        response = self._db_send_command(command, parameters)
        return response

    # Note: limited implementation, only uses JE9PEL downlinks for now
    def get_downlink_freqs(self, sat_id: str) -> list:
        """Return list of JE9PEL active downlink frequencies associated with satellite id"""
        downlink_freqs = []
        tx_profile = self.get_tx_profile(sat_id)
        if tx_profile["je9pel"] is not None:
            for link in tx_profile["je9pel"]["downlink"]:
                if link["active"]:
                    if link["low"] is not None:
                        downlink_freqs.append(link["low"])
                    elif link["high"] is not None:
                        downlink_freqs.append(link["high"])
        return downlink_freqs

if __name__ == "__main__":
    radiometrics = Radiometrics(Config)
    # Sample ids with 2x freqs, 1x freqs, 0x freqs
    sat_ids = ["25397", "39433", "57186"]

    for sat_id in sat_ids:
        tx_profile = radiometrics.get_tx_profile(sat_id)
        print(json.dumps(tx_profile, indent=4))

    for sat_id in sat_ids:
        freqs = radiometrics.get_downlink_freqs(sat_id)
        print(f"Downlink Frequencies for Sat ID {sat_id}: {freqs}")
