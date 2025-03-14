"""
1) Polls hamilton-x-machina for collect requests
2) Transforms hamilton-x-machina collect request to Task and sends to scheduler exchange (scheduler.enqueue_collect_request)
3) Exposes the hamilton-x-machina exchange for receiving collect responses
4) Transforms completed Tasks to collect responses, which are then sent to hamilton-x-machina
"""

import asyncio
from datetime import datetime, timezone, timedelta
import json
from loguru import logger
from loguru import logger
import aiohttp
from hamilton.operators.scheduler.client import SchedulerClient
from hamilton.operators.astrodynamics.client import AstrodynamicsClient
from hamilton.operators.hxm_adapter.config import HXMAdapterControllerConfig
from hamilton.base.task import Task, TaskGenerator
from hamilton.common.utils import wait_until_first_completed, CustomJSONEncoder



class HXMAdapter:
    def __init__(self, config: HXMAdapterControllerConfig, shutdown_event: asyncio.Event = None):
        try:
            self.task_generator: TaskGenerator = TaskGenerator()
            self.scheduler: SchedulerClient = SchedulerClient()
            self.astrodynamics: AstrodynamicsClient = AstrodynamicsClient()
        except Exception as e:
            logger.error(f"An error occurred while initializing HXMAdapter: {e}")
        self.config = config
        self.client_list = [self.task_generator, self.scheduler, self.astrodynamics]
        self.collect_request_queue: asyncio.Queue = asyncio.Queue(maxsize=20)
        self.collect_response_queue: asyncio.Queue = asyncio.Queue(maxsize=20)
        self.last_dispatched_task = None
        self.shutdown_event: asyncio.Event = shutdown_event
        self.dispatch_buffer = timedelta(minutes=6)
        self.hxm_url = f"http://{self.config.hamilton_x_machina_ip}:{self.config.hamilton_x_machina_port}"

    async def start(self):
        """Start hamilton-x-machina adapter and its clients."""
        logger.info("Starting HXMAdapter.")
        self.is_running = True
        for client in self.client_list:
            try:
                await client.start()
            except Exception as e:
                logger.error(f"An error occurred while starting {client}: {e}")

    async def stop(self):
        """Stop the hamilton-x-machina adapter and its clients."""
        logger.info("Stopping HXMAdapter.")
        for client in self.client_list:
            try:
                await client.stop()
            except Exception as e:
                logger.error(f"An error occurred while stopping {client}: {e}")

    async def status(self) -> dict:
        """Get the current status of hamilton-x-machina adapter."""
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
                        if response.status == 404:
                            logger.info(f"No data found at {url}: {response.status}")
                            return None
                        response.raise_for_status()  # Raises an HTTPError for bad responses
                        return await response.json()  # Assuming the response is JSON
                elif method == "POST":
                    async with session.post(url, json=data, headers=headers, ssl=False, timeout=timeout) as response:
                        response.raise_for_status()
                        return await response.json()
            except aiohttp.ClientResponseError as e:
                logger.error(f"HTTP error occurred: {e} - Status code: {e.status}")
                if e.status == 404:
                    # This is an expected case for empty queues
                    return None
            except aiohttp.ClientError as e:
                logger.error(f"Error connecting to {url}: {e}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON from the response: {e}")
            except Exception as e:
                logger.error(f"An unexpected error occurred: {e}")
            return None

    async def pop_collect_request(self):
        """Pop a collect request from the HXM service."""
        url = f"{self.hxm_url}/api/v1/collect-requests/pop"
        response_data = await self.http_request("GET", url)
        if response_data:
            logger.info(f"Successfully popped collect request from HXM: {json.dumps(response_data, indent=4, cls=CustomJSONEncoder)}")
            return response_data
        else:
            # This is normal when queue is empty, so use info level
            logger.info("No collect requests available to pop from HXM")
            return None

    async def peek_collect_request(self):
        """Peek at a collect request from the HXM service without removing it."""
        url = f"{self.hxm_url}/api/v1/collect-requests/peek"
        response_data = await self.http_request("GET", url)
        if response_data:
            logger.info(f"Successfully peeked collect request from HXM: {json.dumps(response_data, indent=4, cls=CustomJSONEncoder)}")
            return response_data
        else:
            # This is normal when queue is empty, so use info level
            logger.info("No collect requests available to peek from HXM")
            return None

    async def get_all_collect_requests(self):
        """Get all collect requests from the HXM service."""
        url = f"{self.hxm_url}/api/v1/collect-requests"
        response_data = await self.http_request("GET", url)
        if response_data:
            logger.info(f"Successfully retrieved {len(response_data)} collect requests from HXM")
            return response_data
        else:
            logger.info("No collect requests available from HXM")
            return []

    async def submit_collect_response(self, collect_response):
        """Submit a collect response to the HXM service."""
        url = f"{self.hxm_url}/api/v1/collect-responses"
        response_data = await self.http_request("POST", url, data=collect_response)
        if response_data:
            logger.info(f"Successfully submitted collect response to HXM: {response_data}")
            return response_data
        else:
            logger.error(f"Failed to submit collect response to HXM")
            return None

    async def poll_hxm_collect_request(self):
        """Periodically poll the HXM service for collect requests, transform them, and send to scheduler."""
        while not self.shutdown_event.is_set():
            try:
                collect_request = await self.pop_collect_request()
                if collect_request:
                    # Transform to Task
                    task = await self.collect_request_to_task(collect_request)
                    if task:
                        # Send to scheduler
                        logger.info("Sending task to scheduler")
                        await self.scheduler.enqueue_collect_request(task)
                        self.last_dispatched_task = task
                        # Wait a short time before checking for more requests
                        await wait_until_first_completed([self.shutdown_event], [asyncio.sleep(1)])
                        continue
                
                # If no request or processing failed, wait before polling again
                logger.info(f"Sleeping for {self.config.hamilton_x_machina_poll_interval} seconds")
                await wait_until_first_completed([self.shutdown_event], [asyncio.sleep(self.config.hamilton_x_machina_poll_interval)])
            except Exception as e:
                logger.error(f"Error in poll_hxm_collect_request: {e}")
                # Continue polling even after errors
                await wait_until_first_completed([self.shutdown_event], [asyncio.sleep(self.config.hamilton_x_machina_poll_interval)])

    async def collect_request_to_task(self, collect_request: dict) -> Task:
        """Transform a collect request to a Task."""
        logger.info(f"Collect request:\n{json.dumps(collect_request, indent=4, cls=CustomJSONEncoder)}")
        try:
            sat_id = collect_request.get("satNo")
            if not sat_id:
                logger.error(f"Missing satNo in collect request: {collect_request}")
                return None
                
            # Use the start time from the request or current time if not available
            start_time = collect_request.get("startTime")
            if not start_time:
                start_time = datetime.now(tz=timezone.utc)
            elif isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                
            task = await self.task_generator.generate_task(sat_id=sat_id, start_time=start_time)
            logger.info(f"Generated task: {json.dumps(task, indent=4, cls=CustomJSONEncoder)}")
            return task
        except Exception as e:
            logger.error(f"Error transforming collect request to task: {e}")
            return None

    async def task_to_collect_response(self, task: Task, accepted: bool = True) -> dict:
        """Transform a Task to a collect response."""
        try:
            request_id = task.get("task_id", "unknown")
            
            if accepted:
                collect_response = {
                    "modelType": "CollectResponseAccepted",
                    "classificationMarking": "U",
                    "source": "hamilton-x-machina",
                    "origin": "TEST-ORIGIN",
                    "collect_request": {
                        "id": request_id
                    },
                    "actualStartDateTime": task["parameters"]["aos"]["time"].isoformat().replace('+00:00', 'Z'),
                    "actualEndDateTime": task["parameters"]["los"]["time"].isoformat().replace('+00:00', 'Z'),
                    "notes": "Accepted by the sensor"
                }
            else:
                collect_response = {
                    "modelType": "CollectResponseRejected",
                    "classificationMarking": "U",
                    "source": "hamilton-x-machina",
                    "origin": "TEST-ORIGIN",
                    "collect_request": {
                        "id": request_id
                    },
                    "notes": "Rejected by the sensor",
                    "errorDescription": "Cannot schedule due to resource constraints"
                }
                
            logger.info(f"Created collect response: {json.dumps(collect_response, indent=4, cls=CustomJSONEncoder)}")
            return collect_response
        except Exception as e:
            logger.error(f"Error transforming task to collect response: {e}")
            return None

    async def generate_collect_requests(self, start_time: datetime = None, end_time: datetime = None):
        """Generate collect requests, respecting dispatch buffer time and AOS/LOS overlap."""
        task_list = []
        max_tasks = 20
        if start_time is None:
            start_time = datetime.now(timezone.utc)
        elif isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            
        if end_time is None:
            end_time = start_time + timedelta(hours=4)
        elif isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
        tasks = await self.retrieve_tasks_from_astrodynamics(start_time=start_time, end_time=end_time)
        for task in tasks:
            aos = task["parameters"]["aos"]["time"]
            los = task["parameters"]["los"]["time"]
            if not task_list or (aos >= task_list[-1]["parameters"]["los"]["time"] + self.dispatch_buffer):
                logger.info(f"Adding task_id:{task['task_id']}, sat_id:{task['parameters']['sat_id']} to task list")
                task_list.append(task)
                if len(task_list) >= max_tasks:
                    break
                    
        logger.info(f"Task list length: {len(task_list)}")
        return task_list

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
