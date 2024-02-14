#!/home/mgp/miniforge3/envs/gr39/bin/python

import argparse
from hamilton.devices.sdr.config import Config
from hamilton.base.client import BaseClient


class SDRClient(BaseClient):
    def __init__(self, config: Config = Config()):
        super().__init__(config)
        self.config = config


def main():
    client = SDRClient(config=Config)

    parser = argparse.ArgumentParser(description="Control SDR operations.")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Sub-command 'start_record'
    parser_start = subparsers.add_parser("start", help="Start recording")
    parser_start.add_argument("--freq", type=float, required=True, help="Frequency in Hz")
    parser_start.add_argument("--sample_rate", type=float, required=True, help="Sample rate in S/s")
    parser_start.add_argument("--sat_id", type=str, required=True, help="Satellite ID or user provided ID")
    parser_start.add_argument("--rx_gain", type=int, required=True, help="RX gain in dB")

    # Sub-command 'stop_record'
    parser_stop = subparsers.add_parser("stop", help="Stop recording")

    args = parser.parse_args()

    if args.command == "start":
        parameters = {k: v for k, v in vars(args).items() if v is not None and k != "command"}
        response = client.send_command("start_record", parameters)
        print("Recording started:", response)
    elif args.command == "stop":
        response = client.send_command("stop_record", {})
        print("Recording stopped:", response)


if __name__ == "__main__":
    main()
