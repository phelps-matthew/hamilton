from hamilton.base.config import MessageNodeConfig, Exchange, Binding, Publishing


class RelayControllerConfig(MessageNodeConfig):
    name = "RelayController"
    exchanges = [
        Exchange(name="relay", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="relay", routing_keys=["observatory.device.relay.command.*"]),
    ]
    publishings = [
        Publishing(exchange="relay", routing_keys=["observatory.device.relay.telemetry.status"]),
    ]

    DEVICE_ID = "AB0OQ0PW"


class RelayClientConfig(MessageNodeConfig):
    name = "RelayClient"
    exchanges = [
        Exchange(name="relay", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="relay", routing_keys=["observatory.device.relay.telemetry.#"]),
    ]
    publishings = [
        Publishing(
            exchange="relay",
            rpc=True,
            routing_keys=[
                "observatory.device.relay.command.set",
                "observatory.device.relay.command.status",
            ],
        ),
    ]
