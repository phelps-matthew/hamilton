from abc import ABC, abstractmethod
from typing import Any, Callable, Optional
from hamilton.base.messages import Message, MessageGenerator, MessageHandlerType
from hamilton.base.config import Config


# Surfaces what methods are available to classes that interface with MessageNode instances
class IMessageNodeOperations(ABC):
    """Defines MessageNode interfacing operations"""

    @abstractmethod
    def publish_message(self, routing_key: str, message: Message, corr_id: Optional[str] = None) -> None:
        pass

    @abstractmethod
    def publish_rpc_message(self, routing_key: str, message: Message, timeout: int = 10) -> Any:
        pass

    @property
    @abstractmethod
    def msg_generator(self) -> MessageGenerator:
        pass


# TODO: Configure default message handler for RPC responses based on `serve_as_rpc` arg
class MessageHandler(ABC):
    def __init__(self, message_type: MessageHandlerType = MessageHandlerType.ALL, serve_as_rpc: bool = False):
        self.message_type: MessageHandlerType = message_type
        self.node_operations: IMessageNodeOperations = None
        self.startup_hooks: list[Callable[[], None]] = []
        self.shutdown_hooks: list[Callable[[], None]] = []

    def set_node_operations(self, node_operations: IMessageNodeOperations) -> None:
        self.node_operations = node_operations

    @abstractmethod
    async def handle_message(self, message: dict, correlation_id: Optional[str] = None) -> Any:
        """Process the received message."""
        raise NotImplementedError
