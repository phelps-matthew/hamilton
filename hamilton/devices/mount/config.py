from hamilton.base.config import GlobalConfig


class Config(GlobalConfig):
    COMMAND_QUEUE = "mount_commands"
    STATUS_QUEUE = "mount_status"

    DEVICE_ADDRESS = "/dev/usbttymd01"
