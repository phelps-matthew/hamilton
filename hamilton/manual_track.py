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

# Configure logging for debug information
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class SatelliteTracker(threading.Thread):
    def __init__(self, rot, sat_id, interval=3, min_elevation=10, dry_run=False):
        super().__init__()
        self.rot = rot
        self.sat_id = sat_id
        self.interval = interval  # Interval between tracking commands (sec)
        self.min_elevation = min_elevation  # Minimum elevation threshold (deg)
        self.dry_run = dry_run
        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.is_set():
            try:
                below_threshold = self.track_satellite()
                if below_threshold:
                    self.stop()
            except Exception as e:
                logger.error(f"Error in tracking: {e}")
            time.sleep(self.interval)

    def stop(self):
        self._stop_event.set()
        self.rot.stop()  # Ensure hardware is properly shut down

    def track_satellite(self):
        # Calculate and set observational parameters
        obs_params = so_tracker.calculate_observational_params(self.sat_id)
        az_so, el_so = obs_params["az"], obs_params["el"]

        # Check if elevation is below minimum threshold
        if el_so < self.min_elevation:
            logger.info(
                f"Elevation {el_so} below threshold {self.min_elevation}. Stopping tracking."
            )
            return True

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
            f"AZ_SO: {az_so:<6.2f}, EL_SO: {el_so:<6.2f}, "
            f"AZ_ROT: {az_rot:<6.2f}, EL_ROT: {el_rot:<6.2f}, "
            f"AZ_ERR: {az_err:<6.2f}, EL_ERR: {el_err:<6.2f}"
        )

        return False  # Continue tracking


def signal_handler(sig, frame):
    logger.info("Stopping Satellite Tracking...")
    tracking_thread.stop()
    tracking_thread.join()
    sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Satellite Tracker CLI")
    parser.add_argument("--sat_id", required=True, help="Satellite ID to track")
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="Emulate tracking sequence without mechanically moving rotors",
    )
    args = parser.parse_args()

    # Connect to MD-01
    try:
        rot = rot2prog.ROT2Prog("/dev/usbttymd01")
        rot.status()  # Query initial status of the rotator
    except Exception as e:
        logger.error(f"Error in ROT2Prog: {e}")

    # Initialize state estimator and update satcom satabase
    so_tracker = SpaceObjectTracker()
    so_tracker.update_database_from_remote()

    # Start the satellite tracking thread
    tracking_thread = SatelliteTracker(
        rot=rot, sat_id=args.sat_id, dry_run=args.dry_run
    )
    signal.signal(signal.SIGINT, signal_handler)  # Handle Ctrl+C signal

    tracking_thread.start()
