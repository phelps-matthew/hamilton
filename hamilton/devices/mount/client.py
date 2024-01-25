import json
import pika


def send_command(rabbitmq_server, command_queue, command, parameters=None):
    connection = pika.BlockingConnection(pika.ConnectionParameters(rabbitmq_server))
    channel = connection.channel()
    channel.queue_declare(queue=command_queue)

    message = {"command": command, "parameters": parameters}
    channel.basic_publish(exchange="", routing_key=command_queue, body=json.dumps(message))

    connection.close()


if __name__ == "__main__":
    import argparse
    from hamilton.devices.mount.config import Config

    RABBITMQ_SERVER = Config.RABBITMQ_SERVER
    COMMAND_QUEUE = Config.COMMAND_QUEUE

    # Main parser with detailed description
    parser = argparse.ArgumentParser(
        description="""
Mount CLI Client: Control the mount system using various commands.

Usage examples:
  mount set <azimuth> <elevation>  Set the azimuth and elevation of the mount.
  mount status                     Request the current status of the mount.
  mount stop                       Stop the mount controller.
""",
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

    if args.command == "set":
        send_command(RABBITMQ_SERVER, COMMAND_QUEUE, "set", {"azimuth": args.azimuth, "elevation": args.elevation})
    elif args.command == "status":
        send_command(RABBITMQ_SERVER, COMMAND_QUEUE, "status")
    elif args.command == "stop":
        send_command(RABBITMQ_SERVER, COMMAND_QUEUE, "stop")
