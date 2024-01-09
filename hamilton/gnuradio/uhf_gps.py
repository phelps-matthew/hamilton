#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: UHF Sigmf Recording
# Author: mgp
# GNU Radio version: 3.9.8.0

from distutils.version import StrictVersion

if __name__ == '__main__':
    import ctypes
    import sys
    if sys.platform.startswith('linux'):
        try:
            x11 = ctypes.cdll.LoadLibrary('libX11.so')
            x11.XInitThreads()
        except:
            print("Warning: failed to XInitThreads()")

from PyQt5 import Qt
from gnuradio import qtgui
from gnuradio.filter import firdes
import sip
from gnuradio import filter
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import uhd
import time
from gnuradio.qtgui import Range, RangeWidget
from PyQt5 import QtCore
import gr_sigmf



from gnuradio import qtgui

class uhf_gps(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "UHF Sigmf Recording", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("UHF Sigmf Recording")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except:
            pass
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("GNU Radio", "uhf_gps")

        try:
            if StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
                self.restoreGeometry(self.settings.value("geometry").toByteArray())
            else:
                self.restoreGeometry(self.settings.value("geometry"))
        except:
            pass

        ##################################################
        # Variables
        ##################################################
        self.target_samp_rate = target_samp_rate = 50e3
        self.samp_rate = samp_rate = 100e3
        self.rx_gain = rx_gain = 40
        self.rx_freq = rx_freq = 425e6

        ##################################################
        # Blocks
        ##################################################
        self._rx_gain_range = Range(1, 100, 1, 40, 200)
        self._rx_gain_win = RangeWidget(self._rx_gain_range, self.set_rx_gain, "'rx_gain'", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._rx_gain_win)
        self._rx_freq_range = Range(300e6, 525e6, 1e6, 425e6, 200)
        self._rx_freq_win = RangeWidget(self._rx_freq_range, self.set_rx_freq, "'rx_freq'", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._rx_freq_win)
        self.uhd_usrp_source_0 = uhd.usrp_source(
            ",".join(("", '')),
            uhd.stream_args(
                cpu_format="fc32",
                args='',
                channels=list(range(0,1)),
            ),
        )
        self.uhd_usrp_source_0.set_samp_rate(samp_rate)
        # Set the time to GPS time on next PPS
        # get_mboard_sensor("gps_time") returns just after the PPS edge,
        # thus add one second and set the time on the next PPS
        self.uhd_usrp_source_0.set_time_next_pps(uhd.time_spec(self.uhd_usrp_source_0.get_mboard_sensor("gps_time").to_int() + 1.0))
        # Sleep 1 second to ensure next PPS has come
        time.sleep(1)

        self.uhd_usrp_source_0.set_center_freq(uhd.tune_request(rx_freq, samp_rate/2), 0)
        self.uhd_usrp_source_0.set_antenna("RX2", 0)
        self.uhd_usrp_source_0.set_bandwidth(0.2e6, 0)
        self.uhd_usrp_source_0.set_gain(rx_gain, 0)
        self.sigmf_usrp_gps_message_source_0 = gr_sigmf.usrp_gps_message_source("", 1)
        self.sigmf_sink_0 = gr_sigmf.sink("cf32", 'cwd_filename', gr_sigmf.sigmf_time_mode_relative, False)
        self.sigmf_sink_0.set_global_meta("core:sample_rate", target_samp_rate)
        self.sigmf_sink_0.set_global_meta("core:description", 'Satellite RX')
        self.sigmf_sink_0.set_global_meta("core:author", 'Matthew Phelps')
        self.sigmf_sink_0.set_global_meta("core:license", '')
        self.sigmf_sink_0.set_global_meta("core:hw", 'crossed-yagi_PGA-103+_B200')
        self.rational_resampler_xxx_0 = filter.rational_resampler_ccc(
                interpolation=int(target_samp_rate),
                decimation=int(samp_rate),
                taps=[],
                fractional_bw=0)
        self.qtgui_sink_x_0 = qtgui.sink_c(
            2048, #fftsize
            window.WIN_BLACKMAN_hARRIS, #wintype
            rx_freq, #fc
            target_samp_rate, #bw
            "Spectrum Analyzer", #name
            True, #plotfreq
            True, #plotwaterfall
            True, #plottime
            True, #plotconst
            None # parent
        )
        self.qtgui_sink_x_0.set_update_time(1.0/10)
        self._qtgui_sink_x_0_win = sip.wrapinstance(self.qtgui_sink_x_0.qwidget(), Qt.QWidget)

        self.qtgui_sink_x_0.enable_rf_freq(True)

        self.top_layout.addWidget(self._qtgui_sink_x_0_win)


        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.sigmf_usrp_gps_message_source_0, 'out'), (self.sigmf_sink_0, 'gps'))
        self.connect((self.rational_resampler_xxx_0, 0), (self.qtgui_sink_x_0, 0))
        self.connect((self.rational_resampler_xxx_0, 0), (self.sigmf_sink_0, 0))
        self.connect((self.uhd_usrp_source_0, 0), (self.rational_resampler_xxx_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "uhf_gps")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_target_samp_rate(self):
        return self.target_samp_rate

    def set_target_samp_rate(self, target_samp_rate):
        self.target_samp_rate = target_samp_rate
        self.qtgui_sink_x_0.set_frequency_range(self.rx_freq, self.target_samp_rate)

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.uhd_usrp_source_0.set_samp_rate(self.samp_rate)
        self.uhd_usrp_source_0.set_center_freq(uhd.tune_request(self.rx_freq, self.samp_rate/2), 0)

    def get_rx_gain(self):
        return self.rx_gain

    def set_rx_gain(self, rx_gain):
        self.rx_gain = rx_gain
        self.uhd_usrp_source_0.set_gain(self.rx_gain, 0)

    def get_rx_freq(self):
        return self.rx_freq

    def set_rx_freq(self, rx_freq):
        self.rx_freq = rx_freq
        self.qtgui_sink_x_0.set_frequency_range(self.rx_freq, self.target_samp_rate)
        self.uhd_usrp_source_0.set_center_freq(uhd.tune_request(self.rx_freq, self.samp_rate/2), 0)




def main(top_block_cls=uhf_gps, options=None):

    if StrictVersion("4.5.0") <= StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
        style = gr.prefs().get_string('qtgui', 'style', 'raster')
        Qt.QApplication.setGraphicsSystem(style)
    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
