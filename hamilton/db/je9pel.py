"""
Parse JE9PEL's satellite frequency list for merging with our "SATCOM" database
"""

import pandas as pd
import json
import requests
import logging
from pathlib import Path
import shutil
from collections import Counter
from typing import Union
import numpy as np
import re

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

# Debugging
pd.set_option("display.max_rows", 500)
pd.set_option("display.max_colwidth", None)

## I/O and HTTP Requests ##


def download_csv(url: str) -> dict:
    response = requests.get(url)
    return response.text


def write_csv_to_file(data: str | Path, file_path: str | Path) -> None:
    logging.info(f"Writing {Path(file_path).absolute()}")
    with Path(file_path).open("w") as file:
        file.write(data)


def load_csv(file_path: str | Path) -> pd.DataFrame:
    # JE9PEL specific columns
    column_names = ["name", "norad_cat_id", "uplink", "downlink", "beacon", "mode", "callsign", "status"]
    # Read the CSV file
    df = pd.read_csv(file_path, sep=";", header=None, names=column_names)
    return df


def write_df_as_json(df: pd.DataFrame, file_path: str | Path):
    # Save the DataFrame as a JSON file
    df.to_json(file_path, orient="records", lines=True)


def write_json_to_file(data, file_path):
    logging.info(f"Writing {Path(file_path).absolute()}")
    with Path(file_path).open("w") as file:
        json.dump(data, file, indent=4)


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
    je9pel_url = "http://www.ne.jp/asahi/hamradio/je9pel/satslist.csv"
    cache_dir = Path(__file__).parent / "cache"
    filename = "je9pel.csv"

    if use_cache:
        logging.info("Referencing local cache.")
        logging.info("Fetching JE9PEL satellite frequency data.")

    else:
        logging.info("Creating local cache.")
        cache_dir = initialize_cache_directory(directory_path=cache_dir, files_to_remove=[filename])

        logging.info("Fetching JE9PEL satellite frequency data.")
        csv_data = download_csv(je9pel_url)
        write_csv_to_file(csv_data, cache_dir / filename)

    data = load_csv(cache_dir / filename)

    return data


## Filter ##


def parse_frequencies(freq_str):
    # Check if the frequency string is empty, NaN, or doesn't contain numeric values
    if not freq_str or pd.isna(freq_str) or not re.search(r"\d", freq_str):
        return []

    freqs = []
    # Split multiple frequencies separated by backslash
    for freq in freq_str.split("/"):
        # Ignore frequencies with "GHz"
        if "GHz" in freq:
            continue

        # Check for special active frequency indicated by '*'
        is_active = "*" in freq
        freq = freq.replace("*", "").strip()

        # Check for frequency range indicated by '-'
        if "-" in freq:
            low, high = freq.split("-")
            freqs.append({"low": float(low.strip()), "high": float(high.strip()), "active": is_active})
        else:
            # Single frequency value
            try:
                freqs.append({"low": float(freq), "high": np.nan, "active": is_active})
            except ValueError:
                # Handle any unexpected non-numeric values
                continue

    return freqs


def merge_freq_dicts(freq_list):
    unique_freqs = []
    seen = set()
    for freq_dict in freq_list:
        # Create a tuple representation of the dictionary to check for uniqueness
        freq_tuple = tuple(freq_dict.items())
        if freq_tuple not in seen:
            seen.add(freq_tuple)
            unique_freqs.append(freq_dict)
    return unique_freqs


def is_within_band(freq_dict):
    # Check if any frequency in the dictionary falls within the defined bands
    for freq_info in freq_dict:
        freq_low = freq_info["low"] * 1e6
        freq_high = freq_info.get("high", freq_low) * 1e6  # Use low freq if high freq is not specified

        if VHF_LOW <= freq_low <= VHF_HIGH or VHF_LOW <= freq_high <= VHF_HIGH:
            return True
        if UHF_LOW <= freq_low <= UHF_HIGH or UHF_LOW <= freq_high <= UHF_HIGH:
            return True

    return False


