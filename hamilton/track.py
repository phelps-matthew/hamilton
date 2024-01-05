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
import rot2prog
from hamilton.space_object_tracker import SpaceObjectTracker
import traceback


# Configure logging for debug information
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

shutdown_event = threading.Event()  # Event to signal shutdown


def signal_handler(sig, frame):
    logger.info("Aborting Satellite Tracking...")
    shutdown_event.set()  # Signal all threads to shut down
    tracking_thread.stop()
    tracking_thread.join()


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
        self.home_coords = (270, 90)
        # self.rotate_to_home()
        # self.rotate_to_aos()

    @staticmethod
    def clockwise_angle(phi):
        if (phi > 270) and (phi < 360):
            return phi
        else:
            phi += 360
            return phi

    @staticmethod
    def counterclockwise_angle(phi):
        if (phi > 270) and (phi < 360):
            phi -= 360
            return phi
        else:
            return phi

    @staticmethod
    def max_orbit_distance(angles):
        """Compute the maximum angular distance traveled in a list of ordered angles."""
        if len(angles) < 2:
            return 0  # No distance covered if there's less than two angles
        total_distance = 0
        for i in range(len(angles) - 1):
            # compute the absolute angular difference between consecutive angles
            diff = abs(angles[i + 1] - angles[i])
            # adjust the difference to be the shortest path between the angles
            if diff > 180:
                diff = 360 - diff
            total_distance += diff

        return total_distance

    def max_rotor_travel(self):
        """Given an orbital pass, compute the furthest absolute angular extent an azimuth rotor must travel"""
        # acquire aos and los times
        event_map = self.so_tracker.get_aos_los(sat_id=self.sat_id)
        aos = event_map[0][0] if event_map[0] else None
        los = event_map[2][0] if event_map[2] else None
        assert aos and los, "Invalid orbit, cannot aquire AOS and LOS"

        # acquire AOS/LOS angular parameters
        # note: azimuth from obs_params always in [0, 360]
        aos_obs_params, los_obs_params = self.so_tracker.get_aos_los_coordinates(sat_id=self.sat_id)
        assert bool(aos_obs_params) and bool(los_obs_params), "No AOS/LOS observational parameters available"
        az_rate_aos = aos_obs_params["az_rate"]
        clockwise_orbit = az_rate_aos > 0

        # compute orbit
        orbit = self.so_tracker.get_interpolated_orbit(sat_id=self.sat_id, aos=aos, los=los)
        az_list = orbit["az"]
        az_aos = orbit["az"][0]
        el_aos = orbit["el"][0]

        # compute angle from home to az_aos
        phi_aos_home_cw = self.clockwise_angle(az_aos) - 270
        phi_aos_home_ccw = self.counterclockwise_angle(az_aos) - 270

        # compute max angular extent of orbit path
        phi_orbit = self.max_orbit_distance(az_list) if clockwise_orbit else -self.max_orbit_distance(az_list)

        # compute max between initial rotor travel and full path (rotor travel + orbit path)
        # this defines the maximum angular extent traveled relative to home
        phi_max_cw = max(phi_aos_home_cw, abs(phi_aos_home_cw + phi_orbit))
        phi_max_ccw = max(abs(phi_aos_home_ccw), abs(phi_aos_home_ccw + phi_orbit))

        logger.debug(f"phi_orbit: {phi_orbit}")
        logger.debug(f"phi_aos_home_cw: {phi_aos_home_cw}")
        logger.debug(f"phi_aos_home_ccw: {phi_aos_home_ccw}")
        logger.debug(f"phi_max_cw: {phi_max_cw}")
        logger.debug(f"phi_max_ccw: {phi_max_ccw}")
        logger.debug(f"az_list: {az_list}")

        return phi_max_cw, phi_max_ccw, az_aos, el_aos

    def get_aos_rotor_angles(self):
        """Compute initial aos rotor angles for rotor prepositioning, taking into account whether to
        traverse cw or ccw relative to home."""
        phi_max_cw, phi_max_ccw, az_aos, el_aos = self.max_rotor_travel()
        if (phi_max_cw > 270) and (phi_max_ccw > 270):
            raise InvalidOrbit("Angular travel exceeds maximum for cw or ccw traversal")
        if phi_max_cw < phi_max_ccw:
            if phi_max_cw <= 270:
                logger.info("Initial rotation direction: cw ⤵")
                clockwise = True
            else:
                logger.info("Invalid cw orbit. Initial rotation direction: ccw ⤴")
                clockwise = False
        else:
            if phi_max_ccw <= 270:
                logger.info("Initial rotation direction: ccw ⤴")
                clockwise = False
            else:
                logger.info("Invalid ccw orbit. Initial rotation direction: cw ⤵")
                clockwise = True

        return (self.clockwise_angle(az_aos), el_aos) if clockwise else (self.counterclockwise_angle(az_aos), el_aos)

    def rotate_and_wait(self, az, el, angular_tolerance=0.2):
        """Rotate to a specific azimuth and elevation and wait until the position is reached."""
        try:
            if self.dry_run:
                logger.info(f"Dry Run: Command issued - rot.set({az}, {el})")
                logger.info(f"Dry Run: Simulated immediate arrival at AZ_ROT: {az}, EL_ROT: {el}")
            else:
                self.rot.set(az, el)
                while True:
                    current_az, current_el = self.rot.status()
                    logger.info(f"Status, AZ_ROT: {current_az:<6.2f}, EL_ROT: {current_el:<6.2f}")
                    if abs(current_az - az) <= angular_tolerance and abs(current_el - el) <= angular_tolerance:
                        break
                    time.sleep(1)  # Wait 1s before checking state again
        except KeyboardInterrupt:
            # Handle Ctrl+C interruption
            logger.info("Interrupt received, stopping rotator...")
            self.rot.stop()
            raise

    def rotate_to_aos(self):
        """Rotate to position ready for acquisition of signal. Must call before tracking satellite."""
        az_aos, el_aos = self.get_aos_rotor_angles()
        logger.info(f"Positioning rotator for AOS at AZ_ROT: {az_aos:<6.2f}, EL_ROT: {el_aos:<6.2f}")
        self.rotate_and_wait(az_aos, el_aos)

    def rotate_to_home(self):
        az_home, el_home = self.home_coords
        logger.info(f"Positioning rotator to home AZ_ROT: {az_home:<6.2f}, EL_ROT: {el_home:<6.2f}")
        self.rotate_and_wait(az_home, el_home)

    def track_satellite(self):
        # Calculate and set observational parameters
        obs_params = self.so_tracker.calculate_observational_params(sat_id=self.sat_id)
        az_so, el_so = obs_params["az"], obs_params["el"]

        # ensure commanded azmiuth value is within bounds
        assert (az_so >= 0) and (az_so <= 540), f"AZ_SO with value {az_so} not in range [0, 540]"

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
        logger.info(f"Rotator limits: {rot.get_limits()}")
        logger.info(f"Setting rotator limits: {rot.set_limits(0, 540, 10, 170)}")
        logger.info(f"Rotator limits: {rot.get_limits()}")
    except Exception as e:
        logger.error(f"Error in ROT2Prog: {e}")

    # Initialize state estimator and update satcom satabase
    so_tracker = SpaceObjectTracker()
    # so_tracker.update_database_from_remote()

    # Create the satellite tracking thread
    tracking_thread = TrackingThread(rot=rot, so_tracker=so_tracker, sat_id=args.sat_id, dry_run=args.dry_run)

    # Rotate to home -> aos -> track satellite
    signal.signal(signal.SIGINT, signal_handler)  # Handle Ctrl+C signal
    tracking_thread.rotate_to_home()
    tracking_thread.rotate_to_aos()
    tracking_thread.start()

    while not shutdown_event.is_set():
        time.sleep(1)  # Main thread continues to run until signaled to stop

    # Any final cleanup can go here
    logger.info("Program terminated")
