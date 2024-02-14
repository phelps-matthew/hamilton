from hamilton.base.config import GlobalConfig


class Config(GlobalConfig):
    COMMAND_QUEUE = "radiometrics_commands"
    STATUS_QUEUE = "radiometrics_status"
