from datetime import datetime, timezone, timedelta
from collections import defaultdict

import numpy as np
from numpy import ndarray
from skyfield.api import EarthSatellite, load, wgs84
import pytz

from hamilton.db.gen_sat_db import get_cached_db as get_satcom_db
from hamilton.db.gen_sat_db import generate_db as generate_satcom_db

LATTITUDE = 20.7464000000
LONGITUDE = -156.4314700000
ALTITUDE = 103.8000000000  # (meters)


class SpaceObjectTracker:
    def __init__(
        self, sat_db="./db/satcom.json", sensor_LLA=(LATTITUDE, LONGITUDE, ALTITUDE)
    ):
        self._root_sat_db = get_satcom_db()
        self._max_space_objects = float("inf")
        # self._max_space_objects = 100
        self._timescale = load.timescale()
        self._params_update_time = None  # all observational params
        self._db_update_time = None
        self._aos_los_update_time = None

        self._sensor = wgs84.latlon(
            latitude_degrees=sensor_LLA[0],
            longitude_degrees=sensor_LLA[1],
            elevation_m=sensor_LLA[2],
        )
        self.min_el = 10  # minimum observational elevation (deg)

        self.aos_los = dict()
        self.orbits = dict()
        # self.update_all_aos_los()
        self.obs_params = dict()
        # self.update_all_observational_params()

    def update_database_from_remote(self):
        """Update database (sats, tles, txs) from remote server"""
        self._root_sat_db = generate_satcom_db(use_cache=False)
        self._db_update_time = datetime.now(tz=timezone.utc)

    def update_all_observational_params(self) -> dict:
        """Update all space object observational parameters (az, el, rel velocity, etc.)"""

        time = datetime.now(tz=timezone.utc)
        self._params_update_time = time

        for i, sat in enumerate(self._root_sat_db):
            if i < self._max_space_objects:
                # if sat not in self.obs_params:
                # print(f"Adding new space object to track:{self._root_sat_db[sat]['name']}")
                self.obs_params[sat] = self.calculate_observational_params(
                    sat_id=sat, time=time
                )

                # if aos/los is over 30 minutes old, reupdate
                if self._aos_los_update_time < (time - timedelta(minutes=30)):
                    self.update_all_aos_los()

                self.obs_params[sat].update(self.aos_los[sat])

    def calculate_observational_params(
        self, sat_id=None, time=None, norad_id=None
    ) -> dict:
        """Calculate observational params for single space object at a given time

        Args:
            sat_id: satnogs satellite identifier
            time: time to evaluate TLE at, defaults to current time
            norad_id: identify satellite by norad_id instead of satnogs id

        Returns: dict, observational params (az, el, az_rate, el_rate, range, rel_vel)
        """
        # search for norad id within root database if required
        if sat_id is None and norad_id is not None:
            for k, v in self._root_sat_db.items():
                if norad_id == v["norad_cat_id"]:
                    sat_id = k

        if time is None:
            time_scale = self._timescale.from_datetime(datetime.now(tz=timezone.utc))
        else:
            time_scale = self._timescale.from_datetime(time)

        tle_line_1 = self._root_sat_db[sat_id]["tle1"]
        tle_line_2 = self._root_sat_db[sat_id]["tle2"]
        satellite = EarthSatellite(line1=tle_line_1, line2=tle_line_2)
        params = (
            (satellite - self._sensor)
            .at(time_scale)
            .frame_latlon_and_rates(self._sensor)
        )

        el = params[0].degrees
        az = params[1].degrees
        range_ = params[2].km
        el_rate = params[3].degrees.per_second
        az_rate = params[4].degrees.per_second
        range_rate = params[5].km_per_s

        obs_params = {
            "az": az,
            "el": el,
            "az_rate": az_rate,
            "el_rate": el_rate,
            "range": range_,
            "rel_vel": range_rate,
            "time": time,
        }

        return obs_params

    def get_all_obs_params(self, sat_name=True, norad_id=True):
        """Return all observational parameters from last update.

        Args:
            sat_name: if true, include satname in output
            norad_id: if true, include norad id in output

        Returns: dict, observational params (az, el, etc.)
        """
        obs_params = self.obs_params
        if not sat_name and not norad_id:
            return obs_params
        else:
            for k in obs_params:
                if sat_name:
                    obs_params[k].update(
                        {
                            "name": self._root_sat_db[k]["name"],
                        }
                    )
                if norad_id:
                    obs_params[k].update(
                        {
                            "norad_id": self._root_sat_db[k]["norad_cat_id"],
                        }
                    )
        return obs_params

    def get_aos_los(self, sat_id, time=None, delta_t=12):
        """Cacluate acquisition of signal (AOS) and loss of signal (LOS) times

        Args:
            sat_id: satnogs satellite identifier
            time: time to evaluate TLE at, defaults to current time
            delta_t: offset from `time` by which to compute next AOS/LOS (hours)
        Returns:
            aos, los: datetime times
        """
        # offset from `time` by which to compute next AOS and LOS
        delta_t = timedelta(hours=delta_t)

        if time is None:
            time = datetime.now(tz=timezone.utc)
        t0 = self._timescale.from_datetime(time - timedelta(minutes=5)) # search results from now - 5 minutes
        t1 = self._timescale.from_datetime(time + delta_t) # search up to +delta_t hours later

        tle_line_1 = self._root_sat_db[sat_id]["tle1"]
        tle_line_2 = self._root_sat_db[sat_id]["tle2"]
        satellite = EarthSatellite(line1=tle_line_1, line2=tle_line_2)
        times, events = satellite.find_events(
            self._sensor, t0=t0, t1=t1, altitude_degrees=self.min_el
        )
        times = [t.utc_datetime() for t in times]
        event_map = defaultdict(list)
        for t, event in zip(times, events):
            event_map[event].append(t)
        return event_map

    def get_aos_los_coordinates(self, sat_id, **kwargs):
        """Calculate observational params associated with AOS time and LOS time"""
        # gather aos, los times
        event_map = self.get_aos_los(sat_id, **kwargs)
        aos = event_map[0][0] if event_map[0] else None
        los = event_map[2][0] if event_map[2] else None

        if aos is None or los is None:
            return {}, {}

        # compute parameters based on these times
        aos_obs_params = self.calculate_observational_params(sat_id, time=aos)
        los_obs_params = self.calculate_observational_params(sat_id, time=los)

        return aos_obs_params, los_obs_params


    def update_all_aos_los(self):
        """Update all space object AOS, TCA, and LOS parameters"""
        time = datetime.now(tz=timezone.utc)
        self._aos_los_update_time = time
        print("Updating all AOS, TCA, and LOS parameters")
        for i, sat in enumerate(self._root_sat_db):
            if i < self._max_space_objects:
                event_map = self.get_aos_los(sat_id=sat, time=time)
                aos = self.utc_to_local(event_map[0][0]) if event_map[0] else None
                tca = self.utc_to_local(event_map[1][0]) if event_map[1] else None
                los = self.utc_to_local(event_map[2][0]) if event_map[2] else None
                # add to aos/los dict
                self.aos_los[sat] = {"aos": aos, "tca": tca, "los": los}
                # add orbit to dict
                self.orbits[sat] = self.get_interpolated_orbit(sat, aos, los)

    def get_interpolated_orbit(self, sat_id, aos, los):
        """Calculate orbital path within observational window (AOS-LOS)

        Args:
            sat_id: satnogs satellite identifier
            aos: datetime utc, AOS
            los: datetime utc, LOS

        Returns:
            orbit: dict of lists of az, el, and times representing interpolated orbit
        """
        orbit = {"az": [], "el": [], "time": []}
        num_samples = 20
        if (aos and los) and (aos < los):
            aos = self.local_to_utc(aos)
            los = self.local_to_utc(los)
            delta = los - aos
            interval = delta / (num_samples - 1)
            for i in range(num_samples):
                t = aos + interval * i
                obs_params = self.calculate_observational_params(sat_id, t)
                orbit["az"].append(obs_params["az"])
                orbit["el"].append(obs_params["el"])
                orbit["time"].append(self.utc_to_local(t).strftime("%m-%d %H:%M:%S"))
        return orbit

    @staticmethod
    def utc_to_local(time, tz="HST"):
        """Convert UTC datetime to local datetime

        Args:
            time: datetime object in UTC timezone
            tz: pytz timezone string identifier
        Returns:
            local_time: local datetime object
        """
        local_timezone = pytz.timezone(tz)
        return time.replace(tzinfo=pytz.utc).astimezone(local_timezone)

    @staticmethod
    def local_to_utc(time):
        return time.astimezone(timezone.utc)


if __name__ == "__main__":
    from pprint import pp

    so_tracker = SpaceObjectTracker()
    sat_id = "AWRD-0316-6644-2878-7013"
    # sat_id = "LSCG-5988-6402-6624-6585"
    # events = so_tracker.get_aos_los(sat_id)
    pp(so_tracker.aos_los)
    pp(so_tracker.orbits)
    # print(datetime.now(tz=timezone.utc))
    # print(so_tracker.utc_to_local(datetime.now(tz=timezone.utc)))
    # import ipdb; ipdb.set_trace()
