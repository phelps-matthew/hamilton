import logging
import asyncio
from hamilton.operators.mount.client import MountClient
from hamilton.operators.astrodynamics.client import AstrodynamicsClient
from hamilton.operators.tracker.config import TrackerControllerConfig
from hamilton.base.task import Task

logger = logging.getLogger(__name__)


class Tracker:
    def __init__(self, config: TrackerControllerConfig):
        self.config = config
        self.shutdown_event = asyncio.Event()
        self.min_elevation = self.config.el_min
        self.slew_interval = self.config.slew_interval
        self.is_tracking = asyncio.Event()
        self.task: Task = None
        self.aos_rotor_angles: tuple[float, float, float] | None = None
        self.sat_id: int | None = None
        try:
            self.mount = MountClient()
            self.astrodynamics = AstrodynamicsClient()
        except Exception as e:
            logger.error(f"Failed to initialize client: {e}")

    async def start(self):
        logger.info("Starting Tracker")
        try:
            await self.mount.start()
            await self.astrodynamics.start()
        except Exception as e:
            logger.error(f"Failed to start tracker clients: {e}")

    async def stop(self):
        logger.info("Stopping Tracker")
        try:
            await self.stop_tracking()
        except Exception as e:
            logger.error(f"Failed to stop tracking routine: {e}")
        try:
            await self.mount.stop()
            await self.astrodynamics.stop()
            logger.info("Tracker api successfully stopped")
        except Exception as e:
            logger.error(f"Failed to stop tracker clients: {e}")

    async def status(self):
        return {"status": "active" if self.is_tracking.is_set() else "idle"}

    async def _finish_tracking(self):
        """Stop the tracking loop and reset tracking status."""
        await self.mount.stop_rotor()
        await asyncio.sleep(self.slew_interval)
        self.is_tracking.clear()
        logger.info("Tracking successfully stopped.")

    async def stop_tracking(self):
        """Set shutdown event, stop the tracking loop and reset tracking status."""
        self.shutdown_event.set()
        await self.wait_for_tracking_complete()
        logger.info("Tracking successfully stopped.")

    async def setup_task(self, task: Task):
        """Idempotently initialize active task parameters"""
        self.task = task
        if task is not None:
            az_rate_aos = task["parameters"]["aos"]["kinematic_state"]["az_rate"]
            interpolated_orbit = task["parameters"]["interpolated_orbit"]
            self.aos_rotor_angles = AOSPath.get_aos_rotor_angles(
                az_rate_aos=az_rate_aos, interpolated_orbit=interpolated_orbit
            )
            self.sat_id = task["parameters"]["sat_id"]
        else:
            logger.error("Task is None")

    async def _slew_and_wait(self, az, el, angular_tolerance=0.3):
        """Rotate to a specific azimuth and elevation and wait until the position is reached."""
        await self.wait_for_tracking_complete()
        await self.clear_shutdown_event()
        az, el = self._safe_az_el(az, el)
        await self.mount.set(az, el)
        sleep_task = asyncio.create_task(asyncio.sleep(self.slew_interval))
        shutdown_task = asyncio.create_task(self.shutdown_event.wait())
        await asyncio.wait([sleep_task, shutdown_task], return_when=asyncio.FIRST_COMPLETED,)
        if self.shutdown_event.is_set():
            logger.info("Shutdown event triggered. Aborting slew.")
            await self._finish_tracking()
            return

        try:
            logger.info(f"Slewing to azimuth: {az}, elevation: {el}")
            self.is_tracking.set()
            while not self.shutdown_event.is_set():
                response = await self.mount.status()
                current_az, current_el = response["azimuth"], response["elevation"]
                logger.info(f"Status, az_rotator: {current_az}, el_rotator: {current_el}")
                az_err = az - current_az
                el_err = el - current_el
                if az_err >= 360:
                    az_err = az_err % 360
                if az_err <= -360:
                    az_err = az_err % -360
                if abs(az_err) <= angular_tolerance and abs(el_err) <= angular_tolerance:
                    logger.info(f"az_err: {az_err}, el_err: {el_err}")
                    break
                await asyncio.sleep(self.slew_interval)  # Wait 1s before checking state again
            logger.info("Slewing complete.")
        except Exception as e:
            logger.error(f"Unexpected error during slew: {e}")
        finally:
            await self._finish_tracking()

    async def slew_to_home(self):
        az, el = self.config.az_home, self.config.el_home
        logger.info("Slewing to home.")
        return await self._slew_and_wait(az, el)

    async def slew_to_aos(self):
        """Rotate to position ready for acquisition of signal. Must call before tracking satellite."""
        az_aos, az_aos_half, el_aos = self.aos_rotor_angles
        logger.info("Slewing to *half* AOS")
        response = await self._slew_and_wait(az_aos_half, el_aos)
        if not self.shutdown_event.is_set():
            logger.info("Slewing to *final* AOS")
            response = await self._slew_and_wait(az_aos, el_aos)
        else:
            logger.warning("Shutdown event set before slewing to AOS")
        return response

    async def track(self):
        """Track a space object until it reaches a minimum elevation or is manually stopped."""
        await self.wait_for_tracking_complete()
        await self.clear_shutdown_event()
        try:
            logger.info("Starting tracking routine")
            self.is_tracking.set()
            while not self.shutdown_event.is_set():
                kinematic_state = await self.astrodynamics.get_kinematic_state(self.sat_id)
                az, el = kinematic_state["az"], kinematic_state["el"]
                if el < self.min_elevation:
                    logger.info(f"Current elevation: {el}. Waiting for elevation to rise above {self.min_elevation}")
                    await asyncio.sleep(self.slew_interval)
                    continue
                az, el = self._safe_az_el(kinematic_state["az"], kinematic_state["el"])
                logger.info(f"Slewing to azimuth: {az}, elevation: {el}")
                await self.mount.set(az, el)
                await asyncio.sleep(self.slew_interval)
            logger.info("Tracking routine completed.")
        except Exception as e:
            logger.error(f"Unexpected error during tracking: {e}")
        finally:
            await self._finish_tracking()

    def _safe_az_el(self, az, el):
        if az < 0:
            safe_az = 0
        elif az > 540:
            safe_az = 540
        else:
            safe_az = az

        if el < self.min_elevation:
            safe_el = self.min_elevation
        elif el > 180 - self.min_elevation:
            safe_el = 180 - self.min_elevation
        else:
            safe_el = el
        return round(safe_az, 2), round(safe_el, 2)

    async def clear_shutdown_event(self):
        if self.shutdown_event is not None:
            self.shutdown_event.clear()

    async def wait_for_tracking_complete(self):
        while self.is_tracking.is_set():
            logger.info("Waiting for tracking to complete..")
            await asyncio.sleep(self.slew_interval)


