from hamilton.base.config import MessageNodeConfig, Exchange, Binding, Publishing
from pathlib import Path


class SensorCapsuleControllerConfig(MessageNodeConfig):
    name = "SensorCapsuleController"
    exchanges = [
        Exchange(name="sensor_capsule", type="topic", durable=True, auto_delete=False),
        Exchange(name="scheduler", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(
            exchange="sensor_capsule",
            routing_keys=["observatory.sensor_capsule.command.*"],
        ),
    ]
    publishings = [
        Publishing(
            exchange="scheduler", rpc=False, routing_keys=["observatory.scheduler.telemetry.status"]
        ),
    ]

    bolt_ip: str = "localhost"
    bolt_port: int = 8080
    bolt_route: str = "/bolt/collectrequest"
    bolt_poll_interval: int = 60  # seconds
    spout_ip: str = "localhost"
    spout_port: int = 8081
    spout_route: str = "/spout/json"
    key: Path = Path("~/hamilton/sensor-capsule/certs/key.pem")
    cert: Path = Path("~/hamilton/sensor-capsule/certs/cert.pem")


class SensorCapsuleClientConfig(MessageNodeConfig):
    name = "SensorCapsuleClient"
    exchanges = [
        Exchange(name="sensor_capsule", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="sensor_capsule", routing_keys=["observatory.sensor_capsule.telemetry.#"]),
    ]
    publishings = [
        Publishing(
            exchange="sensor_capsule",
            rpc=True,
            routing_keys=[
                "observatory.sensor_capsule.command.post_collect_response",
                "observatory.sensor_capsule.command.status",
            ],
        ),
    ]