class Config:
    RABBITMQ_SERVER = "localhost"
    LOGGING_QUEUE = "logging_queue"
    UPDATE_INTERVAL = 3600  # Update every hour
    COMMAND_QUEUE = "db_query_commands"
    DB_PATH = "./satcom.json"

    VHF_LOW = 130e6
    VHF_HIGH = 150e6
    UHF_LOW = 410e6
    UHF_HIGH = 440e6

    SATNOGS_TRANSMITTERS_URL = "https://db.satnogs.org/api/transmitters/?format=json"
    SATNOGS_SATELLITES_URL = "https://db.satnogs.org/api/satellites/?format=json"
    SATNOGS_TLE_URL = "https://db.satnogs.org/api/tle/?format=json"
    JE9PEL_URL = "http://www.ne.jp/asahi/hamradio/je9pel/satslist.csv"
