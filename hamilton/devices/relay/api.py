import pylibftdi
import argparse
import logging
import time
import random


class FTDIBitbangRelay:
    BITMODE_BITBANG = 0x01  # Define bitbang mode value
    BITMODE_RESET = 0x00  # Define reset mode value

    def __init__(self, device_id=None, verbosity=0):
        # Configure logging based on verbosity level
        if verbosity == 0:
            logging.basicConfig(level=logging.WARNING)
        elif verbosity == 1:
            logging.basicConfig(level=logging.INFO)
        elif verbosity >= 2:
            logging.basicConfig(level=logging.DEBUG)

        # Initialize the FTDI device
        self.driver = pylibftdi.Driver()
        try:
            if device_id:
                self.dev = pylibftdi.Device(device_id=device_id)
            else:
                self.dev = pylibftdi.Device()
            self.dev.baudrate = 9600
            self.dev.ftdi_fn.ftdi_set_bitmode(0xFF, self.BITMODE_BITBANG)  # Enable bitbang mode
            logging.info("Initialized FTDI device in bitbang mode.")
        except pylibftdi.FtdiError as e:
            logging.exception("Failed to initialize FTDI device")
            raise

        # Attempt to read the initial state of the device
        self.local_state = self._read_device_state()

    def _read_device_state(self):
        try:
            # Flush any previous data
            # mp I don't think this does anything
            # self.dev.flush_input()

            # Read the current state from the device, this will be used as the local state
            state = ord(self.dev.read(1)) if self.dev.read(1) else 0x00

            # Perform a dummy read to clear the buffer after the initial read
            self.dev.read(1)

            return state
        except pylibftdi.FtdiError as e:
            logging.exception("Failed to read initial state from FTDI device")
            return 0x00  # Default to all relays off if read fails

    def get_relay_state(self):
        """
        Returns the current state of the relays.
        """
        return self.local_state

    def set_relay(self, relay_num, state):
        try:
            # Calculate bitmask for the specific relay
            pin_mask = 1 << (relay_num - 1)

            # Update the local state based on the desired relay state
            if state == "on":
                self.local_state |= pin_mask
            else:
                self.local_state &= ~pin_mask

            # Write the new state to the FTDI device
            self.dev.write(bytes([self.local_state]))

            # Wait briefly to ensure the FTDI device processes the write
            time.sleep(0.05)

            # Perform a dummy read to ensure the next read is accurate
            self.dev.read(1)

            logging.debug(f"Relay {relay_num} set to {state.upper()}. Local state: {self.local_state:08b}")

        except pylibftdi.FtdiError as e:
            logging.exception(f"Failed to set relay {relay_num}")
        except Exception as e:
            logging.exception("An unexpected error occurred while setting the relay")

    def test_readback(self):
        try:
            # Write a known pattern
            # test_pattern = 0xAA  # 10101010 in binary
            test_pattern = random.randint(0, 255)  # Random number between 0 and 255
            self.dev.write(bytes([test_pattern]))

            # Perform a dummy read to retrieve the echo of the write operation.
            # This is just to maintain proper synchronization based on your observations.
            dummy_read = self.dev.read(1)

            # Short delay to allow the device to process the change
            time.sleep(0.1)  # 100 ms delay, adjust as necessary

            # Flush the device's input buffer to clear any stale data
            self.dev.flush_input()

            # Read back the state
            readback_pattern = ord(self.dev.read(1))
            logging.info(f"Written pattern: {test_pattern:08b}")
            logging.info(f"Read back pattern: {readback_pattern:08b}")

            # Check if the read back pattern matches the written pattern
            if test_pattern == readback_pattern:
                logging.info("Readback successful, device supports reading pin states.")
            else:
                logging.error(
                    "Readback failed, device may not support reading pin states in bitbang mode or there's a timing issue."
                )
        except pylibftdi.FtdiError as e:
            logging.exception("An error occurred during the readback test")

    def close(self):
        try:
            # Turn off all relays before closure; this sets the next instance's current state as 00000000.
            self.dev.write(bytes([0]))
            self.dev.ftdi_fn.ftdi_set_bitmode(0x00, self.BITMODE_RESET)  # Disable bitbang mode, back to reset mode
            self.dev.close()
            logging.info("Closed FTDI device")
        except pylibftdi.FtdiError as e:
            logging.exception("Failed to close FTDI device")


def main():
    parser = argparse.ArgumentParser(description="Control a relay via FTDI bitbang mode.")
    parser.add_argument("relay_num", type=int, choices=range(1, 5), help="Relay number (1-4)")
    parser.add_argument("state", choices=["on", "off"], help='Relay state to set ("on" or "off")')
    parser.add_argument("-s", "--status", action="store_true", help="Get the status of the relay")
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="Increase output verbosity (use -vv for debug level)"
    )
    args = parser.parse_args()

    relay = FTDIBitbangRelay(verbosity=args.verbose)
    if args.status:
        print(f"Current Relay State: {relay.get_relay_state():08b}")
    else:
        try:
            relay.set_relay(args.relay_num, args.state)
        finally:
            relay.close()

    args = parser.parse_args()

if __name__ == "__main__":
    logging.basicConfig(filename='relay_control.log', level=logging.DEBUG)
    main()
