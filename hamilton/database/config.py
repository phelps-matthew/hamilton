from hamilton.base.config import DBConfig, Exchange, Binding, Publishing


class DBUpdaterConfig(DBConfig):
    name = "database_controller"
    exchanges = [
        Exchange(name="database", type="topic", durable=True, auto_delete=False),
    ]
    publishings = (
        Publishing(
            exchange="database",
            rpc=True,
            routing_keys=[
                "observatory.database.telemetry.update",
            ],
        ),
    )
    UPDATE_INTERVAL = 3600  # Update every hour
    SATNOGS_TRANSMITTERS_URL = "https://db.satnogs.org/api/transmitters/?format=json"
    SATNOGS_SATELLITES_URL = "https://db.satnogs.org/api/satellites/?format=json"
    SATNOGS_TLE_URL = "https://db.satnogs.org/api/tle/?format=json"
    JE9PEL_URL = "http://www.ne.jp/asahi/hamradio/je9pel/satslist.csv"


class DBControllerConfig(DBConfig):
    name = "database_controller"
    exchanges = [
        Exchange(name="database", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="database", routing_keys=["observatory.database.command.*"]),
    ]
    publishings = (
        Publishing(
            exchange="database",
            rpc=True,
            routing_keys=[
                "observatory.database.telemetry.record",
                "observatory.database.telemetry.satellite_ids",
            ],
        ),
    )


class DBClientConfig(DBConfig):
    name = "database_client"
    exchanges = [
        Exchange(name="database", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="database", routing_keys=["observatory.database.telemetry.#"]),
    ]
    publishings = (
        Publishing(
            exchange="database",
            rpc=True,
            routing_keys=[
                "observatory.database.command.query_record",
                "observatory.database.command.get_satellite_ids",
                "observatory.database.command.get_active_downlink_satellite_ids",
            ],
        ),
    )
