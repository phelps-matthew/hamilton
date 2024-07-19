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
        "hamilton-astrodynamics",
        "hamilton-database-update",
        "hamilton-database-query",
        "hamilton-log-collector",
        "hamilton-mount-controller",
        "hamilton-radiometrics",
        "hamilton-relay-controller",
        "hamilton-sdr-controller",
        "hamilton-service-viewer",
        "hamilton-tracker",
        "hamilton-orchestrator",
        "hamilton-signal-processor",
        "hamilton-scheduler",
        "hamilton-sensor-capsule",
    ]

    UPDATE_INTERVAL = 60 * 5 # seconds

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