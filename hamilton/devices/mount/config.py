class Config:
    RABBITMQ_SERVER = 'localhost'
    # ... other configurations ...
    LOGGING_QUEUE = 'logging_queue'  # Name of the logging queue
    COMMAND_QUEUE = "mount_commands"
    STATUS_QUEUE = "mount_status"

    DEVICE_ADDRESS = "/dev/usbttymd01"
