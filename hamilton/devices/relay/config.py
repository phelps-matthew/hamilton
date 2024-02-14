from hamilton.base.config import GlobalConfig


class Config(GlobalConfig):
    COMMAND_QUEUE = "relay_commands"
    STATUS_QUEUE = "relay_status"

    DEVICE_ID = "AB0OQ0PW"
