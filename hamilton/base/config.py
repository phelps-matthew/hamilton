from dataclasses import dataclass, field


@dataclass
class Binding:
    exchange: str = "base_exchange"
    routing_keys: list = field(default_factory=lambda: ["base.routing.key.*"])


@dataclass
class Publishing:
    exchange: str = "base_exchange"
    rpc: bool = True
    routing_keys: list = field(default_factory=lambda: ["base.routing.key.example"])


@dataclass
class Exchange:
    name: str = "base_name"
    type: str = "topic"
    durable: bool = True
    auto_delete: bool = False


class Config:
    rabbitmq_server: str = "amqp://guest:guest@localhost"
    message_version: str = "1.0.0"
    VHF_LOW: float = 130e6
    VHF_HIGH: float = 150e6
    UHF_LOW: float = 410e6
    UHF_HIGH: float = 440e6


class MessageNodeConfig(Config):
    name: str = "BaseService"
    exchanges: list[Exchange] = []
    bindings: list[Binding] = []
    publishings: list[Publishing] = []
    observations_dir: str = "~/hamilton/observations"


class LogConfig(MessageNodeConfig):
    name: str = "LogService"
    root_log_dir: str = "~/hamilton/log/"
    max_log_size: int = 10 * 1024 * 1024  # 10 MB
    backup_count: int = 3

class DBConfig(MessageNodeConfig):
    root_log_dir: str = "~/hamilton/db/"
    json_db_path: str = "~/hamilton/db/satcom.json"
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "hamilton"
    mongo_collection_name: str = "satcom"