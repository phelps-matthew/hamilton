"""Compute astrodynamic parameters associated with space objects. Based on TLE's for now."""

import json
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import pika
import pytz
from skyfield.api import EarthSatellite, load, wgs84

from hamilton.astrodynamics.config import Config
from hamilton.common.utils import CustomJSONEncoder


class SpaceObjectTracker:
    def __init__(self, config: Config):
        self.config = config

        # DB query init
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.config.RABBITMQ_SERVER))
        self.channel = self.connection.channel()
        result = self.channel.queue_declare(queue="", exclusive=True)
        self.callback_queue = result.method.queue
        self.channel.basic_consume(queue=self.callback_queue, on_message_callback=self._db_on_response, auto_ack=True)
        self.response = None
        self.corr_id = None

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

    def _db_on_response(self, ch, method, properties, body):
        if self.corr_id == properties.correlation_id:
            self.response = json.loads(body)

    def _db_query(self, sat_id: str) -> dict:
        message = {"command": "query", "parameters": {"sat_id": sat_id}}
        self.response = None
        self.corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange="",
            routing_key=self.config.DB_COMMAND_QUEUE,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=json.dumps(message, cls=CustomJSONEncoder),
        )

        while self.response is None:
            self.connection.process_data_events()

        return self.response

    def _get_earth_satellite(self, sat_id: str) -> EarthSatellite:
        # Fetch from cached EarthSatellite objects
        if sat_id in self.satellites:
            satellite = self.satellites[sat_id]
        # Otherwise, create new EarthSatellite and cache it
        else:
            satellite_record = self._db_query(sat_id)
            tle_line_1 = satellite_record["tle1"]
            tle_line_2 = satellite_record["tle2"]
            satellite = EarthSatellite(line1=tle_line_1, line2=tle_line_2)
            self.satellites[sat_id] = satellite

        return satellite

    def get_kinematic_state(self, sat_id=None, time=None) -> dict:
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

        satellite = self._get_earth_satellite(sat_id)
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
        t0 = self._timescale.from_datetime(time - timedelta(minutes=5))  # search results from now - 5 minutes
        t1 = self._timescale.from_datetime(time + delta_t)  # search up to +delta_t hours later

        satellite = self._get_earth_satellite(sat_id=sat_id)
        times, events = satellite.find_events(self._sensor, t0=t0, t1=t1, altitude_degrees=self.min_el)
        times = [t.utc_datetime() for t in times]
        event_map = defaultdict(list)
        for t, event in zip(times, events):
            event_map[event].append(t)
        return event_map

    def get_interpolated_orbit(self, sat_id, aos, los):
        """Calculate orbital path within observational window (AOS-LOS)

        Args:
            sat_id: satnogs satellite identifier
            aos: datetime utc, AOS
            los: datetime utc, LOS

        Returns:
            orbit: dict of lists of az, el, and times representing interpolated orbit
        """
        num_samples = 20
        orbit = {"az": [], "el": [], "time": []}
        if (aos and los) and (aos < los):
            aos = self.local_to_utc(aos)
            los = self.local_to_utc(los)
            delta = los - aos
            interval = delta / (num_samples - 1)
            for i in range(num_samples):
                t = aos + interval * i
                obs_params = self.get_kinematic_state(sat_id, t)
                orbit["az"].append(obs_params["az"])
                orbit["el"].append(obs_params["el"])
                orbit["time"].append(self.utc_to_local(t).strftime("%m-%d %H:%M:%S"))
        return orbit

    def precompute_orbit(self, sat_id: str) -> None:
        """Precompute space object orbit trajectory and AOS, TCA, LOS parameters"""
        time = datetime.now(tz=timezone.utc)
        event_map = self.get_aos_los(sat_id=sat_id, time=time)
        aos = self.utc_to_local(event_map[0][0]) if event_map[0] else None
        tca = self.utc_to_local(event_map[1][0]) if event_map[1] else None
        los = self.utc_to_local(event_map[2][0]) if event_map[2] else None
        # add to aos/los dict
        self.aos_los[sat_id] = {"aos": aos, "tca": tca, "los": los}
        # add orbit to dict
        self.orbits[sat_id] = self.get_interpolated_orbit(sat_id, aos, los)

    @staticmethod
    def utc_to_local(time, tz="HST"):
        local_timezone = pytz.timezone(tz)
        return time.replace(tzinfo=pytz.utc).astimezone(local_timezone)

    @staticmethod
    def local_to_utc(time):
        return time.astimezone(timezone.utc)


if __name__ == "__main__":
    from pprint import pp

    so_tracker = SpaceObjectTracker(Config)
    sat_id = "39446"
    so_tracker.precompute_orbit(sat_id=sat_id)
    pp(so_tracker.aos_los)
    pp(so_tracker.orbits)
    pp(so_tracker.satellites)
    pp(so_tracker.get_kinematic_state(sat_id))