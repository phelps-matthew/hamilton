from hamilton.base.controller import BaseController
from hamilton.devices.sdr.flowgraphs.record_sigmf import SigMFRecordFlowgraph
from hamilton.devices.sdr.api import SDRSigMFRecord
from hamilton.devices.sdr.config import Config
from hamilton.devices.relay.client import RelayClient


class SDRController(BaseController):
    def __init__(self, config: Config, recorder: SDRSigMFRecord):
        super().__init__(config)
        self.config = config
        self.flowgraph = recorder

    def process_command(self, command: str, parameters: str):
        response = None

        if command == "start_record":
            self.flowgraph.update_parameters(parameters)
            self.flowgraph.start_record()

        elif command == "stop_record":
            self.flowgraph.stop_record()

        return response


if __name__ == "__main__":
    relay_client = RelayClient()
    flowgraph = SigMFRecordFlowgraph()
    recorder = SDRSigMFRecord(config=Config, relay_client=relay_client, flowgraph=flowgraph)
    controller = SDRController(config=Config, recorder=recorder)
    controller.start()
