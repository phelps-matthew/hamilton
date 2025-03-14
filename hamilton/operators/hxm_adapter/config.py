from hamilton.base.config import MessageNodeConfig, Exchange, Binding, Publishing
from pathlib import Path


class HXMAdapterControllerConfig(MessageNodeConfig):
    name = "HXMAdapterController"
    exchanges = [
        Exchange(name="hxm_adapter", type="topic", durable=True, auto_delete=False),
        Exchange(name="scheduler", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(
            exchange="hxm_adapter",
            routing_keys=["observatory.hxm_adapter.command.*"],
        ),
    ]
    publishings = [
        Publishing(
            exchange="sensor_capsule",
            routing_keys=[
                "observatory.hxm_adapter.telemetry.status",
                "observatory.hxm_adapter.telemetry.collect_request_list",
            ],
        ),
    ]

    hamilton_x_machina_ip: str = "localhost"
    hamilton_x_machina_port: int = 8003
    hamilton_x_machina_poll_interval: int = 2  # seconds


class HXMAdapterClientConfig(MessageNodeConfig):
    name = "HXMAdapterClient"
    exchanges = [
        Exchange(name="hxm_adapter", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="hxm_adapter", routing_keys=["observatory.hxm_adapter.telemetry.#"]),
    ]
    publishings = [
        Publishing(
            exchange="hxm_adapter",
            rpc=True,
            routing_keys=[
                "observatory.hxm_adapter.command.post_collect_response",
                "observatory.hxm_adapter.command.status",
                "observatory.hxm_adapter.command.generate_collect_requests",
            ],
        ),
    ]
