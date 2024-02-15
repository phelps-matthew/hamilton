from hamilton.base.client import BaseClient
from hamilton.devices.sdr.config import Config


class SDRClient(BaseClient):
    def __init__(self, config: Config = Config()):
        super().__init__(config)
        self.config = config


if __name__ == "__main__":
    import time
    client = SDRClient()

    command = "start_record"
    parameters = {"freq": 144e6}
    response = client.send_command(command, parameters)
    print(response)
    
    time.sleep(10)

    command = "stop_record"
    parameters = {}
    response = client.send_command(command, parameters)
    print(response)

    command = "start_record"
    parameters = {"freq": 433e6}
    response = client.send_command(command, parameters)
    print(response)
    
    time.sleep(10)

    command = "stop_record"
    parameters = {}
    response = client.send_command(command, parameters)
    print(response)