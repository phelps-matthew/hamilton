import aio_pika
import json
import logging
from aio_pika import IncomingMessage
from hamilton.base.config import MessageNodeConfig
from hamilton.message_node.rpc_manager import RPCManager
from hamilton.message_node.interfaces import MessageHandler, MessageHandlerType
from hamilton.common.utils import CustomJSONDecoder


logger = logging.getLogger(__name__)


class AsyncConsumer:
    def __init__(self, config: MessageNodeConfig, rpc_manager: RPCManager, handlers: list[MessageHandler] = []):
        self.config: MessageNodeConfig = config
        self.connection: aio_pika.Connection = None
        self.channel: aio_pika.Channel = None
        self.rpc_manager: RPCManager = rpc_manager
        self.handlers = handlers
        self.handlers_map: dict[MessageHandlerType, list[MessageHandler]] = {}

    async def _connect(self):
        self.connection = await aio_pika.connect_robust(self.config.rabbitmq_server)
        self.channel = await self.connection.channel()

    async def _declare_exchanges(self):
        for exchange in self.config.exchanges:
            logger.info(f"Declaring exchange: {exchange.name}")
            await self.channel.declare_exchange(
                exchange.name,
                aio_pika.ExchangeType(exchange.type),
                durable=exchange.durable,
                auto_delete=exchange.auto_delete,
            )
            logger.debug(f"Exchange {exchange.name} declared successfully.")

    async def _setup_bindings(self):
        for binding in self.config.bindings:
            queue_name = f"{binding.exchange}_{self.config.name}"
            queue = await self.channel.declare_queue(queue_name)
            logger.info(f"Declared queue: {queue_name}")
            for routing_key in binding.routing_keys:
                await queue.bind(binding.exchange, routing_key)
                logger.debug(
                    f"Bound queue: {queue_name} to exchange: {binding.exchange} with routing key: {routing_key}"
                )

    async def start_consuming(self):
        logger.info("Starting consuming...")
        await self._connect()
        self._build_handlers_map()
        await self._declare_exchanges()
        await self._setup_bindings()
        # Setup consumer
        queue_name = f"{self.config.bindings[0].exchange}_{self.config.name}"
        queue = await self.channel.get_queue(queue_name)
        logger.debug(f"Queue {queue_name} obtained.")
        # This registers an on-going consumption task with the event loop and immediately returns
        await queue.consume(self._on_message_received)
        logger.info("Consumer setup complete.")

    async def _on_message_received(self, message: IncomingMessage):
        # Performs message acknowledgement
        async with message.process():
            message_body = json.loads(message.body.decode(), cls=CustomJSONDecoder)
            try:
                message_type = MessageHandlerType(message_body.get("messageType"))
            except ValueError:
                logger.error(f"Invalid message type: {message_body.get('messageType')}")
            handlers = self.handlers_map.get(message_type, [])
            correlation_id = message.correlation_id
            logger.debug(f"Consumer: Received message with correlation id: {correlation_id} and type: {message_type}")
        if handlers:
            for handler in handlers:
                response = await handler.handle_message(message_body, correlation_id)
                if correlation_id:
                    self.rpc_manager.handle_incoming_message(response, correlation_id)
        else:
            logger.warning(f"No handlers found for message type: {message_type}")

    def _build_handlers_map(self):
        """Organizes handlers by message type, allowing multiple handlers per type."""
        for handler in self.handlers:
            # If the handler is for 'all' message types, add it to all types except 'ALL'
            if handler.message_type == MessageHandlerType.ALL:
                for message_type in MessageHandlerType:
                    if message_type != MessageHandlerType.ALL:
                        self.handlers_map.setdefault(message_type, []).append(handler)
            else:
                # Add handler to its specific message type
                self.handlers_map.setdefault(handler.message_type, []).append(handler)

    async def stop(self):
        logger.info("Stopping consumer...")
        if self.channel:
            await self.channel.close()
        if self.connection:
            await self.connection.close()
        logger.info("Consumer stopped successfully.")
