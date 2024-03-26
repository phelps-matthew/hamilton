from typing import Any, Optional
from hamilton.base.config import MessageNodeConfig
from hamilton.base.messages import Message, MessageGenerator
from hamilton.message_node.async_message_node import AsyncMessageNode
from hamilton.message_node.interfaces import MessageHandler


class AsyncMessageNodeOperator:
    """
    A base class to operate on AsyncMessageNode. Subclassed by clients and controllers, for example.

    Attributes
    ----------
    config : MessageNodeConfig
        The configuration for the message node.
    handlers : list[MessageHandler]
        The list of message handlers.
    verbosity : int, optional
        The verbosity level, defaults to 3.

    Methods
    -------
    start()
        Start the message node asynchronously.
    stop()
        Stop the message node asynchronously.
    publish_message(routing_key: str, message: Message, corr_id: Optional[str] = None)
        Publish a message to the message node asynchronously.
    publish_rpc_message(routing_key: str, message: Message, timeout: int = 10) -> Any
        Publish a RPC message to the message node asynchronously and wait for the response.
    """

    def __init__(self, config: MessageNodeConfig, handlers: list[MessageHandler], verbosity: int = 3):
        self.node = AsyncMessageNode(config, handlers, verbosity)
        self.config = config

    async def start(self) -> None:
        """Start the message node asynchronously."""
        await self.node.start()

    async def stop(self) -> None:
        """Stop the message node asynchronously."""
        await self.node.stop()

    async def publish_message(self, routing_key: str, message: Message, corr_id: Optional[str] = None) -> None:
        """Publish a message to the message node asynchronously."""
        return await self.node.publish_message(routing_key, message, corr_id)

    async def publish_rpc_message(self, routing_key: str, message: Message, timeout: int = 10) -> Any:
        """Publish a RPC message to the message node asynchronously and wait for the response."""
        return await self.node.publish_rpc_message(routing_key, message, timeout)

    @property
    def msg_generator(self) -> MessageGenerator:
        """Provides direct access to the message generator."""
        return self.node.msg_generator
