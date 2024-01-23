class Config:
    RABBITMQ_SERVER = 'localhost'  # RabbitMQ server address
    LOGGING_QUEUE = 'logging_queue'  # RabbitMQ queue for logging messages
    LOG_FILE = './logfile.log'  # Path to the log file