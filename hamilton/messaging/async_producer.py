import asyncio
import aio_pika
import json
import logging
import uuid
import asyncio
from typing import Optional, Any
from aio_pika import ExchangeType, Message as AioPikaMessage
from hamilton.base.config import MessageNodeConfig, Publishing
from hamilton.common.utils import CustomJSONEncoder
from hamilton.base.messages import Message
from hamilton.messaging.rpc_manager import RPCManager

logger = logging.getLogger(__name__)


class AsyncProducer:
    def __init__(self, config: MessageNodeConfig, rpc_manager: RPCManager, shutdown_event: asyncio.Event):
        self.config: MessageNodeConfig = config
        self.publish_hashmap: dict[str, Publishing] = self._build_publish_hashmap()
        self.connection: aio_pika.Connection = None
        self.channel: aio_pika.Channel = None
        self.rpc_manager: RPCManager = rpc_manager
        self.shutdown_event: asyncio.Event = shutdown_event

    def _build_publish_hashmap(self) -> dict:
        """Builds a hashmap of routing keys to Publishing objects for quick lookup."""
        publish_hashmap = {}
        for publishing in self.config.publishings:
            for routing_key in publishing.routing_keys:
                publish_hashmap[routing_key] = publishing
        logger.debug("Publishing map built successfully.")
        return publish_hashmap

    async def _connect(self):
        """Establishes the RabbitMQ connection and channel and declares exchanges."""
        self.connection = await aio_pika.connect_robust(self.config.rabbitmq_server)
        self.channel = await self.connection.channel()
        await self._declare_exchanges()

    async def _declare_exchanges(self):
        """Declares necessary exchanges."""
        for exchange in self.config.exchanges:
            try:
                await self.channel.declare_exchange(
                    exchange.name,
                    ExchangeType(exchange.type),
                    durable=exchange.durable,
                    auto_delete=exchange.auto_delete,
                )
                logger.info(f"Exchange '{exchange.name}' declared successfully.")
            except Exception as e:
                logger.error(f"Failed to declare exchange '{exchange.name}': {e}")

    async def publish(self, routing_key: str, message: Message, corr_id: Optional[str] = None):
        """Publishes a message asynchronously."""
        if not self.connection or not self.channel:
            await self._connect()

        publishing = self.publish_hashmap.get(routing_key)
        if not publishing:
            logger.error(f"No publishing configuration found for routing key '{routing_key}'. Message not sent.")
            return

        exchange_name = publishing.exchange
        body = json.dumps(message, cls=CustomJSONEncoder).encode("utf-8")

        try:
            exchange = await self.channel.get_exchange(exchange_name)
            await exchange.publish(
                AioPikaMessage(body=body, content_type="application/json", correlation_id=corr_id),
                routing_key=routing_key,
            )
            logger.debug(f"Message published to exchange '{exchange}' with routing key '{routing_key}'.")
        except Exception as e:
            logger.error(f"Failed to publish message to exchange '{exchange}' with routing key '{routing_key}': {e}")

    async def publish_rpc_message(self, routing_key: str, message: dict, timeout: int = 10) -> Any:
        if not self.connection or not self.channel:
            await self._connect()
            logger.info("Connection and channel established successfully.")

        # Ensure the message generator is used to add necessary fields like correlation_id
        corr_id = str(uuid.uuid4())
        future = self.rpc_manager.create_future_for_rpc(corr_id)
        logger.debug(f"Future created for RPC with correlation id: {corr_id}")

        # Publish the message as usual
        await self.publish(routing_key, message, corr_id)
        logger.info(f"Message published to exchange with routing key: {routing_key}")

        try:
            # If shutdown event is passed in, monitor its state to abort RPC calls
            if self.shutdown_event is not None:
                # Convert the coroutine to a task
                shutdown_wait_task = asyncio.create_task(self.shutdown_event.wait())

                # Now pass the task instead of the coroutine
                done, pending = await asyncio.wait(
                    [future, shutdown_wait_task], timeout=timeout, return_when=asyncio.FIRST_COMPLETED
                )

                if future in done:
                    response = future.result()
                    logger.info("Response received successfully.")
                    return response
                elif self.shutdown_event.is_set():
                    logger.info("Shutdown event detected. Cancelling RPC call.")
                    return None
            # Else wait for the response or timeout
            else:
                response = await asyncio.wait_for(future, timeout)
                logger.info("Response received successfully.")
                return response
        except asyncio.TimeoutError:
            logger.error(f"RPC call timed out after {timeout} seconds.")
            return None
        finally:
            self.rpc_manager.cleanup(corr_id)
            logger.debug("RPC call cleanup completed.")

    async def start(self):
        logger.info("Starting the producer...")
        if not self.connection or not self.channel:
            await self._connect()

    async def stop(self):
        """Closes the connection."""
        logger.info("Stopping the publisher...")
        if self.channel:
            await self.channel.close()
        if self.connection:
            await self.connection.close()
        logger.info("Publisher stopped successfully.")
