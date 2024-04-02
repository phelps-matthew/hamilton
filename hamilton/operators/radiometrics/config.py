from hamilton.base.config import MessageNodeConfig, Exchange, Binding, Publishing


class RadiometricsControllerConfig(MessageNodeConfig):
    name = "RadiometricsController"
    exchanges = [
        Exchange(name="radiometrics", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="radiometrics", routing_keys=["observatory.radiometrics.command.*"]),
    ]
    publishings = [
        Publishing(
            exchange="radiometrics",
            rpc=False,
            routing_keys=[
                "observatory.radiometrics.telemetry.tx_profile",
                "observatory.radiometrics.telemetry.downlink_freqs",
            ],
        ),
    ]


class RadiometricsClientConfig(MessageNodeConfig):
    name = "RadiometricsClient"
    exchanges = [
        Exchange(name="radiometrics", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="radiometrics", routing_keys=["observatory.radiometrics.telemetry.#"]),
    ]
    publishings = [
        Publishing(
            exchange="radiometrics",
            rpc=True,
            routing_keys=[
                "observatory.radiometrics.command.get_tx_profile",
                "observatory.radiometrics.command.get_downlink_freqs",
            ],
        ),
    ]
