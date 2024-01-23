"""
This is a python interface to the Alfa ROT2Prog Controller.
"""
import logging
import time
from threading import Lock, Thread

import serial


class ReadTimeout(Exception):

    """A serial read timed out."""

    pass


class PacketError(Exception):

    """A received packet contained an error."""

    pass


class ROT2Prog:

    """Sends commands and receives responses from the ROT2Prog controller."""

    _log = logging.getLogger(__name__)

    _ser = None

    _divisor_lock = Lock()
    _divisor = 10

    _limits_lock = Lock()

    def __init__(self, port="/dev/ttyUSB0", timeout=5):
        """Creates object and opens serial connection.

        Args:
            port (str): Name of serial port to connect to.
            timeout (int, optional): Maximum response time from the controller.
        """
        # open serial port
        self._ser = serial.Serial(
            port=port,
            baudrate=115200,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=timeout,
            inter_byte_timeout=0.1,  # inter_byte_timeout allows continued operation after a bad packet
        )

        self._log.debug(
            "'" + str(self._ser.name) + "' opened with " + str(timeout) + "s timeout"
        )

        # get resolution from controller
        self.status()
        # set the limits to default values
        self.set_limits()

    def _send_command(self, command_packet):
        """Sends a command packet.

        Args:
            command_packet (list of int): Command packet queued.
        """
        self._ser.write(bytearray(command_packet))
        self._log.debug(
            "Command packet sent: " + str(list(map(hex, list(command_packet))))
        )

    def _recv_response(self):
        """Receives a response packet.

        Returns:
            az (float), el (float): Tuple of current azimuth and elevation.

        Raises:
            PacketError: The response packet is incomplete or contains bad values.
            ReadTimeout: The controller was unresponsive.
        """
        # read with timeout
        response_packet = list(self._ser.read(12))

        # attempt to receive 12 bytes, the length of response packet
        self._log.debug(
            "Response packet received: " + str(list(map(hex, list(response_packet))))
        )
        if len(response_packet) != 12:
            if len(response_packet) == 0:
                raise ReadTimeout("Response timed out")
            else:
                raise PacketError("Incomplete response packet")
        else:
            # convert from byte values
            AZ_DIVISOR = response_packet[5]
            EL_DIVISOR = response_packet[10]

            az = int("".join(str(i) for i in response_packet[1:5])) / AZ_DIVISOR - 360
            el = int("".join(str(i) for i in response_packet[6:10])) / EL_DIVISOR - 360

            az = float(round(az, 1))
            el = float(round(el, 1))

            # check resolution value
            valid_divisor = [1, 10, 100]
            if AZ_DIVISOR != EL_DIVISOR or AZ_DIVISOR not in valid_divisor:
                raise PacketError(
                    "Invalid controller resolution received (AZ_DIVISOR = "
                    + str(AZ_DIVISOR)
                    + ", EL_DIVISOR = "
                    + str(EL_DIVISOR)
                    + ")"
                )
            else:
                with self._divisor_lock:
                    self._divisor = AZ_DIVISOR

            self._log.debug("Received response")
            self._log.debug("-> AZ: " + str(az) + "°")
            self._log.debug("-> EL: " + str(el) + "°")
            self._log.debug("-> AZ_DIVISOR: " + str(AZ_DIVISOR))
            self._log.debug("-> EL_DIVISOR: " + str(EL_DIVISOR))

            return (az, el)

    def stop(self):
        """Sends a stop command to stop the rotator in the current position.

        Returns:
            az (float), el (float): Tuple of current azimuth and elevation.
        """
        self._log.debug("Stop command queued")

        cmd = [
            0x57,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x0F,
            0x20,
        ]
        self._send_command(cmd)
        return self._recv_response()

    def status(self):
        """Sends a status command to determine the current position of the rotator.

        Returns:
            az (float), el (float): Tuple of current azimuth and elevation.
        """
        self._log.debug("Status command queued")

        cmd = [
            0x57,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x1F,
            0x20,
        ]
        self._send_command(cmd)
        return self._recv_response()

    def set(self, az, el):
        """Sends a set command to turn the rotator to the specified position.

        Args:
            az (float): Azimuth angle to turn rotator to.
            el (float): Elevation angle to turn rotator to.

        Raises:
            ValueError: The inputs cannot be sent to the controller.
        """
        # make sure the inputs are within limits
        az = float(az)
        el = float(el)

        with self._limits_lock:
            if az > self._max_az or az < self._min_az:
                raise ValueError(
                    "Azimuth of "
                    + str(az)
                    + "° is out of range ["
                    + str(self._min_az)
                    + "°, "
                    + str(self._max_az)
                    + "°]"
                )
            if el > self._max_el or el < self._min_el:
                raise ValueError(
                    "Elevation of "
                    + str(el)
                    + "° is out of range ["
                    + str(self._min_el)
                    + "°, "
                    + str(self._max_el)
                    + "°]"
                )

        self._log.debug("Set command queued")
        self._log.debug("-> AZ: " + str(round(az, 1)) + "°")
        self._log.debug("-> EL: " + str(round(el, 1)) + "°")

        # encode with resolution
        with self._divisor_lock:
            divisor = self._divisor

        # form coordinates as strings
        H = str(int(divisor * (round(az, 1) + 360)))
        V = str(int(divisor * (round(el, 1) + 360)))

        # build command
        cmd = [
            0x57,
            int(H[0]) + 0x30,
            int(H[1]) + 0x30,
            int(H[2]) + 0x30,
            int(H[3]) + 0x30,
            divisor,
            int(V[0]) + 0x30,
            int(V[1]) + 0x30,
            int(V[2]) + 0x30,
            int(V[3]) + 0x30,
            divisor,
            0x2F,
            0x20,
        ]

        self._send_command(cmd)
        return self._recv_response()

    def get_limits(self):
        """Returns the minimum and maximum limits for azimuth and elevation.

        Returns:
            min_az (float), max_az (float), min_el (float), max_el (float): Tuple of minimum and maximum azimuth and elevation.
        """
        with self._limits_lock:
            return (self._min_az, self._max_az, self._min_el, self._max_el)

    def set_limits(self, min_az=0, max_az=360, min_el=0, max_el=180):
        """Sets the minimum and maximum limits for azimuth and elevation.

        Args:
            min_az (int, optional): Minimum azimuth. Defaults to -180.
            max_az (int, optional): Maximum azimuth. Defaults to 540.
            min_el (int, optional): Minimum elevation. Defaults to -21.
            max_el (int, optional): Maximum elevation. Defaults to 180.
        """
        with self._limits_lock:
            self._min_az = min_az
            self._max_az = max_az
            self._min_el = min_el
            self._max_el = max_el

    def get_pulses_per_degree(self):
        """Returns the number of pulses per degree.

        Returns:
            int: Pulses per degree defining the resolution of the controller.
        """
        with self._divisor_lock:
            return self._divisor