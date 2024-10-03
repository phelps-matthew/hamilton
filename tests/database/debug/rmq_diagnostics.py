import requests

def check_rabbitmq_setup():
    url = 'http://guest:guest@localhost:15672/api/'
    # Check exchanges
    exchanges = requests.get(url + 'exchanges').json()
    print("Exchanges:", exchanges)
    # Check queues
    queues = requests.get(url + 'queues').json()
    print("Queues:", queues)
    # Check bindings
    bindings = requests.get(url + 'bindings').json()
    print("Bindings:", bindings)

# Remember to replace 'guest:guest@localhost:15672' with your actual RabbitMQ credentials and server address
