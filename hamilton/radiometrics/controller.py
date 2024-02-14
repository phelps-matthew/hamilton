from hamilton.base.controller import BaseController
from hamilton.radiometrics.config import Config
from hamilton.radiometrics.api import Radiometrics


class RadiometricsController(BaseController):
    def __init__(self, config: Config, radiometrics: Radiometrics):
        super().__init__(config)
        self.config = config
        self.radiometrics = radiometrics

    def process_command(self, command: str, parameters: str):
        response = None
        if command == "get_tx_profile":
            sat_id = parameters.get("sat_id")
            response = self.radiometrics.get_tx_profile(sat_id)
        elif command == "get_downlink_freqs":
            sat_id = parameters.get("sat_id")
            response = self.radiometrics.get_downlink_freqs(sat_id)

        return response


if __name__ == "__main__":
    radiometrics = Radiometrics(config=Config)
    controller = RadiometricsController(config=Config, radiometrics=radiometrics)
    controller.start()