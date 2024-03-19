"""
Abstract base class for MessageNode, which represents an entity that consumes and publishes data. This naturally includes clients and controllers.

Design choice: All command responses are published as telemetry. If command producer requires a response, they are to include a correlation_id in
the message properties.
"""

import abc
from concurrent.futures import Future
import json
import logging
import uuid
import asyncio
from aio_pika import connect, ExchangeType, Message
from aio_pika.robust_connection import RobustConnection
from aio_pika.robust_channel import RobustChannel

from hamilton.base.config import MessageNodeConfig
from hamilton.base.message_generate import MessageGenerator
from hamilton.common.utils import CustomJSONDecoder, CustomJSONEncoder

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class MessageNode(abc):

    def __init__(self, config: MessageNodeConfig):
        self.config = config
        self.msg_generator = MessageGenerator(config.name, config.message_version)
        self.connection: RobustConnection = None
        self.channel: RobustChannel = None
        self.publishing_map = {}  # Hashmap of routing keys to Publishing objects
        self.loop = asyncio.get_event_loop()
        self.pending_responses = {}

    async def setup_exchanges(self):
        for exchange in self.config.exchanges:
            await self.channel.declare_exchange(
                exchange=exchange.name,
                exchange_type=exchange.type,
                durable=exchange.durable,
                auto_delete=exchange.auto_delete,
            )

    async def setup_bindings(self):
        for binding in self.config.bindings:
            queue_name = f"{binding.exchange}_{self.config.name}"
            queue = await self.channel.declare_queue(queue_name)

            for routing_key in binding.routing_keys:
                await queue.bind(binding.exchange, routing_key)
                # TODO: Safer method for processing message based on routing_key
                if "command" in routing_key:
                    await queue.consume(self.on_command_received)
                elif "event" in routing_key:
                    await queue.consume(self.on_event_received)
                elif "telemetry" in routing_key:
                    await queue.consume(self.on_telemetry_received)

    def setup_publishings(self):
        """Builds a hashmap of routing keys to Publishing objects for quick lookup."""
        for publishing in self.config.publishings:
            for routing_key in publishing.routing_keys:
                self.publishing_map[routing_key] = publishing
        logging.info("Publishing map built successfully.")

    async def connect(self):
        self.connection = await connect(f"amqp://{self.config.rabbitmq_server}", loop=self.loop)
        self.channel = await self.connection.channel()
        await self.setup_exchanges()
        await self.setup_bindings()
        self.setup_publishings()

    async def publish_message(self, routing_key: str, message, response=False):
        """Publish a message with routing_key to the destination exchange, with optional of collecting of response."""
        publishing = self.publishing_map.get(routing_key)

        if not publishing:
            logging.error(f"No publishing configuration found for routing key '{routing_key}'. Message not sent.")
            return

        corr_id = str(uuid.uuid4()) if response else None
        if response:
            future = self.loop.create_future()
            self.pending_responses[corr_id] = future

        # Prepare the message
        message_body = json.dumps(message, cls=CustomJSONEncoder).encode()
        message = Message(
            body=message_body,
            content_type="application/json",
            correlation_id=corr_id,
        )

        # Get the exchange object and publish the message
        exchange = await self.channel.get_exchange(publishing.exchange)
        await exchange.publish(
            message,
            routing_key=routing_key,
        )
        logging.info(f"Message published to '{routing_key}' with correlation ID: {corr_id}")

        # Await the future for a response, if necessary
        if response:
            return await future
        return None

    async def on_command_received(self, ch, method, properties, body):
        raise NotImplementedError("Subclasses must implement this method to handle incoming messages.")

    async def on_event_received(self, ch, method, properties, body):
        raise NotImplementedError("Subclasses must implement this method to handle incoming messages.")

    async def on_telemetry_received(self, message):
        async with message.process():
            body = message.body.decode()  # Assuming body is a byte string
            properties = message.properties
            # Example: Accessing the correlation ID
            corr_id = properties.correlation_id if properties.correlation_id else None

            # Process the message body as needed
            print(f"Received telemetry: {body}")

            # If this message is a response that we're awaiting, let's resolve the future
            if corr_id and corr_id in self.pending_responses:
                self.pending_responses[corr_id].set_result(body)
                del self.pending_responses[corr_id]

    async def start(self):
        await self.connect()
        logging.info(f"Starting {self.config.name}..")
        # This will keep running the event loop and listening for messages
        await asyncio.Future()
