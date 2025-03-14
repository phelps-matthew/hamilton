import json
from loguru import logger
from typing import Optional

from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler
from hamilton.base.messages import Message, MessageHandlerType
from hamilton.common.utils import CustomJSONEncoder
from hamilton.operators.sdr.flowgraphs.rmq.config import RMQControllerConfig




class RMQMessageHandler(MessageHandler):
    def __init__(self, message_node_source, sat_id: str):
        super().__init__(message_type=MessageHandlerType.TELEMETRY)
        self.message_node_source = message_node_source
        self.sat_id = sat_id

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None) -> None:
        telemetry_type = message["payload"]["telemetryType"]
        parameters = message["payload"]["parameters"]

        if telemetry_type == "kinematic_state":
            sat_id = parameters["sat_id"]
            if sat_id != self.sat_id:
                return

        # Need to parse datetime into string for pmt message passing
        parameters_json = json.loads(json.dumps(parameters, cls=CustomJSONEncoder))
        self.message_node_source.process_message(message_key=telemetry_type, message=parameters_json)


class RMQController(AsyncMessageNodeOperator):
    def __init__(self, message_node_source, sat_id: str):
        handlers = [RMQMessageHandler(message_node_source, sat_id)]
        self.config = RMQControllerConfig()
        super().__init__(self.config, handlers)
        message_node_source.set_controller(self)