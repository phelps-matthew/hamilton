from hamilton.base.config import MessageNodeConfig, Exchange, Binding, Publishing


class SDRControllerConfig(MessageNodeConfig):
    name = "SDRController"
    exchanges = [
        Exchange(name="sdr", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="sdr", routing_keys=["observatory.device.sdr.command.*"]),
    ]
    publishings = [
        Publishing(exchange="sdr", rpc=False, routing_keys=["observatory.device.sdr.telemetry.status"]),
    ]


class SDRClientConfig(MessageNodeConfig):
    name = "SDRClient"
    exchanges = [
        Exchange(name="sdr", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="sdr", routing_keys=["observatory.device.sdr.telemetry.#"]),
    ]
    publishings = [
        Publishing(
            exchange="sdr",
            rpc=True,
            routing_keys=[
                "observatory.device.sdr.command.status",
                "observatory.device.sdr.command.start_record",
                "observatory.device.sdr.command.stop_record",
            ],
        ),
    ]
