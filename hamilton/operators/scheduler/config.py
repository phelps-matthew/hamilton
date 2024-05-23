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

        Binding(
            exchange="orchestrator",
            routing_keys=["observatory.orchestrator.telemetry.status_event"],
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
                "observatory.scheduler.command.set_mode",
                "observatory.scheduler.command.status",
                "observatory.scheduler.command.stop_scheduling",
            ],
        ),
    ]

