"""
1) Polls sensor-capsule/bolt for collect requests
2) Transforms bolt collect request to Task and sends to scheduler exchange (scheduler.enqueue_collect_request)
3) Exposes the sensor_capsule exchange for receiving collect responses
4) Transforms completed Tasks to collect responses, which are then sent to sensor-capsule/spout
"""

import asyncio
import json
import logging
import requests
from hamilton.base.task import Task, TaskGenerator
from hamilton.operators.scheduler.client import SchedulerClient
from hamilton.operators.sensor_capsule.config import SensorCapsuleConfig

logger = logging.getLogger(__name__)


class SensorCapsule:
    def __init__(self, config: SensorCapsuleConfig, shutdown_event: asyncio.Event = None):
        try:
            self.task_generator: TaskGenerator = TaskGenerator()
            self.scheduler: SchedulerClient = SchedulerClient()
        except Exception as e:
            logger.error(f"An error occurred while initializing SensorCapsule: {e}")
        self.config = config
        self.client_list = [self.task_generator, self.scheduler]
        self.collect_request_queue: asyncio.Queue = asyncio.Queue(maxsize=20)
        self.collect_response_queue: asyncio.Queue = asyncio.Queue(maxsize=20)
        self.last_dispatched_task = None
        self.shutdown_event: asyncio.Event = shutdown_event

    async def start(self):
        """Start sensor-capsule and its clients."""
        logger.info("Starting SensorCapsule.")
        self.is_running = True
        for client in self.client_list:
            try:
                await client.start()
            except Exception as e:
                logger.error(f"An error occurred while starting {client}: {e}")

    async def stop(self):
        """Stop the sensor-capsule and its clients."""
        logger.info("Stopping SensorCapsule.")
        for client in self.client_list:
            try:
                await client.stop()
            except Exception as e:
                logger.error(f"An error occurred while stopping {client}: {e}")

    async def status(self) -> dict:
        """Get the current status of sensor-capsule."""
        queue_list = [task for task in self.collect_request_queue._queue]
        return {
            "last_dispatched_task": self.last_dispatched_task,
            "collect_request_queue": queue_list,
        }

    async def http_request(self, method, url, data=None):
        """Helper function to handle HTTP requests."""
        try:
            if method == "GET":
                response = requests.get(url, cert=(self.config.cert, self.config.key), verify=False)
            elif method == "POST":
                headers = {"Content-Type": "application/json"}
                response = requests.post(
                    url, json=data, cert=(self.config.cert, self.config.key), verify=False, headers=headers
                )
            response.raise_for_status()  # Raises an HTTPError for bad responses
            return response.json()  # Assuming the response is JSON
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error occurred: {e} - Status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error connecting to {url}: {e}")
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from the response: {response.text}")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
        return None

    async def get_bolt_collect_request(self):
        """Poll the Bolt service for a single collect request."""
        url = f"https://{self.config.bolt_ip}:{self.config.bolt_port}{self.config.bolt_route}"
        response_data = await self.http_request("GET", url)
        if response_data:
            logger.info(f"Successfully completed GET request from Bolt: {response_data}")
            if response_data["request"] is not None:
                await self.collect_response_queue.put((response_data["request"], response_data["timestamp"]))
                logger.info(f"Collect request stored in queue: {response_data['request']}")
                return response_data
            else:
                logger.info("Collect request is None.")
        else:
            logger.error("Failed to retrieve collect request from Bolt.")
        return response_data

    async def post_spout_collect_response(self, collect_response):
        """Post collect response to the Spout service."""
        url = f"https://{self.config.spout_ip}:{self.config.spout_port}{self.config.spout_route}"
        response_data = await self.http_request("POST", url, data=collect_response)
        if response_data:
            logger.info(f"Successfully completed POST to Spout: {response_data}")
            if response_data.get("ingested", False):
                logger.info(f"Collect response ingested by Spout: {response_data}")
                await self.collect_request_queue.put((collect_response, response_data["timestamp"]))
                logger.info(f"Collect request stored in queue: {response_data}")
            else:
                logger.error(f"Collect response not ingested by Spout: {response_data}")
        else:
            logger.error("Failed to post collect response to Spout.")

    async def poll_bolt_collect_request(self):
        """Periodically poll the Bolt service for collect requests, transform them, and send to scheduler."""
        while True:
            await asyncio.sleep(self.config.bolt_poll_interval)
            response = await self.get_bolt_collect_request()
            if response:
                if response["request"] is not None:
                    collect_request = response["request"]
                    timestamp = response["timestamp"]
                    # transform to Task
                    task = await self.transform_bolt_collect_request_to_task(collect_request)
                    # send to scheduler
                    await self.scheduler.enqueue_collect_request(task)

    # TODO: Add start time modifier to task generator
    async def transform_collect_request_to_task(self, collect_request: dict) -> Task:
        """Transform a collect request to a Task."""
        sat_id = collect_request["satNo"]
        task = self.task_generator(sat_id)
        return task

    async def transform_collect_request_to_task(self, collect_request: dict) -> Task:
        """Transform a collect request to a Task."""
        sat_id = collect_request["satNo"]
        task = self.task_generator(sat_id)
        return task
