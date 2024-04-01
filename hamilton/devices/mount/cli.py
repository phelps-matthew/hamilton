#!/home/mgp/miniforge3/envs/gr39/bin/python

import argparse
import asyncio
from hamilton.devices.mount.client import MountClient
import logging


root_logger = logging.getLogger()
root_logger.setLevel(logging.WARNING)


async def handle_command(args):
    client = MountClient()

    try:
        await client.start()
        if args.command == "set":
            params = {"az": args.azimuth, "el": args.elevation}
            response = await client.set(**params)
        elif args.command == "status":
            response = await client.status()
        elif args.command == "stop":
            response = await client.stop_rotor()

        print(response)
    finally:
        await client.stop()


if __name__ == "__main__":
    # Setup argparser
    parser = argparse.ArgumentParser(
        description="Control the mount system using various commands",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", title="Commands", metavar="<command>")

    # Subparser for the 'set' command
    parser_set = subparsers.add_parser("set", help="Set azimuth and elevation")
    parser_set.add_argument("azimuth", type=float, help="Azimuth angle")
    parser_set.add_argument("elevation", type=float, help="Elevation angle")

    # Subparser for the 'status' command
    parser_status = subparsers.add_parser("status", help="Request status")

    # Subparser for the 'stop' command
    parser_stop = subparsers.add_parser("stop", help="Stop the mount controller")

    args = parser.parse_args()

    if args.command:
        asyncio.run(handle_command(args))
    else:
        parser.print_help()
