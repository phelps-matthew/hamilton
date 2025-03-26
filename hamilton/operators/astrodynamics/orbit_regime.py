import numpy as np
from numpy.typing import ArrayLike
from datetime import datetime, timedelta, timezone
from typing import cast
from sgp4.api import Satrec, jday

DAYS2SEC = 86400
EARTH_RADIUS = 6378.1363  # Earth Radius (km)
EARTH_MU = 398600.4415  # km^3/sec^2


def _is_between(value: float, minimum: float, maximum: float) -> bool:
    """Check that a value is between a min and a max.

    Args:
        value (float): number to be check
        minimum (float): minimum value
        maximum (float): maximum value

    Returns:
        bool: True if value is between min and max
    """
    return minimum <= value <= maximum


def check_orbital_regime(
    perigee: float,
    apogee: float,
    altitude: float,
) -> dict:
    """Get the orbital regime of an RSO.

    Args:
        perigee (float): Lowest altitude in an orbit
        apogee (float): Highest altitude in an orbit
        altitude (float): Current altitude in an orbit

    Returns:
        dict: Orbital regime
    """
    orbit = {}
    if _is_between(perigee, 2000, 8000) and _is_between(apogee, 30000, 40000):
        orbit["orbit_type"] = "MOLNIYA"
    elif _is_between(perigee, 0, 1000) and _is_between(apogee, 0, 1000):
        orbit["orbit_type"] = "LILO"  # LEO
    elif _is_between(perigee, 0, 1000) and _is_between(apogee, 550, 2000):
        orbit["orbit_type"] = "LTO"  # LEO
    elif _is_between(perigee, 0, 2000) and _is_between(apogee, 2000, 30000):
        orbit["orbit_type"] = "MTO"  # LEO -> MEO
    elif _is_between(perigee, 0, 2000) and _is_between(apogee, 30000, 40000):
        orbit["orbit_type"] = "GTO"  # LEO -> GEO
    elif _is_between(perigee, 0, 2000) and apogee >= 40000:
        orbit["orbit_type"] = "HTO"  # LEO -> xGEO
    elif _is_between(perigee, 8000, 30000) and _is_between(apogee, 30000, 40000):
        orbit["orbit_type"] = "GTH"  # MEO -> GEO
    elif _is_between(perigee, 30000, 40000) and apogee >= 40000:
        orbit["orbit_type"] = "HTH"  # MEO/GEO -> xGEO
    elif _is_between(perigee, 550, 2000) and _is_between(apogee, 550, 2000):
        orbit["orbit_type"] = "LEO"
    elif _is_between(perigee, 2000, 30000) and _is_between(apogee, 2000, 30000):
        orbit["orbit_type"] = "MEO"
    elif _is_between(perigee, 30000, 40000) and _is_between(apogee, 30000, 40000):
        orbit["orbit_type"] = "GEO"
    # elif perigee >= 40000 and apogee >= 40000:
    else:
        orbit["orbit_type"] = "XGEO"

    if altitude <= 0.0:
        raise ValueError("RSO taking a swim")

    if altitude < 2000.0:
        orbit["regime"] = "LEO"
    elif altitude < 30000.0:
        orbit["regime"] = "MEO"
    elif altitude < 40000.0:
        orbit["regime"] = "GEO"
    else:
        orbit["regime"] = "XGEO"

    return orbit


def check_tle_orbital_regime(
    line1: str, line2: str, date_time: datetime | None = None
) -> dict[str, str]:
    """Check the Orbital Regime of an RSO with a given TLE.

    Args:
        line1 (str): First line of a TLE
        line2 (str): Second line of a TLE
        date_time (datetime, optional): time to propagate to.

    Returns:
        Dict:
            orbit_type (str): Orbit type (Transfer, Molniya, stable)
            regime (str): Orbital regime of RSO at the present time. LEO, MEO, GEO, XGEO
    """
    # Get satellite state at epoch
    if date_time is None:
        date_time = tle_time_to_datetime(line1)
    satellite = Satrec.twoline2rv(line1, line2)
    jd, fr = jday(
        year=date_time.year,
        mon=date_time.month,
        day=date_time.day,
        hr=date_time.hour,
        minute=date_time.minute,
        sec=date_time.second + date_time.microsecond * 1e-6,
    )
    _, r_teme, v_teme = satellite.sgp4(jd, fr)
    _raise_if_invalid_state(r_teme, v_teme)

    # True Equator, Mean Equinox state vector
    state_vector_teme = np.concatenate((r_teme, v_teme))

    # Get RSO altitude from state vector
    rso_altitude = get_altitude(state_vector_teme)

    # Parse mean motion, and convert to semi-major axis
    mean_motion = 2 * np.pi * float(line2[52:63]) / DAYS2SEC  # rads/sec
    sma = (mean_motion**2 / EARTH_MU) ** (1 / 3)

    # Parse eccentricity
    eccentricity = float(f"0.{line2[26:33]}")

    # Get apogee and perigee from orbital elements
    apogee, perigee = get_apogee_and_perigee(
        semimajor_axis=sma, eccentricity=eccentricity
    )

    return check_orbital_regime(perigee, apogee, rso_altitude)


def tle_time_to_datetime(line1: str) -> datetime:
    """Convert the time specified in a TLE to a datetime object.

    Args:
        line1 (str): First line of a TLE

    Returns:
        datetime: Time specified in the TLE, UTC time zone.
    """
    year_day, day_frac = line1[18:32].split(".")
    return datetime.strptime(year_day, "%y%j").replace(tzinfo=timezone.utc) + timedelta(
        seconds=float(f"0.{day_frac}") * DAYS2SEC
    )


def _raise_if_invalid_state(position: ArrayLike, velocity: ArrayLike) -> None:
    """Raises a `RuntimeError` if either the position or velocity returned from TLE propagation contains NaN.

    Args:
        position (ArrayLike): 3x1 array of Earth-centered satellite position
        velocity (ArrayLike): 3x1 array of Earth-centered satellite velocity
    """
    if np.any(np.isnan(position)) or np.any(np.isnan(velocity)):
        raise RuntimeError("TLE cannot be propagated -- likely xGEO.")


def get_altitude(state_vector: ArrayLike) -> float:
    """Calculate the altitude of an ECI state vector.

    Args:
        state_vector (ArrayLike): 6x1 ECI state vector (km; km/s)

    Returns:
        float: Orbital altitude (kilometers)
    """
    return cast(float, np.linalg.norm(state_vector[:3]) - EARTH_RADIUS)


def get_apogee_and_perigee(semimajor_axis: float, eccentricity: float):
    """Calculate Apogee and Perigee of an orbit.

    Args:
        semimajor_axis (float): RSO SMA (km)
        eccentricity (float): RSO ECC (unitless)

    Returns:
        tuple:
            float: apogee (km)
            float: perigee (km)
    """
    apogee = semimajor_axis * (1 + eccentricity) - EARTH_RADIUS
    perigee = semimajor_axis * (1 - eccentricity) - EARTH_RADIUS
    return apogee, perigee
