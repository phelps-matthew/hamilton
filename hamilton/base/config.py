class GlobalConfig:
    RABBITMQ_SERVER = "localhost"
    LOGGING_QUEUE = "logging_queue"
    COMMAND_QUEUE = "base_commands"
    STATUS_QUEUE = "base_status"
    AUTO_ACKNOWLEDGE = True

    DB_COMMAND_QUEUE = "db_query_commands"

    VHF_LOW = 130e6
    VHF_HIGH = 150e6
    UHF_LOW = 410e6
    UHF_HIGH = 440e6