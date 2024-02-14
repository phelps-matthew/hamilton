import json
from hamilton.common.utils import CustomJSONEncoder
from hamilton.base.client import BaseClient
from hamilton.astrodynamics.config import Config


class AstrodynamicsClient(BaseClient):
    def __init__(self, config: Config):
        super().__init__(config)
        self.config = config


if __name__ == "__main__":
    client = AstrodynamicsClient(Config)

    command = "get_kinematic_state"
    parameters = {"sat_id": "39446"}
    response = client.send_command(command, parameters)
    print(f"Response: {json.dumps(response, indent=4, cls=CustomJSONEncoder)}")

    command = "precompute_orbit"
    parameters = {"sat_id": "39446"}
    response = client.send_command(command, parameters)
    print(f"Response: {json.dumps(response, indent=4, cls=CustomJSONEncoder)}")
