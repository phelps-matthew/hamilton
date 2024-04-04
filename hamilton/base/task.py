from typing import TypedDict, Union, Dict
from datetime import datetime, UTC
from enum import Enum


class TaskType(Enum):
    LEO_TRACK = "leo_track"


class TaskParameters(TypedDict):
    sat_id: str
    aos: str
    los: str
    tca: str
    freq: str
    interpolated_orbit: str


class Task(TypedDict):
    source: str
    timestamp: str
    task_id: str
    task_type: TaskType
    parameters: TaskParameters


class MessageGenerator:
    def __init__(self, source: str, version: str):
        self.source = source
        self.version = version

    def _get_timestamp(self) -> str:
        return datetime.now().isoformat()

    def generate_message(self, message_type: MessageType, payload: Payload) -> Message:
        message_schema: Message = {
            "messageType": message_type,
            "timestamp": self._get_timestamp(),
            "source": self.source,
            "version": self.version,
            "payload": payload,
        }
        return message_schema

    def generate_command(self, command_type: str, parameters: Dict[str, Union[str, int, float]] = {}) -> Message:
        payload: CommandPayload = {"commandType": command_type, "parameters": parameters}
        return self.generate_message("command", payload)

    def generate_telemetry(self, telemetry_type: str, parameters: Dict[str, Union[str, int, float]] = {}) -> Message:
        payload: TelemetryPayload = {"telemetryType": telemetry_type, "parameters": parameters}
        return self.generate_message("telemetry", payload)

    def generate_response(self, response_type: str, data: Dict[str, Union[str, int, float]] = {}) -> Message:
        payload: ResponsePayload = {"responseType": response_type, "data": data}
        return self.generate_message("response", payload)
