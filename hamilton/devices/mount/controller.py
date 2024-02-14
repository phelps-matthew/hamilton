from hamilton.base.controller import BaseController
from hamilton.devices.mount.config import Config
from hamilton.devices.mount.api import ROT2Prog


class MountController(BaseController):
    def __init__(self, config: Config, mount_driver: ROT2Prog):
        super().__init__(config)
        self.config = config
        self.mount = mount_driver

    def process_command(self, command: str, parameters: str):
        response = None
        if command == "set":
            az = parameters.get("azimuth")
            el = parameters.get("elevation")
            response = self.mount.set(az, el)
        elif command == "status":
            response = self.mount.status()
        elif command == "stop":
            response = self.mount.stop()

        return response


if __name__ == "__main__":
    mount_driver = ROT2Prog(Config.DEVICE_ADDRESS)
    controller = MountController(config=Config, mount_driver=mount_driver)
    controller.start()
