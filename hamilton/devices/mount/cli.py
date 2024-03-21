#!/home/mgp/miniforge3/envs/gr39/bin/python

import argparse
from hamilton.devices.mount.client import MountClient

if __name__ == "__main__":
    client = MountClient()

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
        try:
            client.node.start()
            if args.command == "set":
                params = {"azimuth": args.azimuth, "elevation": args.elevation}
                message = client.node.msg_generator.generate_command(args.command, params)
                response = client.node.publish_rpc_message("observatory.device.mount.command.set", message)
            elif args.command == "status":
                message = client.node.msg_generator.generate_command(args.command, {})
                response = client.node.publish_rpc_message("observatory.device.mount.command.status", message)
            elif args.command == "stop":
                message = client.node.msg_generator.generate_command(args.command, {})
                response = client.node.publish_rpc_message("observatory.device.mount.command.stop", message)

            print("Response:", response)

        finally:
            client.node.stop()
