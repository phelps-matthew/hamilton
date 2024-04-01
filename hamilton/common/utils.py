import json
import numpy as np
from datetime import datetime
from bson import ObjectId
import json


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
