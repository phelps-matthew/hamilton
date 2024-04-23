"""
1) Astrodynamics: Precompute orbit (for computing mount path?)
2) Radiometrics: Get downlink tx frequency
3) Precompute mount path direction. 
4) Position mount to ready position. (Preposition)
5) When elevation limits aren't violated, start tracking until end of pass. Signal tracking. Start recording.
6) Stop recording. Position mount to home. (Post position) Signal non-active.
"""

from datetime import datetime, timezone, timedelta
import asyncio
import logging
from hamilton.operators.sdr.client import SDRClient
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.operators.tracker.client import TrackerClient
from hamilton.base.task import Task

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self):
        try:
            self.sdr: SDRClient = SDRClient()
            self.tracker: TrackerClient = TrackerClient()
        except Exception as e:
            logger.error(f"An error occured while initializing clients: {e}")

        self.is_running = False
        self.shutdown_event = asyncio.Event()
        self.task: Task = None
        self.client_list: list[AsyncMessageNodeOperator] = [self.sdr, self.tracker]

    async def start(self):
        logger.info("Starting Orchestrator.")
        for client in self.client_list:
            try:
                await client.start()
            except Exception as e:
                logger.error(f"An error occured while starting {client}: {e}")

    async def stop(self):
        logger.info("Stopping Orchestrator.")
        await self.stop_orchestrating()
        for client in self.client_list:
            try:
                await client.stop_orchestrating()
            except Exception as e:
                logger.error(f"An error occured while stopping {client}: {e}")

    async def stop_orchestrating(self):
        """Stop the orchestration loop and reset orchestration status."""
        self.shutdown_event.set()
        self.is_running = False
        logger.info("Orchestration routine has been successfully stopped.")

    async def status(self):
        return {"status": "active" if self.is_running else "idle"}

    async def set_task(self, task: Task):
        self.task = task

    async def orchestrate(self):
        """Orchestrate the tracking and recording of a space object."""
        logger.info("Starting orchestration...")
        self.is_running = True
        await self.clear_shutdown_event()

        try:
            # Slew to AOS ready position
            await self.tracker.slew_to_home()
            await self.tracker.slew_to_aos(self.task)

            # Compute timings
            aos_time = self.task["parameters"]["aos"]["time"]
            los_time = self.task["parameters"]["los"]["time"]
            aos_pre_sleep = aos_time - datetime.now(timezone.utc)
            #aos_los_sleep = los_time - aos_time
            aos_los_sleep = timedelta(seconds=20)

            # Sleep until AOS
            logger.info(f"Waiting for AOS. Sleeping for {aos_pre_sleep.total_seconds()} seconds.")
            aos_pre_sleep_task = asyncio.create_task(asyncio.sleep(aos_pre_sleep.total_seconds()))
            shutdown_task = asyncio.create_task(self.shutdown_event.wait())
            await asyncio.wait(
                [aos_pre_sleep_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            if self.shutdown_event.is_set():
                logger.info("Shutdown event triggered. Aborting orchestration.")
                await self.stop_orchestrating()
                return

            # Start operators
            logger.info("Starting tracking and recording.")
            await self.tracker.start_tracking(self.task)
            await self.sdr.start_record(self.task["parameters"]["sdr"])

            # Sleep until LOS
            logger.info(f"Tracking and recording. Sleeping until LOS for {aos_los_sleep.total_seconds()} seconds.")
            aos_los_sleep_task = asyncio.create_task(asyncio.sleep(aos_los_sleep.total_seconds()))
            shutdown_task = asyncio.create_task(self.shutdown_event.wait())
            await asyncio.wait(
                [aos_los_sleep_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            if self.shutdown_event.is_set():
                logger.info("Shutdown event triggered. Stopping tracking and recording.")
                await self.tracker.stop_tracking()
                await self.sdr.stop_record()
                await self.stop_orchestrating()
                return

            # Stop operators
            logger.info("Stopping tracking and recording.")
            await self.sdr.stop_record()
            await self.tracker.stop_tracking()

            # Finished
            await self.stop_orchestrating()
            logger.info("Orchestration completed successfully.")

        except Exception as e:
            logger.error(f"An error occurred during orchestration: {e}")
            await self.sdr.stop_record()
            await self.tracker.stop_tracking()
            await self.stop_orchestrating()

    async def clear_shutdown_event(self):
        self.shutdown_event.clear()
