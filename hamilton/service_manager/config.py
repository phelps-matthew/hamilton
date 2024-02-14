from hamilton.base.config import GlobalConfig


class Config(GlobalConfig):
    STATUS_QUEUE = "service_status_queue"
    COMMAND_QUEUE = "service_command_queue"

    # Service Manager Configuration
    SERVICES = [
        "hamilton-log-collector",
        "hamilton-mount-controller",
        "hamilton-service-manager",
        "hamilton-database-update",
        "hamilton-database-query",
        "hamilton-astrodynamics",
        "hamilton-radiometrics",
    ]

    STATUS_UPDATE_INTERVAL = 60  # Time interval (in seconds) for sending status updates
