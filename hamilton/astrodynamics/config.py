from hamilton.base.config import GlobalConfig


class Config(GlobalConfig):
    # Queues
    COMMAND_QUEUE = "astrodynamics_commands"
    STATUS_QUEUE = "astrodynamics_status"

    # RME
    LATTITUDE = 20.7464000000
    LONGITUDE = -156.4314700000
    ALTITUDE = 103.8000000000  # (meters)

    # Constraints
    MIN_ELEVATION = 10  # (degrees)
