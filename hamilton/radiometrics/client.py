import json
from hamilton.base.client import BaseClient
from hamilton.common.utils import CustomJSONEncoder
from hamilton.radiometrics.config import Config


class RadiometricsClient(BaseClient):
    def __init__(self, config: Config):
        super().__init__(config)
        self.config = config


if __name__ == "__main__":
    client = RadiometricsClient(Config)

    # Sample ids with 2x freqs, 1x freqs, 0x freqs
    sat_ids = ["25397", "39433", "57186"]

    for sat_id in sat_ids:
        command = "get_tx_profile"
        parameters = {"sat_id": sat_id}
        tx_profile = client.send_command(command, parameters)
        print(json.dumps(tx_profile, indent=4, cls=CustomJSONEncoder))

    for sat_id in sat_ids:
        command = "get_downlink_freqs"
        parameters = {"sat_id": sat_id}
        freqs = client.send_command(command, parameters)
        print(json.dumps(tx_profile, indent=4, cls=CustomJSONEncoder))
