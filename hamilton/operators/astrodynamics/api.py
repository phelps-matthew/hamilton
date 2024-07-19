"""Compute astrodynamic parameters associated with space objects. Based on TLE's for now."""

import asyncio
import logging
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pytz
from skyfield.api import EarthSatellite, load, wgs84

from hamilton.operators.astrodynamics.config import AstrodynamicsControllerConfig
from hamilton.operators.database.client import DBClient

logger = logging.getLogger(__name__)


@asynccontextmanager
async def acquire_lock(lock):
    """
    Context manager to acquire an asyncio lock only if it is not already locked, preventing deadlocks in nested function calls.
    """
    if not lock.locked():
        async with lock:
            yield
    else:
        yield


class SpaceObjectTracker:
    def __init__(self, config: AstrodynamicsControllerConfig, database: DBClient):
        self.config: AstrodynamicsControllerConfig = config
        self.db: DBClient = database

        # Astrodynamics init
        self._timescale = load.timescale()
        self._sensor = wgs84.latlon(
            latitude_degrees=config.LATTITUDE,
            longitude_degrees=config.LONGITUDE,
            elevation_m=config.ALTITUDE,
        )
        self.min_el = config.MIN_ELEVATION  # minimum observational elevation (deg)

        # In memory cached dictionaries of orbital state
        self.aos_los = dict()
        self.orbits = dict()
        self.satellites = dict()

        # Lock for protecting the dictionaries
        self._lock = asyncio.Lock()

    async def _get_earth_satellite(self, sat_id: str) -> EarthSatellite:
        satellite = None
        # Fetch from cached EarthSatellite objects
        if sat_id in self.satellites:
            return self.satellites[sat_id]

        # Otherwise, create new EarthSatellite and cache it
        try:
            satellite_record = await self.db.query_record(sat_id)
            tle_line_1 = satellite_record["tle1"]
            tle_line_2 = satellite_record["tle2"]
            satellite = EarthSatellite(line1=tle_line_1, line2=tle_line_2)
            self.satellites[sat_id] = satellite
        except Exception as e:
            logger.error(f"Failed to create EarthSatellite for {sat_id}: {e}")

        return satellite

    async def get_tle(self, sat_id: str) -> tuple[str, str]:
        try:
            satellite_record = await self.db.query_record(sat_id)
            tle_line_1 = satellite_record["tle1"]
            tle_line_2 = satellite_record["tle2"]
        except Exception as e:
            logger.error(f"Failed to get TLE for {sat_id}: {e}")

        return tle_line_1, tle_line_2

    async def get_kinematic_state(self, sat_id=None, time=None) -> dict:
        """Calculate observational params for single space object at a given time

        Args:
            sat_id: satnogs satellite identifier
            time: time to evaluate TLE at, defaults to current UTC time

        Returns: dict, observational params (az, el, az_rate, el_rate, range, rel_vel)
        """
        kinematic_state = None
        async with acquire_lock(self._lock):
            # Default to current time if not provided
            try:
                if time is None:
                    time = datetime.now(tz=timezone.utc)
                time_scale = self._timescale.from_datetime(time)

                satellite = await self._get_earth_satellite(sat_id)
                params = (satellite - self._sensor).at(time_scale).frame_latlon_and_rates(self._sensor)
                el = params[0].degrees
                az = params[1].degrees
                range_ = params[2].km
                el_rate = params[3].degrees.per_second
                az_rate = params[4].degrees.per_second
                range_rate = params[5].km_per_s

                kinematic_state = {
                    "az": az,
                    "el": el,
                    "az_rate": az_rate,
                    "el_rate": el_rate,
                    "range": range_,
                    "rel_vel": range_rate,
                    "time": time,
                }
            except Exception as e:
                logger.error(f"Failed to get kinematic state for {sat_id} at {time}: {e}")
        return kinematic_state

    async def get_aos_los(self, sat_id, time=None, delta_t=8) -> dict[str, dict[str, datetime]]:
        """Calculate acquisition of signal (AOS) and loss of signal (LOS) times

        Args:
            sat_id: satnogs satellite identifier
            time: time to evaluate TLE at, defaults to current time
            delta_t: offset from `time` by which to compute next AOS/LOS (hours)
        Returns:
            full_event_map: {
                "aos": {"time": datetime, "kinematic_state": dict},
                "tca": {"time": datetime, "kinematic_state": dict},
                "los": {"time": datetime, "kinematic_state": dict}
            }
            Semantics:
                * aos — Satellite rose above ``altitude_degrees``.
                * tca — Satellite culminated and started to descend again.
                * los — Satellite fell below ``altitude_degrees``.
        """
        full_event_map = None
        async with acquire_lock(self._lock):
            try:
                # If no target time is passed, then safe to reference cached AOS/LOS
                if sat_id in self.aos_los and time is None:
                    return self.aos_los[sat_id]

                # offset from `time` by which to compute next AOS and LOS
                delta_t_prior = timedelta(minutes=5)
                delta_t_after = timedelta(hours=delta_t)

                if time is None:
                    time = datetime.now(tz=timezone.utc)
                t0 = self._timescale.from_datetime(time - delta_t_prior)  # search results from now - 5 minutes
                t1 = self._timescale.from_datetime(time + delta_t_after)  # search up to +delta_t hours later

                satellite = await self._get_earth_satellite(sat_id=sat_id)
                times, events = satellite.find_events(self._sensor, t0=t0, t1=t1, altitude_degrees=self.min_el)
                times = [t.utc_datetime() for t in times]
                event_map = defaultdict(list)
                event_key_remap = {0: "aos", 1: "tca", 2: "los"}
                for t, event in zip(times, events):
                    event_map[event_key_remap[int(event)]].append(t)

                full_event_map = {key: {"time": None, "kinematic_state": None} for key in ["aos", "tca", "los"]}

                # Iterate through the lists to find a valid combination of aos < tca < los
                for i in range(len(event_map["aos"])):
                    for j in range(len(event_map["tca"])):
                        for k in range(len(event_map["los"])):
                            if event_map["aos"][i] < event_map["tca"][j] < event_map["los"][k]:
                                aos_time = event_map["aos"][i]
                                tca_time = event_map["tca"][j]
                                los_time = event_map["los"][k]

                                aos_kinematic_state = await self.get_kinematic_state(sat_id, time=aos_time)
                                tca_kinematic_state = await self.get_kinematic_state(sat_id, time=tca_time)
                                los_kinematic_state = await self.get_kinematic_state(sat_id, time=los_time)

                                full_event_map["aos"] = {"time": aos_time, "kinematic_state": aos_kinematic_state}
                                full_event_map["tca"] = {"time": tca_time, "kinematic_state": tca_kinematic_state}
                                full_event_map["los"] = {"time": los_time, "kinematic_state": los_kinematic_state}

                                self.aos_los[sat_id] = full_event_map
                                return full_event_map

                logger.error(f"No valid combination of aos < tca < los found for {sat_id}")
            except Exception as e:
                logger.error(f"Failed to get aos_los for {sat_id}: {e}")

        return full_event_map

    async def get_interpolated_orbit(
        self, sat_id: str, aos: Optional[datetime] = None, los: Optional[datetime] = None
    ) -> dict[str, list[Any]]:
        """Calculate orbital path within observational window (AOS-LOS)

        Args:
            sat_id: satnogs satellite identifier
            aos: datetime utc, AOS
            los: datetime utc, LOS

        Returns:
            orbit: dict of lists of az, el, and times representing interpolated orbit
        """
        orbit = None
        async with acquire_lock(self._lock):
            try:
                # If no target AOS/LOS is passed, then safe to reference cached orbit
                if sat_id in self.orbits and aos is None and los is None:
                    return self.orbits[sat_id]

                # Compute AOS and LOS if not provided
                event_map = await self.get_aos_los(sat_id)
                aos = event_map["aos"]["time"]
                los = event_map["los"]["time"]

                num_samples = 20
                orbit = {"az": [], "el": [], "time": []}

                if (aos and los) and (aos < los):
                    # aos = self.local_to_utc(aos)
                    # los = self.local_to_utc(los)
                    delta = los - aos
                    interval = delta / (num_samples - 1)
                    for i in range(num_samples):
                        t = aos + interval * i
                        obs_params = await self.get_kinematic_state(sat_id, t)
                        orbit["az"].append(obs_params["az"])
                        orbit["el"].append(obs_params["el"])
                        # orbit["time"].append(self.utc_to_local(t).strftime("%m-%d %H:%M:%S"))
                        orbit["time"].append(t.strftime("%m-%d %H:%M:%S"))

                self.orbits[sat_id] = orbit
            except Exception as e:
                logger.error(f"Failed to get interpolated orbit for {sat_id}: {e}")
        return orbit

    async def recompute_all_states(self):
        """Clear stored satellites, aos_los, and orbits and recompute these quantities for all satellites. This operation will
        coincide with database refresh interval."""
        async with acquire_lock(self._lock):
            self.aos_los.clear()
            self.orbits.clear()
            self.satellites.clear()
            sat_ids = await self.db.get_satellite_ids()

            async def recompute_for_satellite(sat_id, index, total):
                logger.info(f"({index}/{total}) Recomputing orbit for {sat_id}")
                await self.get_aos_los(sat_id)
                await self.get_interpolated_orbit(sat_id)

            # Seem to get irreproducable errors here (missing "tle1" key) but batching sometimes helps
            batch_size = 50
            for i in range(0, len(sat_ids), batch_size):
                batch = sat_ids[i : i + batch_size]
                tasks = [recompute_for_satellite(sat_id, j, len(sat_ids)) for j, sat_id in enumerate(batch, start=i)]
                await asyncio.gather(*tasks)

            logger.info("Finished recomputing all orbits")

    async def get_all_aos_los(self, start_time: datetime, end_time: datetime):
        """Get all AOS/LOS events within a given time window, return list of events, sorted by ascending AOS"""
        if not self.aos_los:
            await self.recompute_all_states()
        aos_los = self.aos_los
        # Filter the aos_los dictionary into a list of tuples
        aos_los_list = []
        for sat_id, data in aos_los.items():
            aos = data["aos"]["time"]
            los = data["los"]["time"]
            if aos is None or los is None:
                continue
            if start_time <= aos <= end_time:
                aos_los_list.append((sat_id, aos, los))
        # Sort the list by 'aos'
        sorted_aos_los_list = sorted(aos_los_list, key=lambda x: x[1])
        return sorted_aos_los_list

    @staticmethod
    def utc_to_local(time, tz="HST"):
        local_timezone = pytz.timezone(tz)
        return time.replace(tzinfo=pytz.utc).astimezone(local_timezone)

    @staticmethod
    def local_to_utc(time):
        return time.astimezone(timezone.utc)
