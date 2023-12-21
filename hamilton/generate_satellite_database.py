"""
Generate a json database comprising satellite metadata, TLE, and TX frequencies. Data is sourced from 
Satnogs, as they provide the only complete list of TX frequencies.

Note:
Need method for handling satellites that no longer have TLE in "tle.json".
"""

import json
import pandas as pd
import requests

import tempfile
from pathlib import Path
from collections import Counter


API_BASE_URL = "https://db.satnogs.org/api/"
TX_URL = API_BASE_URL + "transmitters/?format=json"
SATELLITES_URL = API_BASE_URL + "satellites/?format=json"
TLE_URL = API_BASE_URL + "tle/?format=json"

VHF_LOW = 143e6
VHF_HIGH = 147e6
UHF_LOW = 430e6
UHF_HIGH = 440e6


def download_satnogs_endpoint_json(url, json_path):
    response = requests.get(url)
    if response.status_code == 200:
        with open(json_path, "w") as file:
            file.write(response.text)
    return response.status_code


def get_satnogs_tx(base_dir="./"):
    json_path = Path(base_dir) / "transmitters.json"
    url = TX_URL
    print(f"Downloading {json_path} from {url}")
    status_code = download_satnogs_endpoint_json(url, json_path)
    print(f"STATUS: {status_code}")
    return json_path, status_code


def get_satnogs_sats(base_dir="./"):
    json_path = Path(base_dir) / "satellites.json"
    url = SATELLITES_URL
    print(f"Downloading {json_path} from {url}")
    status_code = download_satnogs_endpoint_json(url, json_path)
    print(f"STATUS: {status_code}")
    return json_path, status_code


def get_satnogs_tle(base_dir="./"):
    json_path = Path(base_dir) / "tle.json"
    url = TLE_URL
    print(f"Downloading {json_path} from {url}")
    status_code = download_satnogs_endpoint_json(url, json_path)
    print(f"STATUS: {status_code}")
    return json_path, status_code


def load_json(path):
    with open(path, "r") as f:
        data = f.read()
    return json.loads(data)


def write_json(data, path):
    with open(path, "w") as f:
        json.dump(data, f)


def check_unique_key(data, key):
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
    uniqueQ = len(values) == len(set(values))
    return uniqueQ


def check_nonempty(data, key):
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
    nonemptyQ = not (None in [d[key] for d in data])
    return nonemptyQ


def find_duplicates(lst):
    count = Counter(lst)
    return [item for item in count if count[item] > 1]


