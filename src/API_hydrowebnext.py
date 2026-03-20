import logging
import sys
import argparse
from datetime import datetime
from importlib.metadata import version
try:
    import py_hydroweb
except ImportError:
    print("Problem importing py_hydroweb")
    exit(1)
# Check py-hydroweb version
latest_version = "1.1.0"
if version("py_hydroweb") < latest_version:
    logging.getLogger().warning(
        f"\033[33mConsider upgrading py-hydroweb to {latest_version}\033[0m"
    )

# ******************************************************************************


def main(
    api_key_hydroweb,
    lon_start, lat_start,
    lon_end, lat_end,
    start_date, end_date,
    output_folder
):
    # Set log config
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    # Create a client
    #  - either using the API-Key environment variable
    #    (HYDROWEB_API_KEY) client: py_hydroweb.Client =
    #    py_hydroweb.Client("https://hydroweb.next.theia-land.fr/api")
    #  - or explicitly giving API-Key
    client: py_hydroweb.Client = py_hydroweb.Client(
        "https://hydroweb.next.theia-land.fr/api",
        api_key=api_key_hydroweb
    )

    # Initiate a new download basket (input the name you want here)
    basket: py_hydroweb.DownloadBasket = py_hydroweb.DownloadBasket(
        "my_download_basket"
    )

    # Add collections in our basket
    bbox = [float(lon_start), float(lat_start),
            float(lon_end), float(lat_end)]
    query = {
        "start_datetime": {"lte": start_date},
        "end_datetime": {"gte": end_date}
    }
    basket.add_collection(
        "HYDROWEB_RIVERS_OPE",
        bbox=bbox,
        query=query
    )

    # Do download (input the archive name you want here,
    # and optionally an output folder)
    now = datetime.today().strftime("%Y%m%dT%H%M%S")
    downloaded_zip_path: str = client.submit_and_download_zip(
        basket,
        zip_filename=f"my_hydroweb_data_{now}.zip",
        output_folder=output_folder
    )

    print(downloaded_zip_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download Hydroweb data.")

    parser.add_argument("api_key_hydroweb")
    parser.add_argument("lon_start")
    parser.add_argument("lat_start")
    parser.add_argument("lon_end")
    parser.add_argument("lat_end")
    parser.add_argument("start_date")
    parser.add_argument("end_date")
    parser.add_argument("output_folder")

    args = parser.parse_args()

    main(
        args.api_key_hydroweb,
        args.lon_start,
        args.lat_start,
        args.lon_end,
        args.lat_end,
        args.start_date,
        args.end_date,
        args.output_folder
    )

# ******************************************************************************
