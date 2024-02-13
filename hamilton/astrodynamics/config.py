class Config:
    # Queues
    RABBITMQ_SERVER = 'localhost'
    LOGGING_QUEUE = 'logging_queue'
    COMMAND_QUEUE = "astrodynamics_commands"
    STATUS_QUEUE = "astrodynamics_status"
    DB_COMMAND_QUEUE = "db_query_commands"

    # RME
    LATTITUDE = 20.7464000000
    LONGITUDE = -156.4314700000
    ALTITUDE = 103.8000000000  # (meters)

    # Constraints
    MIN_ELEVATION = 10 # (degrees)

