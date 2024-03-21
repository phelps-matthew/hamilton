#!/home/mgp/miniforge3/envs/gr39/bin/python

import argparse
from hamilton.devices.relay.client import RelayClient
import time

if __name__ == "__main__":
    client = RelayClient()

    parser = argparse.ArgumentParser(description="Control and query the state of FTDI relays.")
    subparsers = parser.add_subparsers(dest="command", help="Sub-command help")

    # Sub-command 'set'
    parser_set = subparsers.add_parser("set", help="Set relay state")
    parser_set.add_argument("id", choices=["uhf_bias", "vhf_bias", "vhf_pol", "uhf_pol"], help="Relay ID")
    parser_set.add_argument("state", choices=["on", "off"], help="Relay state")

    # Sub-command 'status'
    parser_status = subparsers.add_parser("status", help="Get relay status")

    args = parser.parse_args()

    if args.command:
        client.node.start()
        try:
            if args.command == "set":
                command = args.command
                params = {"id": args.id, "state": args.state}
                message = client.node.msg_generator.generate_command(command, params)
                # No relay response on set command
                client.node.publish_message("observatory.device.relay.command.set", message)
                command = "status"
                params = {}
                message = client.node.msg_generator.generate_command(command, params)
                response = client.node.publish_rpc_message("observatory.device.relay.command.status", message)
                print(response)
            elif args.command == "status":
                command = args.command
                params = {}
                message = client.node.msg_generator.generate_command(command, params)
                response = client.node.publish_rpc_message("observatory.device.relay.command.status", message)
                print(response)

        finally:
            client.node.stop()

