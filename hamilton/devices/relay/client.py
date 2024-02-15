from hamilton.base.client import BaseClient
from hamilton.devices.relay.config import Config


class RelayClient(BaseClient):
    def __init__(self, config: Config = Config()):
        super().__init__(config)
        self.config = config


if __name__ == "__main__":
    client = RelayClient(config=Config)

    command = "status"
    parameters = {}
    response = client.send_command(command, parameters)
    print(response)

    command = "set"
    parameters = {"id": "uhf_bias", "state": "on"}
    response = client.send_command(command, parameters)
    print(response)
