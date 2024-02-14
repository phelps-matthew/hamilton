import pika
import json
import sys
from hamilton.service_manager.config import Config
import uuid

class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    END = '\033[0m'

def print_colored(text, color):
    print(f"{color}{text}{Colors.END}")



# NOT USED
class ServiceViewerClient:
    def __init__(self, config: Config):
        self.config = config
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(config.RABBITMQ_SERVER))
        self.channel = self.connection.channel()
        self.command_queue = config.COMMAND_QUEUE

    def format_systemctl_output(self, response):
        formatted_output = ""
        for service, status in response.items():
            color = Colors.GREEN if status == "active" else Colors.RED
            formatted_output += f"{color}{service}:{Colors.END} {status}\n"
        return formatted_output

    # In ServiceViewerClient, modify the on_response method:
    def on_response(self, ch, method, props, body):
        if corr_id == props.correlation_id:
            response = json.loads(body.decode())
            formatted_response = self.format_systemctl_output(response)
            print(formatted_response)
            self.connection.close()


    def send_command(self, command, parameters=None):
        if parameters is None:
            parameters = {}

        message = {"command": command, "parameters": parameters}
        response_queue = self.channel.queue_declare(queue="", exclusive=True).method.queue
        corr_id = str(uuid.uuid4())

        self.channel.basic_publish(
            exchange="",
            routing_key=self.command_queue,
            properties=pika.BasicProperties(reply_to=response_queue, correlation_id=corr_id),
            body=json.dumps(message),
        )

        def on_response(ch, method, props, body):
            if corr_id == props.correlation_id:
                print("Response:", body.decode())
                self.connection.close()

        self.channel.basic_consume(queue=response_queue, on_message_callback=on_response, auto_ack=True)
        self.channel.start_consuming()


if __name__ == "__main__":
    command = sys.argv[1]  # 'status'
    service = sys.argv[2] if len(sys.argv) > 2 else None

    client = ServiceViewerClient(Config)
    client.send_command(command, service)
