class Config:
    # Queues
    RABBITMQ_SERVER = 'localhost'
    LOGGING_QUEUE = 'logging_queue'
    COMMAND_QUEUE = "radiometrics_commands"
    STATUS_QUEUE = "radiometrics_status"
    DB_COMMAND_QUEUE = "db_query_commands"
    