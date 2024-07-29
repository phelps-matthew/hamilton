from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler
from hamilton.base.messages import Message, MessageHandlerType
from hamilton.operators.sdr.flowgraphs.rmq.config import RMQControllerConfig
from typing import Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


class RMQMessageHandler(MessageHandler):
    def __init__(self, message_node_source):
        super().__init__(message_type=MessageHandlerType.COMMAND)
        self.message_node_source = message_node_source

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None) -> None:
        parameters = message["payload"]["parameters"]
        await self.message_node_source.process_message(parameters)


class RMQController(AsyncMessageNodeOperator):
    def __init__(self, message_node_source):
        handlers = [RMQMessageHandler(message_node_source)]
        self.config = RMQControllerConfig()
        super().__init__(self.config, handlers)
        message_node_source.set_controller(self)

    #async def start(self):
    #    logger.info("Starting RMQController")
    #    try:
    #        await super().start()
    #        logger.info("RMQController started successfully")
    #    except Exception as e:
    #        logger.error(f"Error starting RMQController: {e}")
    #        raise

    #async def stop(self):
    #    logger.info("Stopping RMQController")
    #    try:
    #        await super().stop()
    #        logger.info("RMQController stopped successfully")
    #    except asyncio.CancelledError:
    #        logger.info("RMQController stop operation was cancelled")
    #    except Exception as e:
    #        logger.error(f"Error stopping RMQController: {e}")
    #        raise