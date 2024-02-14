#!/home/mgp/miniforge3/envs/gr39/bin/python

import argparse
from hamilton.base.client import BaseClient
from hamilton.devices.relay.config import Config


class RelayClient(BaseClient):
    def __init__(self, config: Config):
        super().__init__(config)
        self.config = config


def main():
    client = RelayClient(config=Config)

    parser = argparse.ArgumentParser(description="Control and query the state of FTDI relays.")
    subparsers = parser.add_subparsers(dest="command", help="Sub-command help")

    # Sub-command 'set'
    parser_set = subparsers.add_parser("set", help="Set relay state")
    parser_set.add_argument("id", choices=["uhf_bias", "vhf_bias", "vhf_pol", "uhf_pol"], help="Relay ID")
    parser_set.add_argument("state", choices=["on", "off"], help="Relay state")

    # Sub-command 'status'
    parser_status = subparsers.add_parser("status", help="Get relay status")

    args = parser.parse_args()

    if args.command == "set":
        response = client.send_command("set", {"id": args.id, "state": args.state})
        response = client.send_command("status", {})
        print(response)
    elif args.command == "status":
        response = client.send_command("status", {})
        print(response)


if __name__ == "__main__":
    main()
