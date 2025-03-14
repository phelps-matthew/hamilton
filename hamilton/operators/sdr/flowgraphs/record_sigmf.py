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
import threading
from loguru import logger

from hamilton.operators.sdr.flowgraphs.blocks.sigmf_block import SigMFUSRPSink
from hamilton.operators.sdr.flowgraphs.blocks.rmq_block import RMQSource
from hamilton.operators.sdr.flowgraphs.rmq.rmq_controller import RMQController




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
        self.rmq_source = RMQSource()
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

        self.rational_resampler_xxx_0 = filter.rational_resampler_ccc(
            interpolation=int(target_samp_rate), decimation=int(samp_rate), taps=[], fractional_bw=0
        )

        self.sigmf_sink_0 = SigMFUSRPSink(
            sample_rate=self.target_samp_rate,
            filename=self.filename,
            uhd_source=self.uhd_usrp_source_0,
            description_meta=f"IQ Data Capture for NORAD ID: {self.sat_id}",
        )

        ##################################################
        # RMQ Controller
        ##################################################
        self.rmq_controller = RMQController(self.rmq_source, self.sat_id)
        self.rmq_source.set_controller(self.rmq_controller)

        ##################################################
        # Connections
        ##################################################
        self.connect((self.rational_resampler_xxx_0, 0), (self.sigmf_sink_0, 0))
        self.connect((self.uhd_usrp_source_0, 0), (self.rational_resampler_xxx_0, 0))
        self.msg_connect((self.rmq_source, "annotations"), (self.sigmf_sink_0, "annotations"))

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

    def start(self):
        try:
            #self.rmq_source.start()
            super().start()
        except Exception as e:
            logger.error(f"Error starting flowgraph: {e}")
            self.stop()

    def stop(self):
        try:
            super().stop()
            #if self.rmq_source:
                #self.rmq_source.stop()
        except Exception as e:
            logger.error(f"Error stopping flowgraph: {e}")
        #finally:
            #self.wait()  # Ensure wait is called to clean up properly

    #def wait(self):
    #    try:
    #        super().wait()
    #    except Exception as e:
    #        logger.error(f"Error waiting for flowgraph: {e}")
    #    finally:
    #        self.stop()  # Ensure stop is called to clean up properly


def main(top_block_cls=SigMFRecordFlowgraph, options=None):
    tb = top_block_cls()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    try:
        tb.start()
        tb.wait()
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        tb.stop()

    # Add a small delay to allow for proper cleanup
    time.sleep(1)

if __name__ == "__main__":
    main()

