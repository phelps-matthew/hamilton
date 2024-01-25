import json
import pika
import time
from threading import Lock
from hamilton.database.config import Config
from hamilton.database.gen_sat_db import generate_db

class DBUpdateService:
    def __init__(self, config):
        self.config = config
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(self.config.RABBITMQ_SERVER))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.config.LOGGING_QUEUE)
        self.db_lock = Lock()

    def log_message(self, level, message):
        log_entry = {"service_name": "DBUpdateService", "level": level, "message": message}
        self.channel.basic_publish(exchange="", routing_key=self.config.LOGGING_QUEUE, body=json.dumps(log_entry))

    def update_database(self):
        with self.db_lock:
            try:
                generate_db(use_cache=False, log=self.log_message)  # Call the function from gen_db.py
                self.log_message("INFO", "Database updated successfully")
            except Exception as e:
                self.log_message("ERROR", f"Database update failed: {str(e)}")

    def start(self):
        while True:
            self.update_database()
            time.sleep(self.config.UPDATE_INTERVAL)  # Interval based on config

if __name__ == "__main__":
    update_service = DBUpdateService(config=Config)
    update_service.start()
