from hamilton.base.config import MessageNodeConfig, Exchange, Binding, Publishing


class ServiceViewerControllerConfig(MessageNodeConfig):
    name = "ServiceViewerController"
    exchanges = [
        Exchange(name="service_viewer", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="service_viewer", routing_keys=["observatory.service_viewer.command.*"]),
    ]
    publishings = [
        Publishing(
            exchange="service_viewer",
            routing_keys=[
                "observatory.service_viewer.telemetry.status",
            ],
        ),
    ]
    SERVICES = [
        "hamilton-log-collector",
        "hamilton-mount-controller",
        "hamilton-service-manager",
        "hamilton-database-update",
        "hamilton-database-query",
        "hamilton-astrodynamics",
        "hamilton-radiometrics",
        "hamilton-relay-controller",
        "hamilton-sdr-controller",
    ]

    UPDATE_INTERVAL = 20 # seconds

class ServiceViewerClientConfig(MessageNodeConfig):
    name = "ServiceViewerClient"
    exchanges = [
        Exchange(name="service_viewer", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="service_viewer", routing_keys=["observatory.service_viewer.telemetry.#"]),
    ]
    publishings = [
        Publishing(
            exchange="service_viewer",
            routing_keys=[
                "observatory.service_viewer.command.status",
            ],
        ),
    ]