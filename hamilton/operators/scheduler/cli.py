#!/home/mgp/miniforge3/envs/gr39/bin/python

import argparse
import asyncio
from loguru import logger
import json

from hamilton.operators.scheduler.client import SchedulerClient
from hamilton.common.utils import CustomJSONEncoder

root_logger = logging.getLogger()
root_logger.setLevel(logging.WARNING)


async def handle_command(args):
    client = SchedulerClient()

    try:
        await client.start()

        if args.command == "status":
            response = await client.status()
            response = json.dumps(response, indent=4, cls=CustomJSONEncoder)

        if args.command == "set_mode":
            response = await client.set_mode(args.mode)

        elif args.command == "stop":
            response = await client.stop_scheduling()

        print(response)

    finally:
        await client.stop()


if __name__ == "__main__":
    # Setup argparser
    parser = argparse.ArgumentParser(
        description="Control the scheduling of Hamilton",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", title="Commands", metavar="<command>")

    # Subparser for the 'status' command
    parser_status = subparsers.add_parser("status", help="Request status")

    # Sub-command 'stop'
    parser_stop = subparsers.add_parser("stop", help="Stop scheduling")

    # Sub-command 'set_mode'
    parser_set_mode = subparsers.add_parser("set_mode", help="Set mode")
    parser_set_mode.add_argument("mode", type=str, help="Mode: survey, standby, inactive")

    args = parser.parse_args()

    if args.command:
        asyncio.run(handle_command(args))
    else:
        parser.print_help()
