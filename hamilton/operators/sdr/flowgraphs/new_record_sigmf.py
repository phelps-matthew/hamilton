#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: SigMFRecording
# Author: mgp
# GNU Radio version: 3.9.8.0

from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import uhd
import time
import gr_sigmf
import threading
import logging

from hamilton.operators.sdr.flowgraphs.sigmf_block import SigMFUSRPSink

logger = logging.getLogger(__name__)

class SigMFRecordFlowgraph(gr.top_block):

    def __init__(
        self,
        samp_rate=100e3,
        target_samp_rate=50e3,
        rx_freq=425e6,
        rx_gain=40,
        sat_id="flowgraph_default_sat_id",
        ch0_antenna="RX2",
        filename="flowgraph_sample_filename",
    ):
        gr.top_block.__init__(self, "SigMFRecording", catch_exceptions=True)

        self._lock = threading.RLock()

        ##################################################
        # Variables
        ##################################################
        self.samp_rate = samp_rate
        self.target_samp_rate = target_samp_rate
        self.rx_freq = rx_freq
        self.rx_gain = rx_gain
        self.sat_id = sat_id
        self.ch0_antenna = ch0_antenna
        self.filename = filename


        ##################################################
        # Log the initializtion arguments (MP)
        ##################################################
        logger.info(f"SAMP RATE: {self.samp_rate}")
        logger.info(f"TARGET SAMP RATE: {self.target_samp_rate}")
        logger.info(f"RX_FREQ: {self.rx_freq}")
        logger.info(f"RX_GAIN: {self.rx_gain}")
        logger.info(f"SAT_ID: {self.sat_id}")
        logger.info(f"CH0_ANTENNA: {self.ch0_antenna}")
        logger.info(f"FILENAME: {self.filename}")


        ##################################################
        # Blocks
        ##################################################
        self.uhd_usrp_source_0 = uhd.usrp_source(
            ",".join(("", "")),
            uhd.stream_args(
                cpu_format="fc32",
                args="",
                channels=list(range(0, 1)),
            ),
        )
        self.uhd_usrp_source_0.set_samp_rate(samp_rate)
        # Set the time to GPS time on next PPS
        # get_mboard_sensor("gps_time") returns just after the PPS edge,
        # thus add one second and set the time on the next PPS
        self.uhd_usrp_source_0.set_time_next_pps(
            uhd.time_spec(self.uhd_usrp_source_0.get_mboard_sensor("gps_time").to_int() + 1.0)
        )
        # Sleep 1 second to ensure next PPS has come
        time.sleep(1)

        self.uhd_usrp_source_0.set_center_freq(uhd.tune_request(rx_freq, samp_rate / 2), 0)
        self.uhd_usrp_source_0.set_antenna("RX2", 0)
        self.uhd_usrp_source_0.set_bandwidth(0.2e6, 0)
        self.uhd_usrp_source_0.set_gain(rx_gain, 0)
        #self.sigmf_usrp_gps_message_source_0 = gr_sigmf.usrp_gps_message_source("", 1)
        #self.sigmf_sink_0 = gr_sigmf.sink("cf32", self.filename, gr_sigmf.sigmf_time_mode_relative, False)
        #self.sigmf_sink_0.set_global_meta("core:sample_rate", self.target_samp_rate)
        #self.sigmf_sink_0.set_global_meta("core:description", sat_id)
        #self.sigmf_sink_0.set_global_meta("core:author", "Matthew Phelps")
        #self.sigmf_sink_0.set_global_meta("core:license", "")
        #self.sigmf_sink_0.set_global_meta("core:hw", "crossed-yagi_PGA-103+_B2000")

        ##self.sigmf_sink_0.set_global_meta("custom:metadata", self.metadata)

        self.rational_resampler_xxx_0 = filter.rational_resampler_ccc(
            interpolation=int(target_samp_rate), decimation=int(samp_rate), taps=[], fractional_bw=0
        )

        self.sigmf_sink_0 = SigMFUSRPSink(
            filename=self.filename,
            uhd_source=self.uhd_usrp_source_0,
            description_meta=f"IQ Data Capture for NORAD ID: {self.sat_id}"
        )

        ##################################################
        # Connections
        ##################################################
        #self.msg_connect((self.sigmf_usrp_gps_message_source_0, "out"), (self.sigmf_sink_0, "gps"))
        #self.connect((self.rational_resampler_xxx_0, 0), (self.sigmf_sink_0, 0))
        self.connect((self.rational_resampler_xxx_0, 0), (self.sigmf_sink_0, 0))
        self.connect((self.uhd_usrp_source_0, 0), (self.rational_resampler_xxx_0, 0))

    def get_target_samp_rate(self):
        return self.target_samp_rate

    def set_target_samp_rate(self, target_samp_rate):
        with self._lock:
            self.target_samp_rate = target_samp_rate

    def get_sat_id(self):
        return self.sat_id

    def set_sat_id(self, sat_id):
        with self._lock:
            self.sat_id = sat_id

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        with self._lock:
            self.samp_rate = samp_rate
            self.uhd_usrp_source_0.set_samp_rate(self.samp_rate)
            self.uhd_usrp_source_0.set_center_freq(uhd.tune_request(self.rx_freq, self.samp_rate / 2), 0)

    def get_rx_gain(self):
        return self.rx_gain

    def set_rx_gain(self, rx_gain):
        with self._lock:
            self.rx_gain = rx_gain
            self.uhd_usrp_source_0.set_gain(self.rx_gain, 0)

    def get_rx_freq(self):
        return self.rx_freq

    def set_rx_freq(self, rx_freq):
        with self._lock:
            self.rx_freq = rx_freq
            self.uhd_usrp_source_0.set_center_freq(uhd.tune_request(self.rx_freq, self.samp_rate / 2), 0)

    def get_filename(self):
        return self.filename

    def set_filename(self, filename):
        with self._lock:
            self.filename = filename

    def set_ch0_antenna(self, ch0_antenna):
        with self._lock:
            self.uhd_usrp_source_0.set_antenna(ch0_antenna, 0)

    def get_ch0_antenna(self):
        self.uhd_usrp_source_0.get_antenna(0)

    def log_antenna_pointing(self, azimuth, elevation):
        self.sigmf_sink_0.add_antenna_pointing(azimuth, elevation)

def main(top_block_cls=SigMFRecordFlowgraph, options=None):
    tb = top_block_cls()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()

    tb.wait()


if __name__ == "__main__":
    main()
