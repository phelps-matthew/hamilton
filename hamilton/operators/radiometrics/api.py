"""
Form radiometrics associated with space objects. 

For now this will be RF quantities like transmitter, downlink frequency,
polarization, modulation, etc.
"""

from hamilton.operators.radiometrics.config import RadiometricsControllerConfig
from hamilton.operators.database.client import DBClient


class Radiometrics:
    def __init__(self, config: RadiometricsControllerConfig, database: DBClient):
        self.config: RadiometricsControllerConfig = config
        self.db: DBClient = database

    async def get_tx_profile(self, sat_id: str) -> dict:
        return await self.db.query_record(sat_id)

    async def get_je9pel_freqs(self, sat_id: str) -> dict:
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
        # use a dict to remove duplicates but keep order
        return list(dict.fromkeys(downlink_freqs))

    async def get_satnogs_freqs(self, sat_id: str) -> dict:
        """Return list of Satnogs active downlink frequencies associated with satellite id"""
        downlink_freqs = []
        tx_profile = await self.get_tx_profile(sat_id)
        for transmitter in tx_profile["transmitters"]:
            freq = transmitter["downlink_low"]
            mode = transmitter["mode"]
            if freq is not None and mode.lower() != "cw":
                downlink_freqs.append(freq)
        # use a dict to remove duplicates but keep order
        return list(dict.fromkeys(downlink_freqs))

    async def get_downlink_freqs(self, sat_id: str) -> list:
        """Return list of JE9PEL active downlink frequencies associated with satellite id"""
        je9pel_freqs = await self.get_je9pel_freqs(sat_id)
        satnogs_freqs = await self.get_satnogs_freqs(sat_id)
        # ranked from best to worst, starting at index 0
        # use a dict to remove duplicates but keep order
        freqs = list(dict.fromkeys(je9pel_freqs + satnogs_freqs))
        return freqs
