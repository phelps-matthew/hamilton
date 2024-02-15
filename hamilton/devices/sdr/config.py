from hamilton.base.config import GlobalConfig


class Config(GlobalConfig):
    COMMAND_QUEUE = "sdr_commands"
    STATUS_QUEUE = "sdr_status"