#!/home/mgp/miniforge3/envs/gr39/bin/python

import argparse
import asyncio
import json
from loguru import logger

from hamilton.common.utils import CustomJSONEncoder
from hamilton.operators.orchestrator.client import OrchestratorClient
from hamilton.base.task import TaskGenerator

root_logger = logging.getLogger()
root_logger.setLevel(logging.WARNING)


async def handle_command(args):
    client = OrchestratorClient()
    task_generator = TaskGenerator()

    try:
        await client.start()
        await task_generator.start()

        if args.command == "status":
            response = await client.status()

        if args.command == "start":
            task = await task_generator.generate_task(args.sat_id)
            print(json.dumps(task, cls=CustomJSONEncoder, indent=4))
            if task is not None:
                response = await client.orchestrate(task)
            else:
                print(f"Failed to generate task for {args.sat_id}")

        elif args.command == "stop":
            response = await client.stop_orchestrating()

        print(response)

    finally:
        await client.stop()


if __name__ == "__main__":
    # Setup argparser
    parser = argparse.ArgumentParser(
        description="Control the orchestration of Hamilton",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", title="Commands", metavar="<command>")

    # Subparser for the 'status' command
    parser_status = subparsers.add_parser("status", help="Request status")

    # Sub-command 'start'
    parser_start = subparsers.add_parser("start", help="Start orchestration")
    parser_start.add_argument("--sat_id", type=str, required=True, help="NORAD Satellite ID")

    # Sub-command 'stop'
    parser_stop = subparsers.add_parser("stop", help="Stop orchestration")

    args = parser.parse_args()

    if args.command:
        asyncio.run(handle_command(args))
    else:
        parser.print_help()
