"""
Generate a json database comprising satellite metadata, TLE, and TX frequencies. Data is sourced from 
Satnogs, as they provide the only complete list of TX frequencies.

Note:
Need method for handling satellites that no longer have TLE in "tle.json".
Schema validation would improve.
"""

import pandas as pd
import json
import requests
import logging
from pathlib import Path
import shutil
from collections import Counter

# Hamilton frequency bands
VHF_LOW = 130e6
VHF_HIGH = 150e6
UHF_LOW = 410e6
UHF_HIGH = 440e6


# Initialize logging
logging.basicConfig(
    format="[%(asctime)s] (%(levelname)s) %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)

## I/O and HTTP Requests ##


def download_json_data(url: str) -> dict:
    response = requests.get(url)
    return json.loads(response.text)


def load_json(path):
    with open(path) as f:
        d = json.load(f)
    return d


def write_json_to_file(data, file_path):
    logging.info(f"Writing {Path(file_path).absolute()}")
    with Path(file_path).open("w") as file:
        json.dump(data, file, indent=4)


def initialize_cache_directory(directory_path="./cache"):
    cache_dir = Path(directory_path)
    # If directory exists, remove it and its contents.
    if cache_dir.is_dir():
        shutil.rmtree(directory_path)
    cache_dir.mkdir()
    return cache_dir

def initialize_cache_directory(directory_path: str | Path = "./cache", files_to_remove: list = []) -> None:
    cache_dir = Path(directory_path)
    # Ensure the directory exists
    cache_dir.mkdir(exist_ok=True)

    # Remove specific files if they exist
    for file_name in files_to_remove:
        file_path = cache_dir / file_name
        if file_path.is_file():
            file_path.unlink()
    
    return cache_dir

## Data Extraction ##


def fetch(use_cache=False):
    transmitters_url = "https://db.satnogs.org/api/transmitters/?format=json"
    satellites_url = "https://db.satnogs.org/api/satellites/?format=json"
    tle_url = "https://db.satnogs.org/api/tle/?format=json"
    cache_dir = Path(__file__).parent / "cache"

    if use_cache:
        logging.info("Referencing local cache.")

        logging.info("Fetching TLE data.")
        tle_data = load_json(cache_dir / "tle.json")

        logging.info("Fetching satellite data.")
        satellites_data = load_json(cache_dir / "satellites.json")

        logging.info("Fetching transmitter data.")
        transmitters_data = load_json(cache_dir / "transmitters.json")

    else:
        logging.info("Creating local cache.")
        files_to_remove = ["tle.json", "satellites.json", "transmitters.json"]
        cache_dir = initialize_cache_directory(directory_path=cache_dir, files_to_remove=files_to_remove)

        logging.info("Fetching TLE data.")
        tle_data = download_json_data(tle_url)
        write_json_to_file(tle_data, cache_dir / "tle.json")

        logging.info("Fetching satellite data.")
        satellites_data = download_json_data(satellites_url)
        write_json_to_file(satellites_data, cache_dir / "satellites.json")

        logging.info("Fetching transmitter data.")
        transmitters_data = download_json_data(transmitters_url)
        write_json_to_file(transmitters_data, cache_dir / "transmitters.json")

    return tle_data, satellites_data, transmitters_data


## Data Validation ##


def is_value_unique(data, key):
    """
    Iterate through a list of dicts (i.e a raw SATNOGS deserialized json) and assert whether values associated
    with `key` is unique.

    Args:
        data: list of dicts
        key: key to be tested to assert if all associated values are unique
    Returns:
        bool, true if all values are unique
    """
    values = [d[key] for d in data]
    is_unique = len(values) == len(set(values))
    return is_unique


def is_nonempty(data, key):
    """
    Iterate through a list of dicts and assert whether values associated with every `key` is nonempty

    Args:
        data: list of dicts
        key: key to be tested to assert if all values are non-null values are nonempty
    Returns:
        bool, true if all values are nonempty
    """
    key_values = [(key, d[key]) for d in data]
    for k, v in key_values:
        if v is None:
            print(f"{k}: {v}")
    _is_nonempty = not (None in [d[key] for d in data])
    return _is_nonempty


def validate(tle_data, satellite_data, transmitter_data):
    logging.info("Validating 1:1 TLE:sat_UUID.")
    assert is_value_unique(tle_data, "sat_id")

    logging.info("Validating non-empty sat_UUID.")
    assert is_nonempty(satellite_data, "sat_id")

    logging.info("Validating unique sat_UUID.")
    assert is_value_unique(satellite_data, "sat_id")

    logging.info("Validating 1:many map of sat_UUID:transmitter.")
    assert not is_value_unique(transmitter_data, "sat_id")


def validate_norad_ids(data):
    logging.info("Validating nonempty NORAD satellites.")
    assert is_nonempty(data, "norad_cat_id")

    logging.info("Validating unique NORAD satellites.")
    assert is_value_unique(data, "norad_cat_id")


## Data Transformation ##


def filter_by_transmitter_frequency(df: pd.DataFrame) -> dict:
    """Filter the database by downlink frequency ranges"""

    # First exlode the dataframe, which creates a row for each transmitter
    df_exploded = df.explode("transmitters")

    # Create two new columns corresponding to downlink high and low
    df_exploded["tx_dl_low"] = df_exploded["transmitters"].map(
        lambda x: x["downlink_high"]
    )
    df_exploded["tx_dl_high"] = df_exploded["transmitters"].map(
        lambda x: x["downlink_low"]
    )

    # Create two new columns associated with tx alive (true, false) and status (active, inactive)
    df_exploded["tx_alive"] = df_exploded["transmitters"].map(lambda x: x["alive"])
    df_exploded["tx_status"] = df_exploded["transmitters"].map(lambda x: x["status"])

    # Filter out dead or inactive transmitters
    df_exploded = df_exploded[
        (df_exploded["tx_alive"] == True) & (df_exploded["tx_status"] == "active")
    ]

    # Filter out null downlink low AND high freqs
    df_exploded = df_exploded[
        df_exploded["tx_dl_low"].notnull() | df_exploded["tx_dl_high"].notnull()
    ]

    # Replace nans in transmitter downlink freq ranges with its associated high or low
    df_exploded["tx_dl_low"] = df_exploded["tx_dl_low"].fillna(
        df_exploded["tx_dl_high"]
    )
    df_exploded["tx_dl_high"] = df_exploded["tx_dl_high"].fillna(
        df_exploded["tx_dl_low"]
    )

    # Filter transmitter frequences to specified VHF range
    df_filtered = df_exploded[
        (
            (df_exploded["tx_dl_low"] >= VHF_LOW)
            & (df_exploded["tx_dl_high"] <= VHF_HIGH)
        )
        | (
            (df_exploded["tx_dl_low"] >= UHF_LOW)
            & (df_exploded["tx_dl_high"] <= UHF_HIGH)
        )
    ]

    # "Implode" the dataframe, s.t. each row now represents a satellite with many transmitters
    agg_cols = {
        col: "first"
        for col in df_filtered.columns
        if col not in ["transmitters", "sat_id", "tx_dl_low", "tx_dl_high"]
    }
    df_imploded = (
        df_filtered.groupby("sat_id")
        .agg({**agg_cols, "transmitters": lambda x: x.tolist()})
        .reset_index()
    )

    return df_imploded


def transform(tle_data, satellite_data, transmitter_data):
    # Convert to DataFrames
    df_tle = pd.DataFrame(tle_data)
    df_satellites = pd.DataFrame(satellite_data)
    df_transmitters = pd.DataFrame(transmitter_data)

    # Merge TLE DataFrame with satellite DataFrame
    # This will only select satellites that have an associated TLE.
    logging.info("Merging TLE's with satellites based on sat_UUID.")
    df = pd.merge(df_tle, df_satellites, on="sat_id")

    # Validate and merge norad_cat_ids.
    norad_cat_id_equal = df["norad_cat_id_x"].equals(df["norad_cat_id_y"].astype(int))
    assert (
        norad_cat_id_equal
    ), "`norad_cat_id` mismatch between tle.json and satellites.json"
    df = df.drop("norad_cat_id_y", axis=1)
    df = df.rename(columns={"norad_cat_id_x": "norad_cat_id"})

    # Rename `updated` and `citation` keys with parent suffix.
    df = df.rename(columns={"updated_x": "updated_tle"})
    df = df.rename(columns={"updated_y": "updated_satellite"})
    df = df.rename(columns={"citation": "citation_satellite"})

    # Drop `image` column.
    df = df.drop("image", axis=1)

    # Filter out any dead or satellits that have re-entered the atmosphere.
    logging.info("Filtering dead or re-entered satellites.")
    df = df[df["status"] == "alive"]

    # Group tx dataframe rows by `sat_id` and convert each group to a list of dictionaries.
    df_transmitters_2 = df_transmitters.groupby("sat_id").apply(
        lambda x: x.drop("sat_id", axis=1).to_dict(orient="records")
    )

    # Reset the index of the tx dataframe to an integer index and name list of dictionaries
    # column as `transmitters`.
    # This prepares the tx dataframe for merging.
    df_transmitters_2 = df_transmitters_2.reset_index()
    df_transmitters_2 = df_transmitters_2.rename(columns={0: "transmitters"})

    # Select `sat_id`s that exist in both (tle+sat) dataframe and tx dataframe.
    logging.info("Merging TLE + Satellite dataframe with transmitter dataframe.")
    df_merged = pd.merge(df, df_transmitters_2, on="sat_id")

    # Explode DataFrame and prune based on prescribed frequency bands.
    logging.info("Filtering database by frequency bands.")
    df_final = filter_by_transmitter_frequency(df_merged)

    # Serialize dataframe to json; this will properly and, among other methods, most straightforwardly
    # convert NaN's to nulls.
    logging.info("Formatting database to normalized dictionary form.")
    data_json = df_final.to_json(orient="records")

    # To (lazily) fix the foward slashes added from DataFrame -> json, we load as dict and *then* write out.
    data = json.loads(data_json)

    return data


## Format ##


def format(data):
    """Re-index the dictionary by satnogs 'sat_id' as the primary key"""
    logging.info("Reindexing data to use sat_UUID as primary key.")
    satcom_db = {}
    for d in data:
        key = d["sat_id"]
        inner_dict = d.copy()
        #inner_dict.pop("sat_id")
        satcom_db[key] = inner_dict
    return satcom_db


## Entrypoint ##


def generate_db(use_cache=False):
    logging.info("Starting SATCOM database generation.")

    # Fetch
    tle_data, satellite_data, transmitter_data = fetch(use_cache)

    # Validate
    validate(tle_data, satellite_data, transmitter_data)

    # Transform
    data = transform(tle_data, satellite_data, transmitter_data)

    # Re-Validate
    validate_norad_ids(data)

    # Format
    data = format(data)

    # Export as json
    path = Path(__file__).parent / "satcom.json"
    write_json_to_file(data, path)

    logging.info(f"Total number of observable satellites: {len(data)}")
    logging.info("SATCOM database generation complete.")

    return data


def get_cached_db():
    logging.info("Fetching cached SATCOM database.")
    path = Path(__file__).parent / "satcom.json"
    with open(path) as f:
        d = json.load(f)
    return d


if __name__ == "__main__":
    generate_db(use_cache=False)
