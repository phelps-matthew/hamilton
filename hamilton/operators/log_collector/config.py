from hamilton.base.config import Exchange, Binding, LogConfig


class LogCollectorConfig(LogConfig):
    name = "LogCollector"
    exchanges = [
        Exchange(name="mount", type="topic", durable=True, auto_delete=False),
        Exchange(name="relay", type="topic", durable=True, auto_delete=False),
        Exchange(name="database", type="topic", durable=True, auto_delete=False),
        Exchange(name="astrodynamics", type="topic", durable=True, auto_delete=False),
        Exchange(name="sdr", type="topic", durable=True, auto_delete=False),
        Exchange(name="radiometrics", type="topic", durable=True, auto_delete=False),
        Exchange(name="service_viewer", type="topic", durable=True, auto_delete=False),
        Exchange(name="tracker", type="topic", durable=True, auto_delete=False),
        Exchange(name="orchestrator", type="topic", durable=True, auto_delete=False),
        Exchange(name="signal_processor", type="topic", durable=True, auto_delete=False),
        Exchange(name="scheduler", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="mount", routing_keys=["#"]),
        Binding(exchange="relay", routing_keys=["#"]),
        Binding(exchange="database", routing_keys=["#"]),
        Binding(exchange="astrodynamics", routing_keys=["#"]),
        Binding(exchange="sdr", routing_keys=["#"]),
        Binding(exchange="radiometrics", routing_keys=["#"]),
        Binding(exchange="service_viewer", routing_keys=["#"]),
        Binding(exchange="tracker", routing_keys=["#"]),
        Binding(exchange="orchestrator", routing_keys=["#"]),
        Binding(exchange="signal_processor", routing_keys=["#"]),
        Binding(exchange="scheduler", routing_keys=["#"]),
    ]
