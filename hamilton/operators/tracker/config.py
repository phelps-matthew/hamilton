from hamilton.base.config import MessageNodeConfig, Exchange, Binding, Publishing


class TrackerControllerConfig(MessageNodeConfig):
    name = "TrackerController"
    exchanges = [
        Exchange(name="tracker", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="tracker", routing_keys=["observatory.tracker.command.*"]),
    ]
    publishings = [
        Publishing(exchange="tracker", rpc=False, routing_keys=["observatory.tracker.telemetry.status"]),
    ]

    slew_interval = 1 # seconds


class TrackerClientConfig(MessageNodeConfig):
    name = "TrackerClient"
    exchanges = [
        Exchange(name="tracker", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="tracker", routing_keys=["observatory.tracker.telemetry.#"]),
    ]
    publishings = [
        Publishing(
            exchange="tracker",
            rpc=True,
            routing_keys=[
                "observatory.tracker.command.start_tracking",
                "observatory.tracker.command.status",
                "observatory.tracker.command.stop_tracking",
                "observatory.tracker.command.slew_to_home",
                "observatory.tracker.command.slew_to_aos",
            ],
        ),
    ]

