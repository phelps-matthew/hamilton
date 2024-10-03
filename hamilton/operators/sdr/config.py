from hamilton.base.config import MessageNodeConfig, Exchange, Binding, Publishing


class SDRControllerConfig(MessageNodeConfig):
    name = "SDRController"
    exchanges = [
        Exchange(name="sdr", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="sdr", routing_keys=["observatory.sdr.command.*"]),
    ]
    publishings = [
        Publishing(exchange="sdr", rpc=False, routing_keys=["observatory.sdr.telemetry.status"]),
    ]


class SDRClientConfig(MessageNodeConfig):
    name = "SDRClient"
    exchanges = [
        Exchange(name="sdr", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="sdr", routing_keys=["observatory.sdr.telemetry.#"]),
    ]
    publishings = [
        Publishing(
            exchange="sdr",
            rpc=True,
            routing_keys=[
                "observatory.sdr.command.status",
                "observatory.sdr.command.start_record",
                "observatory.sdr.command.stop_record",
            ],
        ),
    ]
