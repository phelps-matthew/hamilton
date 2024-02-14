from hamilton.base.client import BaseClient
from hamilton.database.config import DBQueryConfig


class DBQueryClient(BaseClient):
    def __init__(self, config: DBQueryConfig):
        super().__init__(config)
        self.config = config


if __name__ == "__main__":
    client = DBQueryClient(DBQueryConfig)

    command = "query"
    parameters = {"sat_id": "33499"}
    response = client.send_command(command, parameters)
    print(f"Response: {response}")

    command = "get_satellite_ids"
    parameters = {}
    response = client.send_command(command, parameters)
    print(f"Response: {response}")

    command = "get_active_downlink_satellite_ids"
    parameters = {}
    response = client.send_command(command, parameters)
    print(f"Response: {response}")
    print(f"Response Items: {len(response)}")