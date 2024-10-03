from hamilton.base.config import MessageNodeConfig, Exchange, Binding, Publishing


class MountControllerConfig(MessageNodeConfig):
    name = "MountController"
    exchanges = [
        Exchange(name="mount", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="mount", routing_keys=["observatory.mount.command.*"]),
    ]
    publishings = [
        Publishing(exchange="mount", rpc=False, routing_keys=["observatory.mount.telemetry.azel"]),
    ]

    DEVICE_ADDRESS = "/dev/usbttymd01"


class MountClientConfig(MessageNodeConfig):
    name = "MountClient"
    exchanges = [
        Exchange(name="mount", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="mount", routing_keys=["observatory.mount.telemetry.#"]),
    ]
    publishings = [
        Publishing(
            exchange="mount",
            rpc=True,
            routing_keys=[
                "observatory.mount.command.set",
                "observatory.mount.command.status",
                "observatory.mount.command.stop",
            ],
        ),
    ]
