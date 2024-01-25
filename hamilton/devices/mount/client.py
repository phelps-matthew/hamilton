#!/home/mgp/miniforge3/envs/gr39/bin/python

import json
import uuid

import pika


def send_command(rabbitmq_server, command_queue, status_queue, command, parameters=None):
    connection = pika.BlockingConnection(pika.ConnectionParameters(rabbitmq_server))
    channel = connection.channel()

    # Declare the command and status queues
    channel.queue_declare(queue=command_queue)
    channel.queue_declare(queue=status_queue)

    # Define correlation_id and response holder
    corr_id = str(uuid.uuid4())
    response = None

    # Define the response callback function
    def on_response(ch, method, props, body):
        nonlocal response
        if corr_id == props.correlation_id:
            response = body.decode()
            connection.close()  # Close the connection once the response is received

    # Create a callback queue and subscribe to it
    callback_queue = channel.queue_declare(queue="", exclusive=True).method.queue
    channel.basic_consume(queue=callback_queue, on_message_callback=on_response, auto_ack=True)

    # Send the command with reply_to and correlation_id properties
    message = {"command": command, "parameters": parameters}
    channel.basic_publish(
        exchange="",
        routing_key=command_queue,
        properties=pika.BasicProperties(
            reply_to=callback_queue,
            correlation_id=corr_id,
        ),
        body=json.dumps(message),
    )

    # Wait for the response
    while response is None:
        connection.process_data_events()
    print("Response:", response)


if __name__ == "__main__":
    import argparse

    from hamilton.devices.mount.config import Config

    RABBITMQ_SERVER = Config.RABBITMQ_SERVER
    COMMAND_QUEUE = Config.COMMAND_QUEUE
    STATUS_QUEUE = Config.STATUS_QUEUE

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
        send_command(
            RABBITMQ_SERVER, COMMAND_QUEUE, STATUS_QUEUE, "set", {"azimuth": args.azimuth, "elevation": args.elevation}
        )
    elif args.command == "status":
        send_command(RABBITMQ_SERVER, COMMAND_QUEUE, STATUS_QUEUE, "status")
    elif args.command == "stop":
        send_command(RABBITMQ_SERVER, COMMAND_QUEUE, STATUS_QUEUE, "stop")
