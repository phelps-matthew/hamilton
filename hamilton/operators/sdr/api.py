"""
This is a wrapper around SigMFRecordFlowgraph, a self-contained flowgraph. It exposes appropriate methods to the SDR controller service and
internally handles relay control of the LNA.
"""

from typing import Literal
from datetime import datetime
from hamilton.operators.sdr.config import SDRControllerConfig
from hamilton.operators.sdr.flowgraphs.record_sigmf import SigMFRecordFlowgraph
from hamilton.operators.relay.client import RelayClient
from hamilton.operators.radiometrics.client import RadiometricsClient
from hamilton.common.utils import CustomJSONEncoder
from pathlib import Path
import logging
import json

logger = logging.getLogger(__name__)


class SDRSigMFRecord:
    def __init__(self, config: SDRControllerConfig, relay_client: RelayClient, radiometrics_client: RadiometricsClient = None):
        self.config = config
        self.relay = relay_client
        self.radiometrics = radiometrics_client
        self.flowgraph = None
        self.obs_dir = Path(self.config.observations_dir).expanduser()
        self.obs_dir.mkdir(parents=True, exist_ok=True)
        self.is_recording = False

        # Default Values
        self.filename = None
        self.freq = 425e6
        self.sample_rate = 50e3
        self.rx_gain = 40
        self.sat_id = "norad-id"
        self.band = "UHF"
        self.ch0_antenna = "RX2"
        self.metadata = None

    def get_status(self):
        return {"status": "recording" if self.is_recording else "idle"}

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
        self.filename = str(self.obs_dir) + f"/{formatted_time}_{self.band}_{self.sat_id}"

    def overwrite_sample_rate(self):
        if self.filename is not None:
            meta_path = Path(self.filename).with_suffix(".sigmf-meta")
            with open(meta_path, 'r') as f:
                metadata = json.load(f)
            metadata["global"]["core:sample_rate"] = self.sample_rate
            with open(meta_path, 'w') as f:
                logger.info(f"Overwriting sample rate in {str(meta_path)}")
                json.dump(metadata, f, indent=4)

    async def write_metadata(self):
        if self.filename is not None:
            meta_path = Path(self.filename).with_suffix(".json")
            with open(meta_path, 'w') as f:
                logger.info(f"Writing auxillary metadata to {str(meta_path)}")
                json.dump(self.metadata, f, indent=4, cls=CustomJSONEncoder)

    async def set_lna(self, state: Literal["on", "off"] = "off"):
        """Switch appropriate power relay based on value of `self.freq` and `state`"""
        if self.freq <= self.config.VHF_HIGH:
            parameters = {"id": "vhf_bias", "state": state}
        else:
            parameters = {"id": "uhf_bias", "state": state}
        response = await self.relay.set(**parameters)
        logger.info(f"Relay id {parameters['id']} set to state {parameters['state']}")
        return response

    async def update_parameters(self, params: dict):
        """Called by external service"""
        logger.info("Updating flowgraph attributes:")
        logger.info(json.dumps(params, indent=4))
        for param_name, value in params.items():
            setter_method_name = f"set_{param_name}"
            if hasattr(self, setter_method_name):
                setter_method = getattr(self, setter_method_name)
                setter_method(value)
                logger.info(f"Applied {setter_method_name} with value {value}")
        self.band = "VHF" if self.freq <= self.config.VHF_HIGH else "UHF"
        self.ch0_antenna = "TX/RX" if self.band == "VHF" else "RX2"
        self.metadata = await self.radiometrics.get_tx_profile(self.sat_id)

    def initialize_flowgraph(self):
        """Update params within flowgraph"""
        logger.info("Intializing flowgraph")
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

    async def start_record(self):
        """Activate LNA and start SigMF flowgraph recording"""
        try:
            self.initialize_flowgraph()
            await self.set_lna("on")
            self.flowgraph.start()
            self.is_recording = True
            logger.info("Flowgraph started")
            return True
        except Exception as e:
            logger.warning(f"Error starting recording: {e}")
            return False

    async def stop_record(self):
        """Stop SigMF flowgraph recording and deactivate LNA"""
        try:
            if self.flowgraph is not None:
                self.flowgraph.stop()
                self.flowgraph.wait()  # Waits for all processing to stop
                #self.overwrite_sample_rate() # sigmf has issue logging correct sample rate
                await self.write_metadata() # log the database metadata file as json
            self.is_recording = False
            logger.info("Flowgraph stopped")
            await self.set_lna("off")
            return True
        except Exception as e:
            logger.warning(f"Error stopping recording: {e}")
            return False
