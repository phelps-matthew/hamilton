import json
import logging.config
from pathlib import Path

config_path = Path(__file__).parent / "logging" / "logging_config.json"
with open(config_path, "rt") as f:
    config = json.load(f)
logging.config.dictConfig(config)
