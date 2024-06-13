import json
import asyncio
import numpy as np
from datetime import datetime
from bson import ObjectId
import pytz


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            # Convert NumPy arrays to lists
            return obj.tolist()
        elif isinstance(obj, datetime):
            # Format datetime objects as strings
            return obj.isoformat()
        elif isinstance(obj, ObjectId):
            return str(obj)
        return json.JSONEncoder.default(self, o)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


class CustomJSONDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        super().__init__(object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, dct):
        # Decode datetime objects
        for key, value in dct.items():
            if isinstance(value, str):
                try:
                    dct[key] = datetime.fromisoformat(value)
                except ValueError:
                    pass
        return dct

def utc_to_local(utc_dt):
    return utc_dt.replace(tzinfo=pytz.UTC).astimezone(pytz.timezone("HST"))

def local_to_utc(local_dt):
    return local_dt.replace(tzinfo=pytz.timezone("HST")).astimezone(pytz.UTC)

async def wait_until_first_completed(events: list[asyncio.Event], coroutines: list = None):
        """Wait until the first event or coroutine in the list is completed and return the completed task."""
        if coroutines is None:
            coroutines = []
        event_tasks = [asyncio.create_task(event.wait()) for event in events]
        coroutine_tasks = [asyncio.create_task(coro) for coro in coroutines]
        done, pending = await asyncio.wait(event_tasks + coroutine_tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        return done.pop()


if __name__ == "__main__":
    # Example usage (Encoder)
    data = {
        "array": np.array([1, 2, 3]),
        "date": datetime.now(),
    }
    json_data = json.dumps(data, cls=CustomJSONEncoder)
    print(json_data)

    # Example usage (Decoder)
    json_data = '{"array": [1, 2, 3], "date": "2023-01-01T12:00:00"}'
    decoded_data = json.loads(json_data, cls=CustomJSONDecoder)
