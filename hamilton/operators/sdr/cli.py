#!/home/mgp/miniforge3/envs/gr39/bin/python

import argparse
import asyncio
from hamilton.operators.sdr.client import SDRClient
import logging


root_logger = logging.getLogger()
root_logger.setLevel(logging.WARNING)

async def handle_command(args):
    client = SDRClient()

    try:
        await client.start()

        if args.command == "status":
            response = await client.status()

        if args.command == "start_record":
            params = {"freq": args.freq, "sample_rate": args.sample_rate, "sat_id": args.sat_id, "rx_gain": args.rx_gain}
            response = await client.start_record(**params)

        elif args.command == "stop_record":
            response = await client.stop_record()

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

    # Subparser for the 'status' command
    parser_status = subparsers.add_parser("status", help="Request status")

    # Sub-command 'start_record'
    parser_start = subparsers.add_parser("start", help="Start recording")
    parser_start.add_argument("--freq", type=float, required=True, help="Frequency in Hz")
    parser_start.add_argument("--sample_rate", type=float, required=False, help="Sample rate in S/s")
    parser_start.add_argument("--sat_id", type=str, required=False, help="Satellite ID or user provided ID")
    parser_start.add_argument("--rx_gain", type=int, required=False, help="RX gain in dB")

    # Sub-command 'stop_record'
    parser_stop = subparsers.add_parser("stop", help="Stop recording")


    args = parser.parse_args()

    if args.command:
        asyncio.run(handle_command(args))
    else:
        parser.print_help()