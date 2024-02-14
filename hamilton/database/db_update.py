"""Both db_query and db_update acquire and release locks for thread-safe file reading/writing"""

import json
import pika
import time
from threading import Lock
from hamilton.database.config import DBUpdateConfig
from hamilton.database.je9pel import JE9PELGenerator
from hamilton.database.db_generate import SatcomDBGenerator


class DBUpdateService:
    def __init__(self, config: DBUpdateConfig, db_generator: SatcomDBGenerator):
        self.config = config
        self.db_generator = db_generator
        #self.db_generator.set_logger(self.log_message)
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(self.config.RABBITMQ_SERVER))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.config.LOGGING_QUEUE)
        self.db_lock = Lock()

    def log_message(self, level: str, message: str):
        log_entry = {"service_name": "DBUpdateService", "level": level, "message": message}
        self.channel.basic_publish(exchange="", routing_key=self.config.LOGGING_QUEUE, body=json.dumps(log_entry))

    def update_database(self):
        with self.db_lock:
            try:
                self.log_message("INFO", "Updating database...")
                self.db_generator.generate_db(use_cache=False)
                self.log_message("INFO", "Database updated successfully")
            except Exception as e:
                self.log_message("ERROR", f"Database update failed: {str(e)}")

    def start(self):
        print("Starting DBUpdateService...")
        self.log_message("INFO", "Starting DBUpdateService...")
        while True:
            self.update_database()
            time.sleep(self.config.UPDATE_INTERVAL)


if __name__ == "__main__":
    je9pel = JE9PELGenerator(DBUpdateConfig)
    db_generator = SatcomDBGenerator(DBUpdateConfig, je9pel)
    update_service = DBUpdateService(config=DBUpdateConfig, db_generator=db_generator)
    update_service.start()
