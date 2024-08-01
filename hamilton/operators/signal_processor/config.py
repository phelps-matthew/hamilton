from hamilton.base.config import MessageNodeConfig, Exchange, Binding, Publishing


class SignalProcessorControllerConfig(MessageNodeConfig):
    name = "SignalProcessorController"
    exchanges = [
        Exchange(name="signal_processor", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="signal_processor", routing_keys=["observatory.signal_processor.command.*"]),
    ]
    publishings = [
        Publishing(
            exchange="signal_processor", rpc=False, routing_keys=["observatory.signal_processor.telemetry.status"]
        ),
    ]


class SignalProcessorClientConfig(MessageNodeConfig):
    name = "SignalProcessorClient"
    exchanges = [
        Exchange(name="signal_processor", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="signal_processor", routing_keys=["observatory.signal_processor.telemetry.#"]),
    ]
    publishings = [
        Publishing(
            exchange="signal_processor",
            rpc=True,
            routing_keys=[
                "observatory.signal_processor.command.generate_psds",
                "observatory.signal_processor.command.generate_spectrograms",
                "observatory.signal_processor.command.generate_panels",
            ],
        ),
    ]
