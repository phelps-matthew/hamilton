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


class TrackingThread(threading.Thread):
    def __init__(self, rot, so_tracker, sat_id, interval=3, min_elevation=10, dry_run=False):
        super().__init__()
        self.rot = rot
        self.so_tracker = so_tracker
        self.sat_id = sat_id
        self.interval = interval  # Interval between tracking commands (sec)
        self.min_elevation = min_elevation  # Minimum elevation threshold (deg)
        self.dry_run = dry_run
        self._stop_event = threading.Event()
        self.wrap = self.add_wrap()

    @classmethod
    def angular_distance(angle1, angle2, clockwise):
        """
        Compute the absolute angular distance between two angles given an orientation.

        Parameters:
        angle1 (float): The first angle in degrees.
        angle2 (float): The second angle in degrees.
        clockwise (bool): True for clockwise, False for counterclockwise.

        Returns:
        float: The absolute angular distance in degrees.
        """
        if clockwise:
            if angle2 < angle1:
                return 360 - angle1 + angle2
            else:
                return angle2 - angle1
        else:
            if angle2 > angle1:
                return 360 - angle2 + angle1
            else:
                return angle1 - angle2

    def add_wrap(self):
        """Based on orbital path, determine if rotors positions should wrap past 360 deg or not"""
        # ensure orbit is valid, i.e., observational parameters are non null
        aos_obs_params, los_obs_params = self.so_tracker.get_aos_los_coordinates(sat_id=self.sat_id)
        assert bool(aos_obs_params) and bool(los_obs_params), "No AOS/LOS observational parameters available"

        # acquire AOS/LOS angular parameters
        # note: azimuth from obs_params always in [0, 360]
        az_aos = aos_obs_params["az"]
        az_rate_aos = aos_obs_params["az_rate"]
        az_los = los_obs_params["az"]
        clockwise = az_rate_aos > 0

        # compare angular distance relative to home position (270 deg) with and without 2pi wrap
        total_angular_dist = max(
            self.angular_distance(270, az_aos, clockwise), self.angular_distance(270, az_los, clockwise)
        )
        total_angular_dist_wrapped = max(
            self.angular_distance(270, az_aos + 360, clockwise), self.angular_distance(270, az_los + 360, clockwise)
        )
        # if true, add 2*pi to az coordinate
        add_wrap = total_angular_dist > total_angular_dist_wrapped

        if add_wrap:
            logger.info("Adding 2 pi wrap to azimuth coordinates")

        return add_wrap

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

        if self.wrap:
            az_so += 360

        # Check if elevation is below minimum threshold
        if el_so < self.min_elevation:
            logger.info(f"Elevation {el_so} below threshold {self.min_elevation}. Tracking disabled.")
        else:
            if self.dry_run:
                logger.info(f"Dry Run: Command issued - rot.set({az_so}, {el_so})")
            else:
                self.rot.set(az_so, el_so)

        time.sleep(1.0)  # Short delay for rotor movement

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
