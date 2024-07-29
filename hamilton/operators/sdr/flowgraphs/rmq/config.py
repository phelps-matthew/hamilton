from hamilton.base.config import MessageNodeConfig, Exchange, Binding, Publishing


class RMQControllerConfig(MessageNodeConfig):
    name = "RMQController"
    exchanges = [
        Exchange(name="mount", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="mount", routing_keys=["observatory.mount.telemetry.azel"]),
    ]