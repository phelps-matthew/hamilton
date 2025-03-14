#!/home/mgp/miniforge3/envs/gr39/bin/python

import argparse
from hamilton.operators.relay.client import RelayClient
import asyncio
from loguru import logger

root_logger = logging.getLogger()
root_logger.setLevel(logging.WARNING)


async def handle_command(args):
    client = RelayClient()

    try:
        await client.start()

        if args.command == "set":
            parameters = {"id": args.id, "state": args.state}
            response = await client.set(**parameters)

        elif args.command == "status":
            response = await client.status()

        print(response)

    finally:
        await client.stop()


if __name__ == "__main__":
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
        asyncio.run(handle_command(args))
    else:
        parser.print_help()