def generate_sat_db(temp=True, use_cache=False, save_json=True):
    """
    Generate a json database comprising satellite metadata, TLE, and TX frequencies via satnogs http request.

    Args:
        temp: bool, if true use temp filesystem else save response jsons to current directory
        use_cache: if true, use repsonse jsons in local directory, else fetch from remote

    Returns:
        dict, Dictionary of satellite orbits (alive), freqs, and metadata. Custom format.
    """
    # use satnogs db api to download three relevant jsons as dictionaries
    # load raw satnogs jsons from local directory
    if use_cache:
        tx_data = load_json("./transmitters.json")
        sat_data = load_json("./satellites.json")
        tle_data = load_json("./tle.json")
    # create temporary directory to store raw satnogs jsons from http requests
    elif temp:
        with tempfile.TemporaryDirectory() as temp_dir:
            tx_json, _ = get_satnogs_tx(base_dir=temp_dir)
            tx_data = load_json(tx_json)
            sat_json, _ = get_satnogs_sats(base_dir=temp_dir)
            sat_data = load_json(sat_json)
            tle_json, _ = get_satnogs_tle(base_dir=temp_dir)
            tle_data = load_json(tle_json)
    # store raw satnogs jsons from http requests to local directory
    else:
        tx_json, _ = get_satnogs_tx()
        tx_data = load_json(tx_json)
        sat_json, _ = get_satnogs_sats()
        sat_data = load_json(sat_json)
        tle_json, _ = get_satnogs_tle()
        tle_data = load_json(tle_json)

    # convert satnogs dicts to dataframes
    tx_df = pd.DataFrame(tx_data)
    tle_df = pd.DataFrame(tle_data)
    sat_df = pd.DataFrame(sat_data)

    # check tle.json to ensure all sat_id's are unique
    print(f"Testing for unique TLEs: {check_unique_key(tle_data, 'sat_id')}")

    # check satellites.json to ensure all sat_id's are unique
    print(f"Testing for unique satellites: {check_unique_key(sat_data, 'sat_id')}")
    print(f"Testing for nonempty satellites: {check_nonempty(sat_data, 'sat_id')}")

    # check transmitters.json to ensure all sat_id's are unique. Should be false, given 1:many map of sat:tx
    print(f"Testing for unique transmitters: {check_unique_key(tx_data, 'sat_id')}")

    # merge tle dataframe with satellites dataframe. this will only select satellites that have a TLE
    df = pd.merge(tle_df, sat_df, on="sat_id")

    # merge norad_cat_id key's if the same
    norad_cat_id_equal = df["norad_cat_id_x"].equals(df["norad_cat_id_y"].astype(int))
    if norad_cat_id_equal:
        df = df.drop("norad_cat_id_y", axis=1)
        df = df.rename(columns={"norad_cat_id_x": "norad_cat_id"})
    else:
        print(f"`norad_cat_id` mismatch between TLE_JSON and SATELLITES_JSON")

    # rename `updated` and `citation` keys with parent suffix
    df = df.rename(columns={"updated_x": "updated_tle"})
    df = df.rename(columns={"updated_y": "updated_satellite"})
    df = df.rename(columns={"citation": "citation_satellite"})

    # drop `image` column
    df = df.drop("image", axis=1)

    # filter out dead or re-entered satellites
    df = df[df["status"] == "alive"]

    # group tx dataframe rows by `sat_id` and convert each group to a list of dictionaries
    tx_df2 = tx_df.groupby("sat_id").apply(
        lambda x: x.drop("sat_id", axis=1).to_dict(orient="records")
    )

    # reset the index of the tx dataframe to an integer index, name list of dictionaries
    # column as `transmitters`
    # this prepares the tx dataframe for merging
    tx_df2 = tx_df2.reset_index()
    tx_df2 = tx_df2.rename(columns={0: "transmitters"})

    # merge (tle+sat) dataframe with tx dataframe
    # this will only select `sat_id`s that exist in both (tle+sat) dataframe and tx dataframe
    df2 = pd.merge(df, tx_df2, on="sat_id")

    # in the following we are going to filter the database by downlink frequency ranges
    # first exlode the dataframe, which creates a row for each transmitter
    df3 = df2.explode("transmitters")

    # create two new columns corresponding to downlink high and low
    df3["tx_dl_low"] = df3["transmitters"].map(lambda x: x["downlink_high"])
    df3["tx_dl_high"] = df3["transmitters"].map(lambda x: x["downlink_low"])

    # create two new columns associated with tx alive (true, false) and status (active, inactive)
    df3["tx_alive"] = df3["transmitters"].map(lambda x: x["alive"])
    df3["tx_status"] = df3["transmitters"].map(lambda x: x["status"])

    # filter out dead or inactive transmitters
    df3 = df3[(df3["tx_alive"] == True) & (df3["tx_status"] == "active")]

    # filter out null downlink low AND high freqs
    df3 = df3[df3["tx_dl_low"].notnull() | df3["tx_dl_high"].notnull()]

    # replace nans in transmitter downlink freq ranges with its associated high or low
    df3["tx_dl_low"] = df3["tx_dl_low"].fillna(df3["tx_dl_high"])
    df3["tx_dl_high"] = df3["tx_dl_high"].fillna(df3["tx_dl_low"])

    # filter transmitter frequences to specified VHF range
    df4 = df3[
        ((df3["tx_dl_low"] >= VHF_LOW) & (df3["tx_dl_high"] <= VHF_HIGH))
        | ((df3["tx_dl_low"] >= UHF_LOW) & (df3["tx_dl_high"] <= UHF_HIGH))
    ]

    # "implode" the dataframe, s.t. each row now represents a satellite with many transmitters
    agg_cols = {
        col: "first"
        for col in df4.columns
        if col not in ["transmitters", "sat_id", "tx_dl_low", "tx_dl_high"]
    }
    df5 = (
        df4.groupby("sat_id").agg({**agg_cols, "transmitters": lambda x: x.tolist()}).reset_index()
    )

    # export dataframe to json; this will properly and, among other methods, most straightforwardly
    # convert NaN's to nulls
    df_json = df5.to_json(orient="records")

    # to (lazily) fix the foward slashes added from pd.to_json, we load as dict and *then* write out
    df_dict = json.loads(df_json)

    # check dataframe to ensure all norad_cat_id's are unique
    print(f"Testing for unique NORAD satellites: {check_unique_key(df_dict, 'norad_cat_id')}")
    print(f"Testing for nonempty NORAD satellites: {check_nonempty(df_dict, 'norad_cat_id')}")

    # index the dictionary by satnogs 'sat_id' as the primary key
    sat_db = {}
    for d in df_dict:
        key = d["sat_id"]
        inner_dict = d.copy()
        inner_dict.pop("sat_id")
        sat_db[key] = inner_dict

    # write dict to json path
    if save_json:
        sat_tle_tx_json = "./sat_tle_tx.json"
        print(f"Writing cleaned and formatted database to {sat_tle_tx_json}")
        write_json(sat_db, sat_tle_tx_json)

    print(f"Total number of observable satellites: {len(sat_db)}")

    return sat_db


if __name__ == "__main__":
    sat_db = generate_sat_db(temp=False, use_cache=False)
    #sat_db = generate_sat_db(temp=False, use_cache=True)