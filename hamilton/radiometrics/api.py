"""
Form radiometrics associated with space objects. 

For now this will be RF quantities like transmitter, downlink frequency,
polarization, modulation, etc.
"""

from hamilton.radiometrics.config import RadiometricsControllerConfig
from hamilton.database.client import DBClient


class Radiometrics:
    def __init__(self, config: RadiometricsControllerConfig, database: DBClient):
        self.config: RadiometricsControllerConfig = config
        self.db: DBClient = database

    async def get_tx_profile(self, sat_id:str) -> dict:
        return await self.db.query_record(sat_id)

    # Note: limited implementation, only uses JE9PEL downlinks for now
    async def get_downlink_freqs(self, sat_id: str) -> list:
        """Return list of JE9PEL active downlink frequencies associated with satellite id"""
        downlink_freqs = []
        tx_profile = await self.get_tx_profile(sat_id)
        if tx_profile["je9pel"] is not None:
            for link in tx_profile["je9pel"]["downlink"]:
                if link["active"]:
                    if link["low"] is not None:
                        downlink_freqs.append(link["low"])
                    elif link["high"] is not None:
                        downlink_freqs.append(link["high"])
        return downlink_freqs