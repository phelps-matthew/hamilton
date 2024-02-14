#!/home/mgp/miniforge3/envs/gr39/bin/python

from hamilton.base.client import BaseClient
from hamilton.devices.mount.config import Config


class MountClient(BaseClient):
    def __init__(self, config: Config):
        super().__init__(config)
        self.config = config


if __name__ == "__main__":
    import argparse

    client = MountClient(config=Config)
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

    # Map CLI commands to MountClient's send_command method
    if args.command:
        if args.command == "set":
            response = client.send_command("set", {"azimuth": args.azimuth, "elevation": args.elevation})
        elif args.command == "status":
            response = client.send_command("status")
        elif args.command == "stop":
            response = client.send_command("stop")

        print("Response:", response)
