"""Both db_query and db_update acquire and release locks for thread-safe file reading/writing"""

import json
from threading import Lock
from hamilton.base.controller import BaseController
from hamilton.database.config import DBQueryConfig


class DBQueryService(BaseController):
    def __init__(self, config: DBQueryConfig):
        super().__init__(config)
        self.config = config
        self.db_lock = Lock()

    def query_record(self, key) -> dict:
        with self.db_lock:
            with open(self.config.DB_PATH, "r") as file:
                data = json.load(file)
                return data.get(key, {})

    def get_satellite_ids(self) -> list:
        with self.db_lock:
            with open(self.config.DB_PATH, "r") as file:
                data = json.load(file)
                return list(data.keys())

    def get_active_downlink_satellite_ids(self) -> list:
        """Return list of sat ids with at least one JE9PEL active downlink"""
        with self.db_lock:
            with open(self.config.DB_PATH, "r") as file:
                data = json.load(file)
                active_sat_ids = []
                for k, d in data.items():
                    is_active = False
                    if d["je9pel"] is not None:
                        for link in d["je9pel"]["downlink"]:
                            if link["active"]:
                                is_active = True
                    if is_active:
                        active_sat_ids.append(k)
                return active_sat_ids

    def process_command(self, command: str, parameters: str):
        # Process the command
        if command == "query":
            sat_id = parameters.get("sat_id")
            response = self.query_record(sat_id)
        elif command == "get_satellite_ids":
            response = self.get_satellite_ids()
        elif command == "get_active_downlink_satellite_ids":
            response = self.get_active_downlink_satellite_ids()

        return response


if __name__ == "__main__":
    controller = DBQueryService(DBQueryConfig)
    controller.start()
