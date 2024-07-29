import numpy as np
from datetime import datetime, timedelta
from gnuradio import gr
import pmt
import sigmf
from sigmf import SigMFFile
import threading
from pathlib import Path
import os
import logging

logger = logging.getLogger(__name__)


class SigMFUSRPSink(gr.sync_block):
    """
    A custom GNU Radio sink block for writing SigMF-formatted data from a USRP source.

    This block processes complex samples from a USRP source, buffers them, and writes
    them to a SigMF-compliant data file. It also generates and maintains the associated
    metadata file.

    Args:
        filename (str): Base name for the output SigMF files.
        uhd_source (uhd.usrp_source): The USRP source block providing the samples.
        description_meta (str): Description to be included in the SigMF metadata.
        buffer_size_bytes (int): Size of the internal buffer in bytes. Default is 1MB.

    Note: We assume each complex sample (np.complex64) occupies 8 bytes. Given our default SDR sample rate
    of 50kHz and given hard drive benchmarks, disk write speeds are faster than SDR data rate. Suggested
    buffer sizes are 400kB-2MB, which results in writing every 1-5 seconds. 1MB buffer write every 2.62 seconds.
    """

    def __init__(self, sample_rate, filename, uhd_source, description_meta, buffer_size_bytes=1048576):  # 1MB buffer
        gr.sync_block.__init__(self, name="Custom SigMF Sink", in_sig=[np.complex64], out_sig=None)
        self.message_port_register_in(pmt.intern("annotations"))
        self.set_msg_handler(pmt.intern("annotations"), self.handle_annotation)
        self.sample_rate = sample_rate
        self.filename = Path(filename)
        self.uhd_source = uhd_source
        self.description_meta = description_meta
        self.sample_count = 0
        self.buffer_size = buffer_size_bytes // 8  # Convert bytes to number of complex samples
        self.buffer = np.empty(self.buffer_size, dtype=np.complex64)
        self.buffer_index = 0
        self.lock = threading.Lock()
        self.meta = None
        self.data_file = None
        self.data_file_set = False

    def start(self):
        logger.info("Starting SigMFUSRPSink")
        logger.info(f"Opening datafile: {self.filename.with_suffix('.sigmf-data')}")
        self.data_file = self.filename.with_suffix(".sigmf-data").open("w+b")
        self._initialize_metadata()
        return True

    def handle_annotation(self, msg):
        annotation = pmt.to_python(msg)
        with self.lock:
            self.meta.add_annotation(
                annotation['core:sample_start'],
                annotation['core:sample_count'],
                metadata=annotation
            )
        self._write_metadata()

    def _initialize_metadata(self):
        logger.info("Initializing metadata")
        usrp_info = self.uhd_source.get_usrp_info()
        mboard_id = usrp_info.get("mboard_id", "Unknown")
        daughterboard_id = usrp_info.get("rx_id", "Unknown").split()[0]
        serial_number = usrp_info.get("mboard_serial", "Unknown")

        self.meta = SigMFFile(
            global_info={
                SigMFFile.DATATYPE_KEY: "cf32_le",
                SigMFFile.SAMPLE_RATE_KEY: self.sample_rate,
                SigMFFile.AUTHOR_KEY: "Hamilton",
                SigMFFile.DESCRIPTION_KEY: self.description_meta,
                SigMFFile.RECORDER_KEY: f"USRP {mboard_id} with {daughterboard_id}",
                SigMFFile.VERSION_KEY: sigmf.__version__,
                SigMFFile.FREQUENCY_KEY: self.uhd_source.get_center_freq(),
                SigMFFile.DATETIME_KEY: self._get_time().isoformat() + "Z",
                SigMFFile.HW_KEY: "crossed-yagi_PGA-103+_B200",
                "core:hw_serial": serial_number,
                "core:gps_locked": self._gps_locked(),
            }
        )

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

    def work(self, input_items, output_items):
        with self.lock:
            self._process_samples(input_items[0])
        return len(input_items[0])

    def _process_samples(self, samples):
        samples_to_process = len(samples)
        while samples_to_process > 0:
            space_in_buffer = self.buffer_size - self.buffer_index
            samples_to_write = min(samples_to_process, space_in_buffer)

            end_index = len(samples) - samples_to_process + samples_to_write
            self.buffer[self.buffer_index : self.buffer_index + samples_to_write] = samples[
                end_index - samples_to_write : end_index
            ]

            self.buffer_index += samples_to_write
            samples_to_process -= samples_to_write

            if self.buffer_index == self.buffer_size:
                self._write_buffer()

        self.sample_count += len(samples)

    def _write_buffer(self):
        bytes_to_write = self.buffer_index * 8  # Convert samples to bytes
        logger.debug(f"Writing buffer of size {self.buffer_index} samples ({bytes_to_write} bytes) to file")
        self.data_file.write(self.buffer[: self.buffer_index].tobytes())
        self.data_file.flush()

        if not self.data_file_set:
            self.meta.set_data_file(str(self.filename.with_suffix(".sigmf-data").absolute()))
            self.data_file_set = True

        self.buffer_index = 0
        logger.debug("Buffer written and flushed to disk")

    def _write_metadata(self):
        meta_file = self.filename.with_suffix(".sigmf-meta")
        with meta_file.open("w") as f:
            self.meta.dump(f, pretty=True)

    def _gps_locked(self):
        try:
            return self.uhd_source.get_mboard_sensor("gps_locked").to_bool()
        except Exception:
            return False

    def _get_time(self):
        current_time = self.uhd_source.get_time_now()
        full_secs = current_time.get_full_secs()
        frac_secs = current_time.get_frac_secs()
        return datetime.utcfromtimestamp(full_secs) + timedelta(seconds=frac_secs)

    def stop(self):
        with self.lock:
            if self.buffer_index > 0:
                self._write_buffer()
            if self.data_file:
                self.data_file.flush()
                os.fsync(self.data_file.fileno())
                self.data_file.close()
                logger.info(f"Closing datafile: {self.filename.with_suffix('.sigmf-data')}")
            self._write_metadata()

        logger.info(
            f"SigMFUSRPSink stopped. Total samples processed: {self.sample_count} ({self.sample_count * 8} bytes)"
        )
        return True
