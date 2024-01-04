"""
Manual interface for satellite tracking based on TLE.

1. Update SATCOM database with latest space object states
2. Propagate TLE to obtain local az/el coordinates for future LEO pass
3. Track satellite given satellite ID, until minimum elevation reached or aborted
"""

import logging
import threading
import time
import argparse
import signal
import sys
import rot2prog
from hamilton.space_object_tracker import SpaceObjectTracker
import traceback
import numpy as np


# Configure logging for debug information
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

shutdown_event = threading.Event()  # Event to signal shutdown

class InvalidOrbit(Exception):
    pass

class TrackingThread(threading.Thread):
    def __init__(self, rot, so_tracker, sat_id, interval=1, min_elevation=10, dry_run=False):
        super().__init__()
        self.rot = rot
        self.so_tracker = so_tracker
        self.sat_id = sat_id
        self.interval = interval  # Interval between tracking commands (sec)
        self.min_elevation = min_elevation  # Minimum elevation threshold (deg)
        self.dry_run = dry_run
        self._stop_event = threading.Event()
        self.cw = self.cw_init()

    @staticmethod
    def clockwise_angle(phi):
        if (phi > 270) and (phi < 360):
            return phi
        else:
            phi += 360
            return phi

    @staticmethod
    def counterclockwise_angle(phi):
        if (phi < 270) and (phi > 0):
            return phi
        else:
            phi -= 360
            return phi

    def cw_init(self):
        """Based on orbital path, determine if initial rotors direction should proceed clockwise or counterclockwise"""
        # ensure orbit is valid, i.e., observational parameters are non null
        aos_obs_params, los_obs_params = self.so_tracker.get_aos_los_coordinates(sat_id=self.sat_id)
        assert bool(aos_obs_params) and bool(los_obs_params), "No AOS/LOS observational parameters available"

        # acquire AOS/LOS angular parameters
        # note: azimuth from obs_params always in [0, 360]
        az_aos = aos_obs_params["az"]
        az_rate_aos = aos_obs_params["az_rate"]
        az_los = los_obs_params["az"]
        clockwise_orbit = az_rate_aos > 0

        # compute maximum angular distance for clockwise rotor initialization
        az_aos_cw = abs(270 - self.clockwise_angle(az_aos))
        az_los_cw = abs(270 - self.clockwise_angle(az_los))
        az_cw_max = max(az_aos_cw, az_los_cw)

        # compute maximum angular distance for counterclockwise rotor initialization
        az_aos_ccw = abs(270 - self.counterclockwise_angle(az_aos))
        az_los_ccw = abs(270 - self.counterclockwise_angle(az_los))
        az_ccw_max = max(az_aos_ccw, az_los_ccw)

        # select initial direction based on minimum arc length
        cw_init = az_cw_max < az_ccw_max

        # determine if clockwise init is valid
        valid_aos_cw = (self.clockwise_angle(az_aos) >= 0) and (self.clockwise_angle(az_aos) <= 540)
        valid_los_cw = (self.clockwise_angle(az_los) >= 0) and (self.clockwise_angle(az_los) <= 540)

        # determine if counterclockwise init is valid
        valid_aos_ccw = (self.counterclockwise_angle(az_aos) >= 0) and (self.counterclockwise_angle(az_aos) <= 540)
        valid_los_ccw = (self.counterclockwise_angle(az_los) >= 0) and (self.counterclockwise_angle(az_los) <= 540)

        # ensure the orbit is valid in either rotor intialization
        if not (valid_aos_cw and valid_los_cw and valid_aos_ccw and valid_los_ccw):
            raise InvalidOrbit("Neither cw or ccw rotor initialization yields a valid orbit!")

        if cw_init:
            if (valid_aos_cw and valid_los_cw):
                logger.info("Initial rotation direction: cw")
                return True
            else:
                logger.info("Invalid cw orbit. Initial rotation direction: ccw")
                return False
        else:
            if (valid_aos_ccw and valid_los_ccw):
                logger.info("Initial rotation direction: ccw")
                return False
            else:
                logger.info("Invalid ccw orbit. Initial rotation direction: cw")
                return True

    def run(self):
        while not shutdown_event.is_set():
            try:
                below_threshold = self.track_satellite()
                if below_threshold:
                    self.stop()
            except SystemExit:
                break  # Exit the loop if a SystemExit exception is caught
            except Exception as e:
                logger.error(f"Error in tracking: {e}")
                logger.debug(traceback.format_exc())
            time.sleep(self.interval)

    def stop(self):
        self._stop_event.set()
        self.rot.stop()  # Ensure hardware is properly shut down

    def track_satellite(self):
        # Calculate and set observational parameters
        obs_params = self.so_tracker.calculate_observational_params(sat_id=self.sat_id)
        az_so, el_so = obs_params["az"], obs_params["el"]

        if self.cw:
            az_so = self.clockwise_angle(az_so)
        else:
            az_so = self.counterclockwise_angle(az_so)

        assert az_so >= 0 and az_so <= 540, f"AZ_SO with value {az_so} not in range [0, 540]"

        # Check if elevation is below minimum threshold
        if el_so < self.min_elevation:
            logger.info(f"Elevation {el_so} below threshold {self.min_elevation}. Tracking disabled.")
        else:
            if self.dry_run:
                logger.info(f"Dry Run: Command issued - rot.set({az_so}, {el_so})")
            else:
                self.rot.set(az_so, el_so)

        # time.sleep(min(1.0, self.interval))  # Short delay for rotor movement

        az_rot, el_rot = self.rot.status()
        az_err = az_so - az_rot
        el_err = el_so - el_rot

        # Logging the tracking information
        logger.info(
            f"ID: {self.sat_id}, AZ_SO: {az_so:<6.2f}, EL_SO: {el_so:<6.2f}, "
            f"AZ_ROT: {az_rot:<6.2f}, EL_ROT: {el_rot:<6.2f}, "
            f"AZ_ERR: {az_err:<6.2f}, EL_ERR: {el_err:<6.2f}"
        )

        return False  # Continue tracking


def signal_handler(sig, frame):
    logger.info("Aborting Satellite Tracking...")
    shutdown_event.set()  # Signal all threads to shut down
    tracking_thread.stop()
    tracking_thread.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Satellite Tracker CLI")
    parser.add_argument("--sat_id", required=False, help="Satnogs UUID to track")
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="Emulate tracking sequence without mechanically moving rotors",
    )
    args = parser.parse_args()

    # Connect to MD-01
    try:
        logger.info("Connecting to MD-01")
        rot = rot2prog.ROT2Prog("/dev/usbttymd01")
        logger.info("Successfully connected to MD-01")
        logger.info(f"Rotator status: {rot.status()}")
    except Exception as e:
        logger.error(f"Error in ROT2Prog: {e}")

    # Initialize state estimator and update satcom satabase
    so_tracker = SpaceObjectTracker()
    # so_tracker.update_database_from_remote()

    # Start the satellite tracking thread
    tracking_thread = TrackingThread(rot=rot, so_tracker=so_tracker, sat_id=args.sat_id, dry_run=args.dry_run)

    signal.signal(signal.SIGINT, signal_handler)  # Handle Ctrl+C signal
    tracking_thread.start()

    while not shutdown_event.is_set():
        time.sleep(1)  # Main thread continues to run until signaled to stop

    # Any final cleanup can go here
    logger.info("Program terminated")
