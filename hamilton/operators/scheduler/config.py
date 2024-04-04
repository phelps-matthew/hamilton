from hamilton.base.config import MessageNodeConfig, Exchange, Binding, Publishing


class SchedulerControllerConfig(MessageNodeConfig):
    name = "SchedulerController"
    exchanges = [
        Exchange(name="scheduler", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(
            exchange="scheduler",
            routing_keys=["observatory.scheduler.command.*"],
        ),
    ]
    publishings = [
        Publishing(exchange="scheduler", rpc=False, routing_keys=["observatory.scheduler.telemetry.status"]),
    ]


class SchedulerClientConfig(MessageNodeConfig):
    name = "SchedulerClient"
    exchanges = [
        Exchange(name="scheduler", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="scheduler", routing_keys=["observatory.scheduler.telemetry.#"]),
    ]
    publishings = [
        Publishing(
            exchange="scheduler",
            rpc=True,
            routing_keys=[
                "observatory.scheduler.command.enqueue_task",
                "observatory.scheduler.command.status",
            ],
        ),
    ]

