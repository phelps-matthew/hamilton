class Config:
    rabbitmq_server = "localhost"
    db_command_queue = "db_query_commands"

    VHF_LOW = 130e6
    VHF_HIGH = 150e6
    UHF_LOW = 410e6
    UHF_HIGH = 440e6


class MessageNodeConfig(Config):
    name = "BaseService"
    exchanges = []
    bindings = []
    publishings = []


class ControllerConfig(MessageNodeConfig):
    pass


class ClientConfig(MessageNodeConfig):
    pass


class Binding:
    exchange = "base_exchange"
    routing_keys = ["base.routing.key.*"]


class Publishing:
    exchange = "base_exchange"
    rpc = True
    routing_keys = ["base.routing.key.example"]


class Exchange:
    name = "base_name"
    type = "topic"
    durable = True
    auto_delete = False


# Example


class MountControllerConfig(ControllerConfig):
    node_name = "MountController"
    exchanges = [
        Exchange(name="mount", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="mount", routing_keys=["observatory.device.mount.command.*"]),
    ]
    publishings = [
        Publishing(exchange="mount", rpc=False, routing_keys=["observatory.device.mount.telemetry.azel"]),
    ]