class AOSPath:
    @staticmethod
    def _clockwise_angle(phi):
        if (phi > 270) and (phi < 360):
            return phi
        else:
            phi += 360
            return phi

    @staticmethod
    def _counterclockwise_angle(phi):
        if (phi > 270) and (phi < 360):
            phi -= 360
            return phi
        else:
            return phi

    @staticmethod
    def _max_orbit_distance(angles):
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

    @staticmethod
    def max_rotor_travel(az_rate_aos: float, interpolated_orbit: dict[str, float]):
        """Given an orbital pass, compute the furthest absolute angular extent an azimuth rotor must travel"""
        clockwise_orbit = az_rate_aos > 0
        az_aos = interpolated_orbit["az"][0]
        el_aos = interpolated_orbit["el"][0]
        az_list = interpolated_orbit["az"]

        # compute angle from home to az_aos
        phi_aos_home_cw = AOSPath._clockwise_angle(az_aos) - 270
        phi_aos_home_ccw = AOSPath._counterclockwise_angle(az_aos) - 270

        # compute max angular extent of orbit path
        phi_orbit = AOSPath._max_orbit_distance(az_list) if clockwise_orbit else -AOSPath._max_orbit_distance(az_list)

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

    @staticmethod
    def get_aos_rotor_angles(az_rate_aos: float, interpolated_orbit: dict[str, float]):
        """Compute initial aos rotor angles for rotor prepositioning, taking into account whether to
        traverse cw or ccw relative to home."""

        phi_max_cw, phi_max_ccw, az_aos, el_aos = AOSPath.max_rotor_travel(az_rate_aos, interpolated_orbit)

        if (phi_max_cw > 270) and (phi_max_ccw > 270):
            raise InvalidOrbitException("Angular travel exceeds maximum for cw or ccw traversal")
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

        # Compute correct az_aos angle and halfway angle (needed since MD-01 shortway = true)
        if clockwise:
            az_aos = AOSPath._clockwise_angle(az_aos)
            az_aos_half = 270 + (az_aos - 270) / 2
        else:
            az_aos = AOSPath._counterclockwise_angle(az_aos)
            az_aos_half = 270 - (270 - az_aos) / 2

        return az_aos, az_aos_half, el_aos


class InvalidOrbitException(Exception):
    def __init__(self, message="Orbit parameters are out of valid range"):
        self.message = message
        super().__init__(self.message)
