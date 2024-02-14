from hamilton.base.client import BaseClient
from hamilton.devices.mount.config import Config


class MountClient(BaseClient):
    def __init__(self, config: Config):
        super().__init__(config)
        self.config = config


if __name__ == "__main__":
    client = MountClient(config=Config)

    command = "status"
    parameters = {}
    response = client.send_command(command, parameters)
    print(response)

    command = "set"
    parameters = {"azimuth": float(270), "elevation": float(90)}
    response = client.send_command(command, parameters)
    print(response)

 