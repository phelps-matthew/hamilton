"""
1) Astrodynamics: Precompute orbit (for computing mount path?)
2) Radiometrics: Get downlink tx frequency
3) Precompute mount path direction. 
4) Position mount to ready position. (Preposition)
5) When elevation limits aren't violated, start tracking until end of pass. Signal tracking. Start recording.
6) Stop recording. Position mount to home. (Post position) Signal non-active.
"""

import asyncio
import logging
from hamilton.operators.astrodynamics.client import AstrodynamicsClient
from hamilton.operators.radiometrics.client import RadiometricsClient
from hamilton.operators.mount.client import MountClient
from hamilton.operators.sdr.client import SDRClient
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self):
        try:
            self.sdr: AsyncMessageNodeOperator = SDRClient()
            self.astrodynamics: AsyncMessageNodeOperator = AstrodynamicsClient()
            self.radiometrics: AsyncMessageNodeOperator = RadiometricsClient()
            self.mount: AsyncMessageNodeOperator = MountClient()
        except Exception as e:
            logger.error(f"An error occured while initializing clients: {e}")

        self.client_list: list[AsyncMessageNodeOperator] = [self.sdr, self.astrodynamics, self.radiometrics, self.mount]

    async def start(self):
        for client in self.client_list:
            try:
                await client.start()
            except Exception as e:
                logger.error(f"An error occured while starting {client}: {e}")

    async def stop(self):
        for client in self.client_list:
            try:
                await client.stop()
            except Exception as e:
                logger.error(f"An error occured while stopping {client}: {e}")
