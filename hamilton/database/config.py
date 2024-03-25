from hamilton.base.config import GlobalConfig


class DBUpdateConfig(GlobalConfig):
    UPDATE_INTERVAL = 3600  # Update every hour

    SATNOGS_TRANSMITTERS_URL = "https://db.satnogs.org/api/transmitters/?format=json"
    SATNOGS_SATELLITES_URL = "https://db.satnogs.org/api/satellites/?format=json"
    SATNOGS_TLE_URL = "https://db.satnogs.org/api/tle/?format=json"
    JE9PEL_URL = "http://www.ne.jp/asahi/hamradio/je9pel/satslist.csv"


from hamilton.base.config import MessageNodeConfig, Exchange, Binding, Publishing


class DBQueryConfig(MessageNodeConfig):
    name = "database_query"
    exchanges = [
        Exchange(name="database", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="database", routing_keys=["observatory.database.command.*"]),
    ]
    publishings = [
        Publishing(exchange="database", routing_keys=["observatory.database.telemetry.query_record"]),
        Publishing(exchange="database", routing_keys=["observatory.database.telemetry.get_satellite_ids"]),
        Publishing(
            exchange="database", routing_keys=["observatory.database.telemetry.get_active_downlink_satellite_ids"]
        ),
    ]
    DB_PATH = "./satcom.json"