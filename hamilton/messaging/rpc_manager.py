import asyncio
from hamilton.base.messages import Message

class RPCManager:
    def __init__(self):
        self.rpc_events: dict[str, asyncio.Future] = {}

    def create_future_for_rpc(self, correlation_id: str) -> asyncio.Future:
        """Creates a future for an RPC call identified by the given correlation ID."""
        if correlation_id in self.rpc_events:
            raise ValueError(f"Correlation ID {correlation_id} already in use.")
        future = asyncio.get_event_loop().create_future()
        self.rpc_events[correlation_id] = future
        return future

    def handle_incoming_message(self, message: Message, correlation_id: str):
        """Handles incoming messages by checking if they correspond to any waiting RPC calls."""
        if correlation_id and correlation_id in self.rpc_events:
            future = self.rpc_events.pop(correlation_id, None)
            if future and not future.done():
                future.set_result(message)

    def cleanup(self, correlation_id: str):
        """Cleans up any resources associated with a given correlation ID, if necessary."""
        self.rpc_events.pop(correlation_id, None)