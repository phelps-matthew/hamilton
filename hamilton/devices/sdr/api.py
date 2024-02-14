"""
This is a wrapper around SigMFRecordFlowgraph, a self-contained flowgraph. It exposes appropriate methods to the SDR controller service and
internally handles relay control
"""

from typing import Literal
from datetime import datetime
from hamilton.devices.sdr.config import Config
from hamilton.devices.sdr.flowgraphs.record_sigmf import SigMFRecordFlowgraph
from hamilton.devices.relay.client import RelayClient


class SDRSigMFRecord:
    def __init__(self, config: Config, relay_client: RelayClient, flowgraph: SigMFRecordFlowgraph):
        self.config = config
        self.relay = relay_client
        self.flowgraph = flowgraph

        # Default Values
        self.filename = None
        self.freq = 425e6
        self.sample_rate = 50e3
        self.rx_gain = 40
        self.sat_id = "sample_norad_id"
        self.band = "UHF"

    def set_freq(self, freq):
        self.freq = freq

    def set_sample_rate(self, sample_rate):
        self.sample_rate = sample_rate

    def set_rx_gain(self, rx_gain):
        self.rx_gain = rx_gain

    def set_sat_id(self, sat_id: str):
        self.sat = sat_id

    def set_filename(self):
        """Set unique filename for SigMF recording."""
        current_time = datetime.utcnow()
        formatted_time = current_time.strftime("%Y%m%d_%H%M%S")
        self.filename = f"record_{self.sat_id}_{self.band}_{formatted_time}"

    def set_lna(self, state: Literal["on", "off"] = "off"):
        """Switch appropriate power relay based on value of self.freq and state"""
        if self.config.VHF_LOW <= self.freq <= self.config.VHF_HIGH:
            command = "set"
            parameters = {"id": "vhf_bias", "state": state}
        else:
            command = "set"
            parameters = {"id": "uhf_bias", "state": state}
        response = self.relay.send_command(command, parameters)
        print(f"Relay id {parameters['id']} set to state {parameters['state']}")

        return response

    def update_parameters(self, params: dict):
        """Called by external service"""
        print("Updating flowgraph attributes")
        for param_name, value in params.items():
            setter_method_name = f"set_{param_name}"
            if hasattr(self, setter_method_name):
                setter_method = getattr(self, setter_method_name)
                setter_method(value)
        if self.config.VHF_LOW <= self.freq <= self.config.VHF_HIGH:
            self.band = "VHF"
        else:
            self.band = "UHF"

    def initialize_flowgraph(self):
        """Update params within flowgraph"""
        print("Intializing flowgraph")
        ch0_antenna = "TX/RX" if self.band == "VHF" else "RX2"
        self.flowgraph.set_ch0_antenna(ch0_antenna)
        self.flowgraph.set_rx_freq(self.freq)
        self.flowgraph.set_target_samp_rate(self.sample_rate)
        self.flowgraph.set_rx_gain(self.rx_gain)
        self.set_filename()
        self.flowgraph.set_filename(self.filename)

    def start_record(self):
        """Activate LNA and start SigMF flowgraph recording"""
        self.initialize_flowgraph()
        self.set_lna("on")
        self.flowgraph.start()
        print("Flowgraph started")

    def stop_record(self):
        """Stop SigMF flowgraph recording and deactivate LNA"""
        self.flowgraph.stop()
        self.flowgraph.wait()  # Waits for all processing to stop
        print("Flowgraph stopped")
        self.set_lna("off")
