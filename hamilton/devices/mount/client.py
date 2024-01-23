import json
import pika
import uuid

class MountClient:
    def __init__(self, rabbitmq_server, command_queue, status_queue):
        self.command_queue = command_queue
        self.status_queue = status_queue

        # Set up RabbitMQ connection and channel
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(rabbitmq_server))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.command_queue)
        self.channel.queue_declare(queue=self.status_queue)

        # Subscribe to the status queue
        self.channel.basic_consume(queue=self.status_queue, on_message_callback=self.on_status_received, auto_ack=True)

    def send_command(self, command, parameters=None):
        message = {'command': command}
        if parameters:
            message['parameters'] = parameters
        self.channel.basic_publish(exchange='', routing_key=self.command_queue, body=json.dumps(message))

    def on_status_received(self, ch, method, properties, body):
        print("Received status update:", body.decode())

    def start_listening(self):
        print("Starting to listen for status updates...")
        self.channel.start_consuming()

    def close(self):
        self.connection.close()

if __name__ == "__main__":
    client = MountClient(rabbitmq_server='localhost', command_queue='mount_commands', status_queue='mount_status')
    
    # Query the status of the rotor
    client.send_command('status')

    # Set the state of the rotor
    client.send_command('set', {'azimuth': 270, 'elevation': 90})

    # Start listening for status updates
    client.start_listening()

    client.send_command('status')
    import time
    time.sleep(2)
    client.send_command('status')