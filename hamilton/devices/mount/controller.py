import json
import pika
from hamilton.devices.mount.driver import ROT2Prog

class MountController:
    def __init__(self, rabbitmq_server, command_queue, status_queue):
        self.mount = ROT2Prog("/dev/usbttymd01")  # Initialize the ROT2Prog instance
        self.command_queue = command_queue
        self.status_queue = status_queue

        # Set up RabbitMQ connection and channel
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(rabbitmq_server))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.command_queue)

        # Subscribe to the command queue
        self.channel.basic_consume(queue=self.command_queue, on_message_callback=self.on_command_received, auto_ack=True)

    def on_command_received(self, ch, method, properties, body):
        message = json.loads(body)
        command = message.get('command')
        parameters = message.get('parameters', {})

        # Process the command
        if command == 'set':
            az = parameters.get('azimuth')
            el = parameters.get('elevation')
            self.mount.set(az, el)
        elif command == 'status':
            status = self.mount.status()
            self.publish_status(status)

    def publish_status(self, status):
        self.channel.basic_publish(exchange='', routing_key=self.status_queue, body=json.dumps(status))

    def start(self):
        self.channel.start_consuming()

if __name__ == "__main__":
    controller = MountController(rabbitmq_server='localhost', command_queue='mount_commands', status_queue='mount_status')
    controller.start()