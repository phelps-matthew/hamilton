from typing import TypedDict, Union, Dict, Any
from datetime import datetime, UTC
from enum import Enum


class TaskType(Enum):
    LEO_TRACK = "leo_track"


class TaskParameters(TypedDict):
    sat_id: str
    aos: dict[str, Any]
    tca: dict[str, Any]
    los: dict[str, Any]
    sdr: dict[str, Any]
    interpolated_orbit: dict[str, list[float, datetime]]


class Task(TypedDict):
    source: str
    timestamp: str
    task_id: str
    task_type: TaskType
    parameters: TaskParameters


class TaskGenerator:
    @staticmethod
    def generate_task(sat_id: str) -> Task:
        task = {
            "source": "hamilton",
            "timestamp": datetime.now().isoformat(),
            "task_id": str(uuid.uuid4()),
            "task_type": "leo_track",
            "parameters": None,
        }




