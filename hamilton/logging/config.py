from hamilton.base.config import Exchange, Binding, LogConfig


class LogCollectorConfig(LogConfig):
    name = "LogCollector"
    exchanges = [
        Exchange(name="mount", type="topic", durable=True, auto_delete=False),
        Exchange(name="relay", type="topic", durable=True, auto_delete=False),
        Exchange(name="database", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="mount", routing_keys=["#"]),
        Binding(exchange="relay", routing_keys=["#"]),
        Binding(exchange="database", routing_keys=["#"]),
    ]
