from hamilton.base.config import MessageNodeConfig, Exchange, Binding, Publishing


class OrchestatorControllerConfig(MessageNodeConfig):
    name = "OrchestratorController"
    exchanges = [
        Exchange(name="orchestrator", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(
            exchange="orchestrator",
            routing_keys=["observatory.orchestrator.command.*"],
        ),
    ]
    publishings = [
        Publishing(exchange="orchestrator", rpc=False, routing_keys=["observatory.orchestrator.telemetry.status"]),
    ]


class OrchestratorClientConfig(MessageNodeConfig):
    name = "OrchestratorClient"
    exchanges = [
        Exchange(name="orchestrator", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="orchestrator", routing_keys=["observatory.orchestrator.telemetry.#"]),
    ]
    publishings = [
        Publishing(
            exchange="orchestrator",
            rpc=True,
            routing_keys=[
                "observatory.orchestrator.command.orchestrate",
                "observatory.orchestrator.command.stop_orchestrating",
                "observatory.orchestrator.command.status",
            ],
        ),
    ]
