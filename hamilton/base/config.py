class GlobalConfig:
    RABBITMQ_SERVER = "localhost"
    LOGGING_QUEUE = "logging_queue"
    COMMAND_QUEUE = "base_commands"
    STATUS_QUEUE = "base_status"
    AUTO_ACKNOWLEDGE = True

    DB_COMMAND_QUEUE = "db_query_commands"
