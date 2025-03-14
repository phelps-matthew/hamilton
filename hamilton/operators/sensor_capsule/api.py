"""
1) Polls sensor-capsule/bolt for collect requests
2) Transforms bolt collect request to Task and sends to scheduler exchange (scheduler.enqueue_collect_request)
3) Exposes the sensor_capsule exchange for receiving collect responses
4) Transforms completed Tasks to collect responses, which are then sent to sensor-capsule/spout
"""

import asyncio
from datetime import datetime, timezone, timedelta
import json
from loguru import logger
import aiohttp
from hamilton.operators.scheduler.client import SchedulerClient
from hamilton.operators.astrodynamics.client import AstrodynamicsClient
from hamilton.operators.sensor_capsule.config import SensorCapsuleControllerConfig
from hamilton.base.task import Task, TaskGenerator
from hamilton.common.utils import wait_until_first_completed, CustomJSONEncoder




class SensorCapsule:
    def __init__(self, config: SensorCapsuleControllerConfig, shutdown_event: asyncio.Event = None):
        try:
            self.task_generator: TaskGenerator = TaskGenerator()
            self.scheduler: SchedulerClient = SchedulerClient()
            self.astrodynamics: AstrodynamicsClient = AstrodynamicsClient()
        except Exception as e:
            logger.error(f"An error occurred while initializing SensorCapsule: {e}")
        self.config = config
        self.client_list = [self.task_generator, self.scheduler, self.astrodynamics]
        self.collect_request_queue: asyncio.Queue = asyncio.Queue(maxsize=20)
        self.collect_response_queue: asyncio.Queue = asyncio.Queue(maxsize=20)
        self.last_dispatched_task = None
        self.shutdown_event: asyncio.Event = shutdown_event
        # TODO: remove
        self.dispatch_buffer = timedelta(minutes=6)

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
        """Helper function to handle HTTP requests asynchronously."""
        headers = {"Content-Type": "application/json"} if method == "POST" else {}
        timeout = aiohttp.ClientTimeout(total=5)  # Set a timeout for the request
        async with aiohttp.ClientSession() as session:
            try:
                if method == "GET":
                    async with session.get(url, ssl=False, timeout=timeout) as response:
                        response.raise_for_status()  # Raises an HTTPError for bad responses
                        return await response.json()  # Assuming the response is JSON
                elif method == "POST":
                    async with session.post(url, json=data, headers=headers, ssl=False, timeout=timeout) as response:
                        response.raise_for_status()
                        return await response.json()
            except aiohttp.ClientResponseError as e:
                logger.error(f"HTTP error occurred: {e} - Status code: {response.status}")
            except aiohttp.ClientError as e:
                logger.error(f"Error connecting to {url}: {e}")
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON from the response: {await response.text()}")
            except Exception as e:
                logger.error(f"An unexpected error occurred: {e}")
            return None

    async def get_bolt_collect_request(self):
        """Poll the Bolt service for a single collect request."""
        url = f"https://{self.config.bolt_ip}:{self.config.bolt_port}{self.config.bolt_route}"
        response_data = await self.http_request("GET", url)
        if response_data:
            logger.info(
                f"Successfully completed GET request from Bolt: {json.dumps(response_data, indent=4, cls=CustomJSONEncoder)}"
            )
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
        while not self.shutdown_event.is_set():
            response = await self.get_bolt_collect_request()
            if response:
                if response["request"] is not None:
                    collect_request = response["request"]
                    timestamp = response["timestamp"]
                    # transform to Task
                    task = await self.collect_request_to_task(collect_request)
                    # send to scheduler
                    logger.info("Sending task to scheduler")
                    await self.scheduler.enqueue_collect_request(task)
                    await wait_until_first_completed([self.shutdown_event], [asyncio.sleep(1)])
                    continue
            logger.info(f"Sleeping for {self.config.bolt_poll_interval} seconds")
            await wait_until_first_completed([self.shutdown_event], [asyncio.sleep(self.config.bolt_poll_interval)])

    async def collect_request_to_task(self, collect_request: dict) -> Task:
        """Transform a collect request to a Task."""
        sat_id = collect_request["satNo"]
        start_time = collect_request["startTime"]
        start_time = datetime.now(tz=timezone.utc)
        task = await self.task_generator.generate_task(sat_id=sat_id, start_time=start_time)
        logger.info(f"Generated task: {json.dumps(task, indent=4, cls=CustomJSONEncoder)}")
        return task

    async def task_to_collect_request(self, task: Task) -> dict:
        """Transform a Task to a collect request."""
        tle = await self.astrodynamics.get_tle(task["parameters"]["sat_id"])
        collect_request = {
            "classificationMarking": "U",
            "dataMode": "TEST",
            "type": "OBJECT",
            "source": task["source"],
            "startTime": task["parameters"]["aos"]["time"],
            "endTime": task["parameters"]["los"]["time"],
            "satNo": int(task["parameters"]["sat_id"]),
            "id": task["task_id"],
            "orbitRegime": "LEO",
            "freq": task["parameters"]["sdr"]["freq"],
            "polarization": "H/V",
            "duration": int((task["parameters"]["los"]["time"] - task["parameters"]["aos"]["time"]).total_seconds()),
            "numTracks": int(1),
            "createdAt": datetime.now(tz=timezone.utc),
            "elset": {
                "line1": tle[0],
                "line2": tle[1],
            },
        }
        logger.info(f"Collect request: {json.dumps(collect_request, indent=4, cls=CustomJSONEncoder)}")
        return collect_request

    async def generate_collect_requests(self, start_time: datetime = None, end_time: datetime = None):
        """Generate collect requests, respecting dispatch buffer time and AOS/LOS overlap."""
        task_list = []
        max_tasks = 20
        if start_time is None:
            start_time = datetime.now(timezone.utc)
        if end_time is None:
            end_time = start_time + timedelta(hours=4)
        tasks = await self.retrieve_tasks_from_astrodynamics(start_time=start_time, end_time=end_time)
        for task in tasks:
            aos = task["parameters"]["aos"]["time"]
            los = task["parameters"]["los"]["time"]
            if not task_list or (aos >= task_list[-1]["parameters"]["los"]["time"] + self.dispatch_buffer):
                logger.info(f"Adding task_id:{task['task_id']}, sat_id:{task['parameters']['sat_id']} to task list")
                task_list.append(task)
                if len(task_list) > max_tasks:
                    break
        logger.info(f"Task list length: {len(task_list)}")
        collect_request_list = [await self.task_to_collect_request(task) for task in task_list]
        return collect_request_list

    async def retrieve_tasks_from_astrodynamics(
        self, start_time: datetime = None, end_time: datetime = None
    ) -> list[Task]:
        """Retrieve satellite records with AOS between `start_time` and `end_time`, ascending in AOS."""
        if start_time is None:
            start_time = datetime.now(timezone.utc)
        if end_time is None:
            end_time = datetime.now(timezone.utc) + timedelta(hours=1)
        sats_aos_los = await self.astrodynamics.get_all_aos_los(start_time, end_time)
        task_list = []
        for sat_id, aos, los in sats_aos_los:
            task = await self.task_generator.generate_task(sat_id)
            if task is not None:
                task_list.append(task)

        logger.info(f"Tasks retrieved: {len(task_list)}")
        return task_list