def unique_list_or_all(series):
    if len(series) > 1 and len(series.unique()) > 1:
        return list(series)
    return series.iloc[0]


def filter(df: pd.DataFrame):
    # Filter out rows with NaN in norad_id
    df = df[df["norad_cat_id"].notna()].copy()

    # Convert norad_id to integer (pandas nonsensible, have to copy above for this to work)
    df["norad_cat_id"] = df["norad_cat_id"].astype(int)

    # Filter out rows where both 'downlink' and 'beacon' are empty
    df = df[~(df["downlink"].isna() & df["beacon"].isna())]

    # Keep only rows where sat is in active, weather, or deep space
    # Most weather sats are active, despite JE9PEL not indicating so in the csv
    df = df[df.status.isin(["active", "weather", "deep space"])]

    # Parse the frequency string for downlinks and beacons
    df["parsed_downlink"] = df["downlink"].apply(parse_frequencies)
    df["parsed_beacon"] = df["beacon"].apply(parse_frequencies)

    # Filter rows where either 'downlink' or 'beacon' has a frequency within the band
    df["parsed_downlink"] = df["parsed_downlink"].apply(
        lambda freq_list: [freq for freq in freq_list if is_within_band([freq])]
    )
    df["parsed_beacon"] = df["parsed_beacon"].apply(
        lambda freq_list: [freq for freq in freq_list if is_within_band([freq])]
    )
    df = df[df.apply(lambda row: any(row["parsed_downlink"]) or any(row["parsed_beacon"]), axis=1)]

    # Drop the original 'downlink' and 'beacon' columns
    df = df.drop(columns=["downlink", "beacon"])

    # Rename 'parsed_downlink' to 'downlink' and 'parsed_beacon' to 'beacon'
    df = df.rename(columns={"parsed_downlink": "downlink", "parsed_beacon": "beacon"})

    # Group by norad_cat_id and aggregate
    df = (
        df.groupby("norad_cat_id")
        .agg(
            {
                "name": lambda x: list(x) if len(x) > 1 else x.iloc[0],
                "uplink": "first",
                "mode": lambda x: unique_list_or_all(x),
                "callsign": lambda x: unique_list_or_all(x),
                "status": lambda x: unique_list_or_all(x),
                "downlink": lambda x: merge_freq_dicts(sum(x, [])),
                "beacon": lambda x: merge_freq_dicts(sum(x, [])),
            }
        )
        .reset_index()
    )

    return df


## Transform ##


def transform(df: pd.DataFrame) -> dict:
    # Serialize dataframe to json; this will properly and, among other methods, most straightforwardly
    # convert NaN's to nulls.
    logging.info("Formatting database to normalized dictionary form.")
    data_json = df.to_json(orient="records")

    # To (lazily) fix the foward slashes added from DataFrame -> json, we load as dict and *then* write out.
    data = json.loads(data_json)

    return data


## Format ##


def format(data):
    """Re-index the dictionary by 'norad_cat_id' as the primary key"""
    logging.info("Reindexing data to use norad_id as primary key.")
    je9pel_db = {}
    for d in data:
        key = d["norad_cat_id"]
        inner_dict = d.copy()
        je9pel_db[key] = inner_dict
    return je9pel_db


## Entrypoint ##


def generate_db(use_cache=False):
    logging.info("Starting JE9PEL data generation.")

    # Fetch
    data = fetch(use_cache)

    # Validate

    # Filter
    data = filter(data)

    # Transform
    data = transform(data)

    # Format
    data = format(data)

    # Export as json
    path = Path(__file__).parent / "cache" / "je9pel.json"
    write_json_to_file(data, path)

    logging.info(f"Total number of observable JE9PEL satellites: {len(data)}")
    logging.info("JE9PEL database generation complete.")

    return data


if __name__ == "__main__":
    generate_db(use_cache=True)
