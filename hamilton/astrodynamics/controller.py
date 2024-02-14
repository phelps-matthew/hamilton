from hamilton.base.controller import BaseController
from hamilton.astrodynamics.config import Config
from hamilton.astrodynamics.api import SpaceObjectTracker


class AstrodynamicsController(BaseController):
    def __init__(self, config: Config, so_tracker: SpaceObjectTracker):
        super().__init__(config)
        self.config = config
        self.so_tracker = so_tracker

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


if __name__ == "__main__":
    so_tracker = SpaceObjectTracker(config=Config)
    controller = AstrodynamicsController(config=Config, so_tracker=so_tracker)
    controller.start()
