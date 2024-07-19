import numpy as np
from datetime import datetime, timedelta
from gnuradio import gr
import sigmf
from sigmf import SigMFFile
import datetime as dt
import threading


class SigMFUSRPSink(gr.sync_block):
    def __init__(self, filename, uhd_source, description_meta):
        gr.sync_block.__init__(self, name="Custom SigMF Sink", in_sig=[np.complex64], out_sig=None)
        self.filename = filename
        self.uhd_source = uhd_source
        self.description_meta = description_meta
        self.sample_count = 0
        self.data_file = None
        self.meta = None
        self.lock = threading.Lock()

    def start(self):
        self.data_file = open(f"{self.filename}.sigmf-data", "wb")

        # Query UHD device for information
        usrp_info = self.uhd_source.get_usrp_info()
        mboard_id = usrp_info.get("mboard_id", "Unknown")
        daughterboard_id = usrp_info.get("rx_id", "Unknown").split()[0]
        serial_number = usrp_info.get("mboard_serial", "Unknown")

        self.meta = SigMFFile(
            global_info={
                SigMFFile.DATATYPE_KEY: "cf32_le",
                SigMFFile.SAMPLE_RATE_KEY: self.uhd_source.get_samp_rate(),
                SigMFFile.AUTHOR_KEY: "GNURadio Custom SigMF Sink",
                SigMFFile.DESCRIPTION_KEY: self.description_meta,
                SigMFFile.RECORDER_KEY: f"USRP {mboard_id} with {daughterboard_id}",
                SigMFFile.VERSION_KEY: sigmf.__version__,
                SigMFFile.FREQUENCY_KEY: self.uhd_source.get_center_freq(),
                SigMFFile.DATETIME_KEY: self._get_time().isoformat() + "Z",
                SigMFFile.HW_KEY: f"USRP {mboard_id} with {daughterboard_id}",
                "core:hw_serial": serial_number,
                "core:gps_locked": self._gps_locked(),
            }
        )
        self.meta.set_data_file(self.data_file.name)

        self.meta.add_capture(
            0,
            metadata={
                SigMFFile.FREQUENCY_KEY: self.uhd_source.get_center_freq(),
                SigMFFile.DATETIME_KEY: self._get_time().isoformat() + "Z",
                "capture_details": {
                    "acquisition_bandwidth": self.uhd_source.get_bandwidth(),
                    "gain": self.uhd_source.get_gain(),
                    "antenna": self.uhd_source.get_antenna(),
                },
            },
        )
        return True

    def work(self, input_items, output_items):
        in0 = input_items[0]
        with self.lock:
            self.data_file.write(in0.tobytes())
            self.sample_count += len(in0)
        return len(in0)

    def _write_metadata(self):
        with open(f"{self.filename}.sigmf-meta", "w") as f:
            self.meta.dump(f, pretty=True)

    def _gps_locked(self):
        try:
            # Check if GPS is locked
            return self.uhd_source.get_mboard_sensor("gps_locked").to_bool()
        except Exception as e:
            # Assume GPS is not locked if sensor is unavailable
            return False

    def _get_time(self):
        """If GPSDO is present, UHD will update internal clock based on PPS."""
        # Query the current UHD time
        current_time = self.uhd_source.get_time_now()

        # Get full seconds and fractional seconds
        full_secs = current_time.get_full_secs()
        frac_secs = current_time.get_frac_secs()

        # Convert to datetime object
        dt = datetime.utcfromtimestamp(full_secs) + timedelta(seconds=frac_secs)

        return dt

    def add_antenna_pointing(self, azimuth, elevation):
        with self.lock:
            self.meta.add_annotation(
                self.sample_count,
                1,
                metadata={
                    "custom:azimuth": azimuth,
                    "custom:elevation": elevation,
                },
            )
        self._write_metadata()

    def stop(self):
        if self.data_file:
            self.data_file.close()
        self._write_metadata()
        return True
