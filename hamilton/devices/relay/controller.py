from hamilton.base.controller import BaseController
from hamilton.devices.relay.api import FTDIBitbangRelay
from hamilton.devices.relay.config import Config


class RelayController(BaseController):
    def __init__(self, config: Config, relay_driver: FTDIBitbangRelay):
        super().__init__(config)
        self.config = config
        self.relay = relay_driver
        self.id_map = {"uhf_bias": 1, "vhf_bias": 2, "vhf_pol": 3, "uhf_pol": 4}

    def parse_state_to_dict(self, state):
        relay_names = ["uhf_bias", "vhf_bias", "vhf_pol", "uhf_pol"]
        state_dict = {}
        for i, name in enumerate(relay_names):
            # Shift the state right by i places and check the least significant bit
            state_dict[name] = "on" if state & (1 << i) else "off"
        return state_dict

    def process_command(self, command: str, parameters: str):
        response = None
        if command == "set":
            id = parameters.get("id")
            state = parameters.get("state")
            if state not in ["on", "off"]:
                self.log_message("INFO", f"{state} not in [on, off]")
                return response
            if id not in self.id_map:
                self.log_message("INFO", f"{id} not in {list(self.id_map.keys())}")
                return response
            else:
                response = self.relay.set_relay(relay_num=self.id_map[id], state=state)
        elif command == "status":
            raw_response = self.relay.get_relay_state()
            response = self.parse_state_to_dict(raw_response)

        return response


if __name__ == "__main__":
    relay_driver = FTDIBitbangRelay(device_id=Config.DEVICE_ID, verbosity=2)
    controller = RelayController(config=Config, relay_driver=relay_driver)
    controller.start()
