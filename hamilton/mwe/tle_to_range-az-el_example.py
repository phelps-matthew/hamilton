"""From TLE compute local Az/El, Az/El rates, and range rates (relative velocity)"""
from __future__ import annotations

# Standard Library Imports
from datetime import datetime, timezone

# Third Party Imports
import numpy as np
from skyfield.api import EarthSatellite, load, wgs84
from numpy import ndarray


TIMESCALE = load.timescale()


def tle2razel(line1: str, line2: str, sensor_lla: ndarray, date_time: datetime | None = None):
    """Convert a tle 2 range

    Args:
        line1 (``str``): first line of TLE
        line2 (``str``): second line of TLE
        sensor_lla (ndarray): 3x1 LLA sensor position vector position (deg, deg, meters)
        date_time (datetime, Optional): time of conversion. If not set, defaults to TLE time

    Returns:
        ndarray: 6x1 razel and rates observation vector
            azimuth (float): topocentric horizon azimuth angle (degrees)
            elevation (float): topocentric horizon elevation angle (degrees)
            range (float): topocentric horizon range to target (km)
            azimuth_rate (float): topocentric horizon azimuth angular rate (degrees/sec)
            elevation_rate (float): topocentric horizon elevation angular rate (degrees/sec)
            range_rate (float): topocentric horizon range rate of target (km/sec)
    """
    satellite = EarthSatellite(line1=line1, line2=line2)

    if date_time:
        if not date_time.tzinfo:
            date_time = datetime(
                year=date_time.year,
                month=date_time.month,
                day=date_time.day,
                hour=date_time.hour,
                minute=date_time.minute,
                second=date_time.second,
                tzinfo=timezone.utc,
            )
        time_scale = TIMESCALE.from_datetime(date_time)
    else:
        time_scale = satellite.ts

    # Compute Range Rate
    ground = wgs84.latlon(
        latitude_degrees=sensor_lla[0],
        longitude_degrees=sensor_lla[1],
        elevation_m=sensor_lla[2],
    )
    pos = (satellite - ground).at(time_scale)
    (
        az,
        el,
        ra,
        az_rate,
        el_rate,
        ra_rate,
    ) = pos.frame_latlon_and_rates(ground)

    return np.array(
        [
            az.degrees,
            el.degrees,
            ra.km,
            az_rate.degrees.per_second,
            el_rate.degrees.per_second,
            ra_rate.km_per_s,
        ]
    )


if __name__ == "__main__":
    import time

    # Sample TLE
    line1 = "1 41168U 15077C   23137.26416622  .00111382  00000+0  17513-2 0  9999"
    line2 = "2 41168  14.9862 103.0069 0005705 291.3486  68.6231 15.51726067411496"

    # Local sensor position
    sensor_lla = [30, 30, 3000]

    # TLE propagated with SPG4
    satellite = EarthSatellite(line1=line1, line2=line2)

    # World Geodetic System. Object admits map of (lat, long, elev) to Earth centered, Earth fixed
    # (x,y,z)
    ground = wgs84.latlon(
        latitude_degrees=sensor_lla[0],
        longitude_degrees=sensor_lla[1],
        elevation_m=sensor_lla[2],
    )

    for i in range(100):
        time_scale = TIMESCALE.from_datetime(datetime.now(tz=timezone.utc))
        position = (satellite - ground).at(time_scale).frame_latlon_and_rates(ground)
        print(
            [
                position[0].degrees,
                position[1].degrees,
                position[2].km,
                position[3].degrees.per_second,
                position[4].degrees.per_second,
                position[5].km_per_s,
            ],
            sep="\n",
        )
        time.sleep(1)
