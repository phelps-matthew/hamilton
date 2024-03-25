"""
This is a wrapper around SigMFRecordFlowgraph, a self-contained flowgraph. It exposes appropriate methods to the SDR controller service and
internally handles relay control of the LNA.
"""

from typing import Literal
from datetime import datetime
from hamilton.devices.sdr.config import Config
from hamilton.devices.sdr.flowgraphs.record_sigmf import SigMFRecordFlowgraph
from hamilton.devices.relay.client import RelayClient
from pathlib import Path
import logging


class SDRSigMFRecord:
    def __init__(self, config: Config, relay_client: RelayClient):
        self.config = config
        self.relay = relay_client
        self.flowgraph = None

        obs_dir = Path(__file__).parent.parent.parent / "observations"
        self.obs_dir = obs_dir.absolute()

        # Default Values
        self.filename = None
        self.freq = 425e6
        self.sample_rate = 50e3
        self.rx_gain = 40
        self.sat_id = "norad-id"
        self.band = "UHF"
        self.ch0_antenna = "RX2"

        # Setup logger (needed for journalctl)
        self.log = logging.getLogger(self.__class__.__name__)
        if not self.log.handlers:
            handler = logging.StreamHandler()
            self.log.addHandler(handler)
        self.log.setLevel(logging.DEBUG)

    def set_freq(self, freq):
        self.freq = freq

    def set_sample_rate(self, sample_rate):
        self.sample_rate = sample_rate

    def set_rx_gain(self, rx_gain):
        self.rx_gain = rx_gain

    def set_sat_id(self, sat_id: str):
        self.sat_id = sat_id

    def set_filename(self):
        """Set unique filename for SigMF recording."""
        current_time = datetime.utcnow()
        formatted_time = current_time.strftime("%Y%m%d_%H%M%S")
        self.filename = str(self.obs_dir) + f"/{self.sat_id}_{self.band}_{formatted_time}"

    def set_lna(self, state: Literal["on", "off"] = "off"):
        """Switch appropriate power relay based on value of self.freq and state"""
        if self.freq <= self.config.VHF_HIGH:
            command = "set"
            parameters = {"id": "vhf_bias", "state": state}
        else:
            command = "set"
            parameters = {"id": "uhf_bias", "state": state}
        response = self.relay.send_command(command, parameters)
        self.log.info(f"Relay id {parameters['id']} set to state {parameters['state']}")

        return response

    def update_parameters(self, params: dict):
        """Called by external service"""
        self.log.info("Updating flowgraph attributes")
        for param_name, value in params.items():
            setter_method_name = f"set_{param_name}"
            if hasattr(self, setter_method_name):
                setter_method = getattr(self, setter_method_name)
                setter_method(value)
                self.log.info(f"Applied {setter_method_name} with value {value}")
        self.band = "VHF" if self.freq <= self.config.VHF_HIGH else "UHF"
        self.ch0_antenna = "TX/RX" if self.band == "VHF" else "RX2"

    def initialize_flowgraph(self):
        """Update params within flowgraph"""
        self.log.info("Intializing flowgraph")
        self.set_filename()
        params = {
            "target_samp_rate": self.sample_rate,
            "rx_freq": self.freq,
            "rx_gain": self.rx_gain,
            "sat_id": self.sat_id,
            "ch0_antenna": self.ch0_antenna,
            "filename": self.filename,
        }
        self.flowgraph = SigMFRecordFlowgraph(**params)

    def start_record(self):
        """Activate LNA and start SigMF flowgraph recording"""
        try:
            self.initialize_flowgraph()
            self.set_lna("on")
            self.flowgraph.start()
            self.log.info("Flowgraph started")
            return True
        except Exception as e:
            self.log.warning(f"Error starting recording: {e}")
            return False

    def stop_record(self):
        """Stop SigMF flowgraph recording and deactivate LNA"""
        try:
            self.flowgraph.stop()
            self.flowgraph.wait()  # Waits for all processing to stop
            self.log.info("Flowgraph stopped")
            self.set_lna("off")
            return True
        except Exception as e:
            self.log.warning(f"Error stopping recording: {e}")
            return False
