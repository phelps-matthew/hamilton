from typing import TypedDict, Union, Dict, Any, Optional
from datetime import datetime, UTC, timezone, timedelta
from enum import Enum
from hamilton.operators.astrodynamics.client import AstrodynamicsClient
from hamilton.operators.radiometrics.client import RadiometricsClient
import logging
import uuid

logger = logging.getLogger(__name__)


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
    def __init__(self):
        try:
            self.radiometrics: RadiometricsClient = RadiometricsClient()
            self.astrodynamics: AstrodynamicsClient = AstrodynamicsClient()
        except Exception as e:
            logger.error(f"An error occurred while initializing clients: {e}")
        self.client_list = [self.radiometrics, self.astrodynamics]

    async def start(self):
        logger.info("Starting clients.")
        for client in self.client_list:
            try:
                await client.start()
            except Exception as e:
                logger.error(f"An error occurred while starting {client}: {e}")

    async def stop(self):
        logger.info("Stopping clients.")
        for client in self.client_list:
            try:
                await client.stop()
            except Exception as e:
                logger.error(f"An error occurred while stopping {client}: {e}")

    async def generate_task(self, sat_id: str) -> Optional[Task]:
        aos_los = await self.astrodynamics.get_aos_los(sat_id)
        interpolated_orbit = await self.astrodynamics.get_interpolated_orbit(sat_id)
        downlink_freqs = await self.radiometrics.get_downlink_freqs(sat_id)
        if downlink_freqs:
            freq = downlink_freqs[0]
        else:
            logger.error(f"No downlink freqs found for sat_id {sat_id}")
            return None
        task_id = str(uuid.uuid4())

        task = {
            "source": "hamilton",
            "timestamp": datetime.now().isoformat(),
            "task_id": task_id,
            "task_type": "leo_track",
            "parameters": {
                "sat_id": sat_id,
                "aos": aos_los.get("aos", None),
                "tca": aos_los.get("tca", None),
                "los": aos_los.get("los", None),
                "sdr": {"sat_id": sat_id, "freq": freq},
                "interpolated_orbit": interpolated_orbit,
            },
        }

        if self.validate_task(task):
            return task
        else:
            logger.error(f"Generated task id {task_id} for sat_id {sat_id} is invalid.")
            return None

    def validate_task(self, task: Task) -> bool:
        parameters = task["parameters"]
        if not parameters:
            return False
        try:
            aos_time = parameters["aos"]["time"]
            los_time = parameters["los"]["time"]
        except KeyError:
            return False
        current_time = datetime.now(timezone.utc)

        if (
            aos_time
            and los_time
            and aos_time < los_time
            and los_time > current_time
            and los_time - aos_time < timedelta(minutes=15)
        ):
            return True
        else:
            logger.error(f"Invalid task. aos_time: {aos_time}, los_time: {los_time}, current_time: {current_time}")
            return False
