"""
Generate a json database comprising satellite metadata, TLE, and TX frequencies. Data is sourced from 
Satnogs, as they provide the only complete list of TX frequencies.

Note:
Need method for handling satellites that no longer have TLE in "tle.json".
Schema validation would improve.
"""

import json
import logging
from pathlib import Path
import requests
import pandas as pd
from hamilton.database.config import DBUpdateConfig
from hamilton.database.je9pel import JE9PELGenerator


class SatcomDBGenerator:
    def __init__(self, config: DBUpdateConfig, je9pel: JE9PELGenerator, logger=None):
        self.config = config
        self.je9pel = je9pel
        self.transmitters_url = config.SATNOGS_TRANSMITTERS_URL
        self.satellites_url = config.SATNOGS_SATELLITES_URL
        self.tle_url = config.SATNOGS_TLE_URL
        self.cache_dir = Path(__file__).parent / "cache"
        if logger:
            self.log = logger
        else:
            logging.basicConfig(
                format="[%(asctime)s] (%(levelname)s) %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                level=logging.INFO,
            )
            self.log = lambda x, y: logging.info(y)

    def set_logger(self, logger):
        self.log = logger
        self.je9pel.set_logger(logger)

    ## I/O and HTTP Requests ##

    @staticmethod
    def download_json_data(url: str) -> dict:
        response = requests.get(url)
        return json.loads(response.text)

    @staticmethod
    def load_json(path):
        with open(path) as f:
            return json.load(f)

    def write_json_to_file(self, data, file_path):
        self.log("INFO", f"Writing {Path(file_path).absolute()}")
        with Path(file_path).open("w") as file:
            json.dump(data, file, indent=4)

    def initialize_cache_directory(self, files_to_remove: list = []) -> None:
        cache_dir = Path(self.cache_dir)
        # Ensure the directory exists
        cache_dir.mkdir(exist_ok=True)

        # Remove specific files if they exist
        for file_name in files_to_remove:
            file_path = cache_dir / file_name
            if file_path.is_file():
                file_path.unlink()

        return cache_dir

    ## Data Extraction ##

    def fetch(self, use_cache=False):
        if use_cache:
            self.log("INFO", "Referencing local cache.")

            self.log("INFO", "Fetching TLE data.")
            tle_data = self.load_json(self.cache_dir / "tle.json")

            self.log("INFO", "Fetching satellite data.")
            satellites_data = self.load_json(self.cache_dir / "satellites.json")

            self.log("INFO", "Fetching transmitter data.")
            transmitters_data = self.load_json(self.cache_dir / "transmitters.json")

        else:
            self.log("INFO", "Creating local cache.")
            files_to_remove = ["tle.json", "satellites.json", "transmitters.json"]
            self.cache_dir = self.initialize_cache_directory(files_to_remove=files_to_remove)

            self.log("INFO", "Fetching TLE data.")
            tle_data = self.download_json_data(self.tle_url)
            self.write_json_to_file(tle_data, self.cache_dir / "tle.json")

            self.log("INFO", "Fetching satellite data.")
            satellites_data = self.download_json_data(self.satellites_url)
            self.write_json_to_file(satellites_data, self.cache_dir / "satellites.json")

            self.log("INFO", "Fetching transmitter data.")
            transmitters_data = self.download_json_data(self.transmitters_url)
            self.write_json_to_file(transmitters_data, self.cache_dir / "transmitters.json")

        return tle_data, satellites_data, transmitters_data

    ## Data Validation ##

    @staticmethod
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

    @staticmethod
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

    def validate(self, tle_data, satellite_data, transmitter_data):
        self.log("INFO", "Validating 1:1 TLE:sat_UUID.")
        assert self.is_value_unique(tle_data, "sat_id")

        self.log("INFO", "Validating non-empty sat_UUID.")
        assert self.is_nonempty(satellite_data, "sat_id")

        self.log("INFO", "Validating unique sat_UUID.")
        assert self.is_value_unique(satellite_data, "sat_id")

        self.log("INFO", "Validating 1:many map of sat_UUID:transmitter.")
        assert not self.is_value_unique(transmitter_data, "sat_id")

    def validate_norad_ids(self, data):
        self.log("INFO", "Validating nonempty NORAD satellites.")
        assert self.is_nonempty(data, "norad_cat_id")

        self.log("INFO", "Validating unique NORAD satellites.")
        assert self.is_value_unique(data, "norad_cat_id")

    ## Data Transformation ##

    def filter_by_transmitter_frequency(self, df: pd.DataFrame) -> dict:
        """Filter the database by downlink frequency ranges"""

        # First exlode the dataframe, which creates a row for each transmitter
        df_exploded = df.explode("transmitters")

        # Create two new columns corresponding to downlink high and low
        df_exploded["tx_dl_low"] = df_exploded["transmitters"].map(lambda x: x["downlink_high"])
        df_exploded["tx_dl_high"] = df_exploded["transmitters"].map(lambda x: x["downlink_low"])

        # Create two new columns associated with tx alive (true, false) and status (active, inactive)
        df_exploded["tx_alive"] = df_exploded["transmitters"].map(lambda x: x["alive"])
        df_exploded["tx_status"] = df_exploded["transmitters"].map(lambda x: x["status"])

        # Filter out dead or inactive transmitters
        df_exploded = df_exploded[(df_exploded["tx_alive"] == True) & (df_exploded["tx_status"] == "active")]

        # Filter out null downlink low AND high freqs
        df_exploded = df_exploded[df_exploded["tx_dl_low"].notnull() | df_exploded["tx_dl_high"].notnull()]

        # Replace nans in transmitter downlink freq ranges with its associated high or low
        df_exploded["tx_dl_low"] = df_exploded["tx_dl_low"].fillna(df_exploded["tx_dl_high"])
        df_exploded["tx_dl_high"] = df_exploded["tx_dl_high"].fillna(df_exploded["tx_dl_low"])

        # Filter transmitter frequences to specified VHF range
        df_filtered = df_exploded[
            ((df_exploded["tx_dl_low"] >= self.config.VHF_LOW) & (df_exploded["tx_dl_high"] <= self.config.VHF_HIGH))
            | ((df_exploded["tx_dl_low"] >= self.config.UHF_LOW) & (df_exploded["tx_dl_high"] <= self.config.UHF_HIGH))
        ]

        # "Implode" the dataframe, s.t. each row now represents a satellite with many transmitters
        agg_cols = {
            col: "first"
            for col in df_filtered.columns
            if col not in ["transmitters", "sat_id", "tx_dl_low", "tx_dl_high"]
        }
        df_imploded = (
            df_filtered.groupby("sat_id").agg({**agg_cols, "transmitters": lambda x: x.tolist()}).reset_index()
        )

        return df_imploded

    def transform(self, tle_data, satellite_data, transmitter_data):
        # Convert to DataFrames
        df_tle = pd.DataFrame(tle_data)
        df_satellites = pd.DataFrame(satellite_data)
        df_transmitters = pd.DataFrame(transmitter_data)

        # Merge TLE DataFrame with satellite DataFrame
        # This will only select satellites that have an associated TLE.
        self.log("INFO", "Merging TLE's with satellites based on sat_UUID.")
        df = pd.merge(df_tle, df_satellites, on="sat_id")

        # Validate and merge norad_cat_ids.
        norad_cat_id_equal = df["norad_cat_id_x"].equals(df["norad_cat_id_y"].astype(int))
        assert norad_cat_id_equal, "`norad_cat_id` mismatch between tle.json and satellites.json"
        df = df.drop("norad_cat_id_y", axis=1)
        df = df.rename(columns={"norad_cat_id_x": "norad_cat_id"})

        # Rename `updated` and `citation` keys with parent suffix.
        df = df.rename(columns={"updated_x": "updated_tle"})
        df = df.rename(columns={"updated_y": "updated_satellite"})
        df = df.rename(columns={"citation": "citation_satellite"})

        # Drop `image` column.
        df = df.drop("image", axis=1)

        # Filter out any dead or satellits that have re-entered the atmosphere.
        self.log("INFO", "Filtering dead or re-entered satellites.")
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
        self.log("INFO", "Merging TLE + Satellite dataframe with transmitter dataframe.")
        df_merged = pd.merge(df, df_transmitters_2, on="sat_id")

        # Explode DataFrame and prune based on prescribed frequency bands.
        self.log("INFO", "Filtering database by frequency bands.")
        df_final = self.filter_by_transmitter_frequency(df_merged)

        # Serialize dataframe to json; this will properly and, among other methods, most straightforwardly
        # convert NaN's to nulls.
        self.log("INFO", "Formatting database to normalized dictionary form.")
        data_json = df_final.to_json(orient="records")

        # To (lazily) fix the foward slashes added from DataFrame -> json, we load as dict and *then* write out.
        data = json.loads(data_json)

        return data

    ## Format ##

    def format(self, data) -> dict:
        """Re-index the dictionary by satnogs 'norad_cat_id' as the primary key"""
        self.log("INFO", "Reindexing data to use norad_cat_id as primary key.")
        satcom_db = {}
        for d in data:
            #key = d["sat_id"]
            key = d["norad_cat_id"]
            inner_dict = d.copy()
            satcom_db[key] = inner_dict
        return satcom_db

    ## Merge ##
    def merge_with_je9pel(self, data: dict, je9pel_data: dict):
        # Iterate over each item in the satcom dictionary
        for sat_id, details in data.items():
            # Get the 'norad_cat_id' from the current entry
            norad_cat_id = details.get("norad_cat_id")

            # Check if 'norad_cat_id' exists in the je9pel dictionary
            if norad_cat_id in je9pel_data:
                # Add the corresponding entry from the je9pel dictionary
                # under the key "je9pel"
                details["je9pel"] = je9pel_data[norad_cat_id]

            else:
                details["je9pel"] = None
                self.log("DEBUG", f"NORAD CAT ID {norad_cat_id} in JE9PEL but not Satnogs DB. Skipping..")

        return data

    ## Entrypoint ##

    def generate_db(self, use_cache=False):
        self.log("INFO", "Starting SATCOM database generation.")

        # Fetch
        tle_data, satellite_data, transmitter_data = self.fetch(use_cache)

        # Validate
        self.validate(tle_data, satellite_data, transmitter_data)

        # Transform
        data = self.transform(tle_data, satellite_data, transmitter_data)

        # Re-Validate
        self.validate_norad_ids(data)

        # Format
        data = self.format(data)

        # Merge with JE9PEL
        je9pel_data = self.je9pel.generate_db(use_cache=use_cache)
        # import ipdb; ipdb.set_trace()
        data = self.merge_with_je9pel(data, je9pel_data)

        # Export as json
        path = Path(__file__).parent / "satcom.json"
        self.write_json_to_file(data, path)

        self.log("INFO", f"Total number of observable satellites: {len(data)}")
        self.log("INFO", "SATCOM database generation complete.")

        return data

    def get_cached_db(self):
        self.log("INFO", "Fetching cached SATCOM database.")
        path = Path(__file__).parent / "satcom.json"
        with open(path) as f:
            d = json.load(f)
        return d


if __name__ == "__main__":
    je9pel = JE9PELGenerator(DBUpdateConfig)
    generator = SatcomDBGenerator(DBUpdateConfig, je9pel)
    generator.generate_db(use_cache=False)
