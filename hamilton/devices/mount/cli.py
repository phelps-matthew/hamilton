#!/home/mgp/miniforge3/envs/gr39/bin/python

import argparse
import asyncio
from hamilton.devices.mount.client import MountClient


async def handle_command(args):
    client = MountClient()

    try:
        await client.start()
        if args.command == "set":
            params = {"azimuth": args.azimuth, "elevation": args.elevation}
            message = client.msg_generator.generate_command(args.command, params)
            response = await client.publish_rpc_message("observatory.device.mount.command.set", message)
        elif args.command == "status":
            message = client.msg_generator.generate_command(args.command, {})
            response = await client.publish_rpc_message("observatory.device.mount.command.status", message)
        elif args.command == "stop":
            message = client.msg_generator.generate_command(args.command, {})
            response = await client.publish_rpc_message("observatory.device.mount.command.stop", message)

        print("Response:", response)
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
