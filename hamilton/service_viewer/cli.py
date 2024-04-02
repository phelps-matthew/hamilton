#!/home/mgp/miniforge3/envs/gr39/bin/python

import argparse
import asyncio
from hamilton.service_viewer.client import ServiceViewerClient
import logging


root_logger = logging.getLogger()
root_logger.setLevel(logging.WARNING)


async def handle_command(service):
    client = ServiceViewerClient()

    try:
        await client.start()
        response = await client.status(service)
        print(response)
    finally:
        await client.stop()


if __name__ == "__main__":
    # Setup argparser
    parser = argparse.ArgumentParser(
        description="Service status viewer. If no service name is provided,"
        + "status for all services will be returned.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--service", type=str, help="Optional service name to request status for", default=None)

    args = parser.parse_args()

    asyncio.run(handle_command(args.service))
