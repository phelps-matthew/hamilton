"""Compute astrodynamic parameters associated with space objects. Based on TLE's for now."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

import pytz
from skyfield.api import EarthSatellite, load, wgs84

from hamilton.operators.astrodynamics.config import AstrodynamicsControllerConfig
from hamilton.operators.database.client import DBClient


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

    async def _get_earth_satellite(self, sat_id: str) -> EarthSatellite:
        # Fetch from cached EarthSatellite objects
        if sat_id in self.satellites:
            satellite = self.satellites[sat_id]
        # Otherwise, create new EarthSatellite and cache it
        else:
            await self.db.start()
            satellite_record = await self.db.query_record(sat_id)
            tle_line_1 = satellite_record["tle1"]
            tle_line_2 = satellite_record["tle2"]
            satellite = EarthSatellite(line1=tle_line_1, line2=tle_line_2)
            self.satellites[sat_id] = satellite

        return satellite

    async def get_kinematic_state(self, sat_id=None, time=None) -> dict:
        """Calculate observational params for single space object at a given time

        Args:
            sat_id: satnogs satellite identifier
            time: time to evaluate TLE at, defaults to current UTC time

        Returns: dict, observational params (az, el, az_rate, el_rate, range, rel_vel)
        """
        # Default to current time if not provided
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

        return kinematic_state

    async def get_aos_los(self, sat_id, time=None, delta_t=12) -> dict[str, dict[str, datetime]]:
        """Calculate acquisition of signal (AOS) and loss of signal (LOS) times

        Args:
            sat_id: satnogs satellite identifier
            time: time to evaluate TLE at, defaults to current time
            delta_t: offset from `time` by which to compute next AOS/LOS (hours)
        Returns:
            event_map: dict(str, datetime)
            Event map:
            * aos — Satellite rose above ``altitude_degrees``.
            * tca — Satellite culminated and started to descend again.
            * los — Satellite fell below ``altitude_degrees``.
        """
        # offset from `time` by which to compute next AOS and LOS
        delta_t = timedelta(hours=delta_t)

        if time is None:
            time = datetime.now(tz=timezone.utc)
        t0 = self._timescale.from_datetime(time)  # search results from now - 5 minutes
        t1 = self._timescale.from_datetime(time + delta_t)  # search up to +delta_t hours later

        satellite = await self._get_earth_satellite(sat_id=sat_id)
        times, events = satellite.find_events(self._sensor, t0=t0, t1=t1, altitude_degrees=self.min_el)
        times = [t.utc_datetime() for t in times]
        event_map = defaultdict(list)
        event_key_remap = {0: "aos", 1: "tca", 2: "los"}
        for t, event in zip(times, events):
            event_map[event_key_remap[int(event)]].append(t)

        full_event_map = {key: {"time": None, "kinematic_state": None} for key in ["aos", "tca", "los"]}

        for key in full_event_map.keys():
            if event_map[key]:
                time = event_map[key][0]  # Here we only take the first occurance
                kinematic_state = await self.get_kinematic_state(sat_id, time=time)
                full_event_map[key] = {"time": time, "kinematic_state": kinematic_state}

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
        # Compute AOS and LOS if not provided
        if aos is None or los is None:
            event_map = await self.get_aos_los(sat_id)
            aos = event_map["aos"]["time"]
            los = event_map["los"]["time"]

        num_samples = 20
        orbit = {"az": [], "el": [], "time": []}

        if (aos and los) and (aos < los):
            aos = self.local_to_utc(aos)
            los = self.local_to_utc(los)
            delta = los - aos
            interval = delta / (num_samples - 1)
            for i in range(num_samples):
                t = aos + interval * i
                obs_params = await self.get_kinematic_state(sat_id, t)
                orbit["az"].append(obs_params["az"])
                orbit["el"].append(obs_params["el"])
                orbit["time"].append(self.utc_to_local(t).strftime("%m-%d %H:%M:%S"))
        return orbit

    async def precompute_orbit(self, sat_id: str) -> None:
        """Precompute space object orbit trajectory and AOS, TCA, LOS parameters"""
        time = datetime.now(tz=timezone.utc)
        event_map = await self.get_aos_los(sat_id=sat_id, time=time)
        aos = self.utc_to_local(event_map["aos"][0]) if event_map["aos"] else None
        tca = self.utc_to_local(event_map["tca"][0]) if event_map["tca"] else None
        los = self.utc_to_local(event_map["los"][0]) if event_map["los"] else None
        # add to aos/los dict
        self.aos_los[sat_id] = {"aos": aos, "tca": tca, "los": los}
        # add orbit to dict
        self.orbits[sat_id] = await self.get_interpolated_orbit(sat_id, aos, los)

    @staticmethod
    def utc_to_local(time, tz="HST"):
        local_timezone = pytz.timezone(tz)
        return time.replace(tzinfo=pytz.utc).astimezone(local_timezone)

    @staticmethod
    def local_to_utc(time):
        return time.astimezone(timezone.utc)
