class Config:
    # RabbitMQ Configuration
    RABBITMQ_SERVER = 'localhost'  # Address of the RabbitMQ server
    STATUS_QUEUE = 'services_status_queue'  # Queue name for service status messages
    LOGGING_QUEUE = 'logging_queue'  # Name of the logging queue

    # Service Manager Configuration
    SERVICES = [
        "hamilton-log-collector",
        'hamilton-mount-controller',
    ]

    STATUS_UPDATE_INTERVAL = 60  # Time interval (in seconds) for sending status updates