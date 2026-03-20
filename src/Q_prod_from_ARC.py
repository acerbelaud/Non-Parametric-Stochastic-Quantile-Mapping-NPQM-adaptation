#!/usr/bin/env python3
# ******************************************************************************
# Q_prod_from_ARC.ipynb
# ******************************************************************************

# Purpose:
# Producing discharge estimates from altimetric rating curves and WSE data
# Author:
# Arnaud Cerbelaud, 2026


# ******************************************************************************
# Import Python modules and set file/folder locations
# ******************************************************************************

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from scipy.interpolate import interp1d
import zipfile
from datetime import datetime
import subprocess
import requests
from dotenv import load_dotenv

# File location
FILE_DIR = Path(__file__).resolve().parent
print(FILE_DIR)

# Project root
PROJECT_ROOT = FILE_DIR.parents[0]
print(PROJECT_ROOT)

# Retrieving hydrowebnext api key for WSE data download
load_dotenv(PROJECT_ROOT / ".env")
print(os.getenv("HYDROWEBNEXT_API_KEY"))
# Fill in your own hydroweb.next API key in your .env file
# (need to create a free account to get a key)
api_key_hydroweb = os.getenv("HYDROWEBNEXT_API_KEY")
if api_key_hydroweb is None:
    raise ValueError("Please set HYDROWEBNEXT_API_KEY environment variable")


# ******************************************************************************
# Functions
# ******************************************************************************


# Function to remove outliers in WSE
def remove_outliers(series, threshold=2):
    # Removes outliers
    mean = series.mean()
    std_dev = series.std()
    z_scores = (series - mean) / std_dev
    filtered_series = series[abs(z_scores) < threshold]
    return filtered_series


def remove_uncertain_wse(series, series_u, threshold=1):
    std_dev = series.std()
    return series[series_u < threshold*std_dev]


def replace_inf_with_min(arr):
    finite_min = np.min(arr[np.isfinite(arr)])
    return np.where(np.isfinite(arr), arr, finite_min)


# ******************************************************************************
# This is the NPQM rating curve database, calibrated using Hydrowebnext
# river WSE data downloaded in early 2025, and the MeanDRS reference model
ARCfilename = "ARC_NPQM_hydroweb_ope_MeanDRS_flags"

# Columns that give the name of
# the ID of the VS
# the ID of the reach location that the VS was snapped to
# the altimeter used in the altimetric_wse_files
# the name of the basin in which the VS is
# the name of the river on which the VS is
# the distance along the river in km
# the longitude
# the latitude
# the width of the river at that VS
# the name of the station
ID_VS = 'ID'
ID_Q = 'COMID'
satvar = 'MISSION(S)-TRACK(S)'
basin_name_db = 'BASIN'
river_name_db = 'RIVER'
distance_name_db = 'REFERENCE DISTANCE (km)'
lon_name_db = 'REFERENCE LONGITUDE'
lat_name_db = 'REFERENCE LATITUDE'
width_db = 'APPROX. WIDTH OF REACH (m)'
station_db = 'STATION'


# ******************************************************************************
# Declaration of variables (given as command line arguments)
# ******************************************************************************
# 1 - data_folder (e.g. "./")
# 2 - VSs         (IDs, e.g. 7176,7177,... or one river_name, eg "YELLOWSTONE")
# 3 - KGE_thresh  (e.g. 0.0)
# 4 - start_date  (e.g. "2000-01-01")
# 5 - end_date    (e.g. "2024-12-01")

# ******************************************************************************
# Get command line arguments
# ******************************************************************************

if len(sys.argv) != 6:
    print('ERROR - 5 arguments must be used')
    print("data_folder VSs KGE_thresh start_date end_date")
    raise SystemExit(22)

data_folder = sys.argv[1]
VSs = sys.argv[2]
KGE_thresh = sys.argv[3]
start_date = sys.argv[4]
end_date = sys.argv[5]

# ******************************************************************************
# 1- Check data_folder exists
# ******************************************************************************

data_path = Path(data_folder).resolve()

if not data_path.exists():
    print(f"ERROR - data_folder does not exist: {data_folder}")
    raise SystemExit(1)

if not data_path.is_dir():
    print(f"ERROR - data_folder is not a directory: {data_folder}")
    raise SystemExit(1)

# ******************************************************************************
# 2- Validate VSs
# ******************************************************************************

# Option A: list of integers like "7176,7177,7178"
if "," in VSs:
    try:
        IDs = [int(v.strip()) for v in VSs.split(",")]
    except ValueError:
        print("ERROR - VSs must be integers separated by commas, no space")
        raise SystemExit(1)

# Option B: single integer
elif VSs.isdigit():
    IDs = [int(VSs)]

# Option C: river name (string)
else:
    VSs = VSs.strip()
    if len(VSs) == 0:
        print("ERROR - VSs cannot be empty")
        raise SystemExit(1)
    IDs = []
    river_name = VSs

# ******************************************************************************
# 3- Validate KGE_thresh (must be float)
# ******************************************************************************

try:
    KGE_thresh = float(KGE_thresh)
except ValueError:
    print("ERROR - KGE_thresh must be a float")
    raise SystemExit(1)

# Optional: enforce reasonable KGE range
if not (-1 <= KGE_thresh <= 1):
    print("WARNING - KGE_thresh outside typical range [-1, 1]")

# ******************************************************************************
# 4 and 5- Validate dates (YYYY-MM-DD format)
# ******************************************************************************


def validate_date(date_string, name):
    try:
        datetime.strptime(date_string, "%Y-%m-%d")  # only checks format
        return date_string                          # keep it as string
    except ValueError:
        print(f"ERROR - {name} must be in format YYYY-MM-DD")
        raise SystemExit(1)


start_date = validate_date(start_date, "start_date")
end_date = validate_date(end_date, "end_date")

# Compare by parsing temporarily
if (
    datetime.strptime(start_date, "%Y-%m-%d")
    >= datetime.strptime(end_date, "%Y-%m-%d")
):
    print("ERROR - start_date must be before end_date")
    sys.exit(1)

print("All inputs validated successfully.")


# ******************************************************************************
# Uploading JPL NPQM  altimetric rating curves (ARC)
# ******************************************************************************

ARC_path = PROJECT_ROOT / "zenodo" / ARCfilename
pickle_path = ARC_path.with_suffix(".pkl")
excel_path = ARC_path.with_suffix(".xlsx")

# Ensure the folder exists
ARC_path.parent.mkdir(parents=True, exist_ok=True)

# Check if file exists
if pickle_path.exists() or excel_path.exists():
    print(f"{ARCfilename} found locally.")
else:
    print(f"{ARCfilename} not found locally. Downloading from Zenodo...")
    doi = "https://doi.org/10.5281/zenodo.19006996"
    zenodo_url = (
        "https://zenodo.org/records/19006998/files/"
        + ARCfilename
        + ".pkl"
    )
    try:
        response = requests.get(zenodo_url)
        response.raise_for_status()
        with open(pickle_path, "wb") as f:
            f.write(response.content)
        print("Download complete.")
    except:
        print(
            "Can't download from Zenodo."
            "Check Internet connection or permissions."
        )
        raise SystemExit(1)

# Read the file
if pickle_path.exists():
    df_ARCs = pd.read_pickle(pickle_path)
elif excel_path.exists():
    df_ARCs = pd.read_excel(ARC_path, skiprows=[0], index_col=0)


# ******************************************************************************
# Filtering the VS database
# ******************************************************************************

if IDs == []:
    IDs = (
        df_ARCs[
            (df_ARCs[river_name_db] == river_name)
            & (df_ARCs['KGE'] > KGE_thresh)
        ]
        .sort_values(by='uparea')
        .index
        .to_list()
    )
    if len(IDs) == 0:
        print(
            "River name "
            + river_name
            + " doesn't appear to exist in the database."
        )
        raise SystemExit(1)

missing_IDs = set(IDs)-set(df_ARCs.index)
if missing_IDs:
    print("The following IDs are not present in the rating curve database:")
    print(missing_IDs)
else:
    print("All IDs are present in the rating curve database")

df_ARCs = df_ARCs[df_ARCs.index.isin(IDs)]


# ******************************************************************************
# Downloading WSE data from hydroweb.next
# ******************************************************************************

lon_start = str(df_ARCs[lon_name_db].min()-0.05)
lat_start = str(df_ARCs[lat_name_db].min()-0.05)
lon_end = str(df_ARCs[lon_name_db].max()+0.05)
lat_end = str(df_ARCs[lat_name_db].max()+0.05)

result = subprocess.run(
    [
        "python",
        "API_hydrowebnext.py",
        str(api_key_hydroweb),
        lon_start, lat_start,
        lon_end, lat_end,
        start_date,
        end_date,
        str(data_path)
    ],
    cwd=FILE_DIR,
    capture_output=True,
    text=True
    # check=True
)
print("STDOUT:\n", result.stdout)
print("STDERR:\n", result.stderr)
print("Return code:", result.returncode)

zip_path = result.stdout.strip().split("\n")[-1]
print("Downloaded file: ", zip_path)

extract_folder = Path(zip_path).with_suffix("")

with zipfile.ZipFile(zip_path, 'r') as zip_ref:
    zip_ref.extractall(extract_folder)

# Only keep the Hydrowebnext files corresponding to the IDs that are in the
# rating curve database (df_ARCs). That way, if there are other virtual
# stations in the bounding box (from other rivers, or new virtual stations)
# that are downloaded, we discard them.
# Build all patterns once
patterns = [
    (
        f"{row[basin_name_db]}_"
        f"{row[river_name_db]}_"
        f"KM{int(row[distance_name_db]):04d}"
    )
    for _, row in df_ARCs.iterrows()
]

kept_files = []
for root, dirs, files in os.walk(extract_folder):
    for filename in files:
        full_path = Path(root) / filename
        if any(p in filename for p in patterns) and filename.endswith(".txt"):
            kept_files.append(full_path)
        else:
            full_path.unlink()

print(f"Kept {len(kept_files)} files")

# Delete the zip after extraction and filtering
Path(zip_path).unlink()
print(f"Deleted zip file {Path(zip_path).name}")


# ******************************************************************************
# Reading and rearranging the Hydroweb.next .txt files
# ******************************************************************************

alti_rows = []
alti_u_rows = []

for alti_file in kept_files:

    with open(alti_file, "r") as f:
        content = f.readlines()

    row_data = {}
    row_u_data = {}

    # -----------------------------
    # Read header
    # -----------------------------
    i = 0
    while not content[i].startswith("###"):
        line = content[i]
        key, _, value = line.partition("::")
        key = key[1:]
        value = value.strip()
        row_data[key] = value
        row_u_data[key] = value
        i += 1

    # -----------------------------
    # Read WSE data
    # -----------------------------
    for line in content[i+1:]:
        parts = line.split()
        date = parts[0]   # this is the date of acquisition
        # time = parts[1]   # time of day (can be useful for tide correction)
        wse = np.float32(parts[2])
        wse_u = np.float32(parts[3])

        row_data[date] = wse
        row_u_data[date] = wse_u

    alti_rows.append(row_data)
    alti_u_rows.append(row_u_data)

# -----------------------------
# Build DataFrames once
# -----------------------------
alti_data = pd.DataFrame(alti_rows)
alti_u_data = pd.DataFrame(alti_u_rows)

alti_data.index = alti_data[ID_VS].astype(int)
alti_u_data.index = alti_u_data[ID_VS].astype(int)

# -----------------------------
# Split metadata vs WSE
# -----------------------------
date_mask = pd.to_datetime(alti_data.columns, errors='coerce').notna()

alti_loc_data = alti_data.loc[:, ~date_mask]
wse_data = alti_data.loc[:, date_mask]
wse_u_data = alti_u_data.loc[:, date_mask]

# -----------------------------
# Clean date columns
# -----------------------------
wse_data = wse_data.sort_index(axis=1)
wse_u_data = wse_u_data.sort_index(axis=1)

wse_data.columns = pd.to_datetime(wse_data.columns)
wse_u_data.columns = pd.to_datetime(wse_u_data.columns)

# -----------------------------
# Additional step if Hydroweb.next does not contain some virtual stations
# anymore (that were in df_ARCs)
# -----------------------------
common_IDs = df_ARCs.index.intersection(wse_data.index)
# Updating the IDs list and both datasets WSE and df_ARCs
IDs = list(common_IDs)
df_ARCs = df_ARCs.loc[common_IDs]
wse_data = wse_data.loc[common_IDs]
wse_u_data = wse_u_data.loc[common_IDs]

# -----------------------------
# Extract series
# -----------------------------
height = [wse_data.loc[ID] for ID in IDs]
height_u = [wse_u_data.loc[ID] for ID in IDs]
# That way height and height_u are built sorted like IDs, just like df_ARCs


# ******************************************************************************
# Produce discharge series and plots
# ******************************************************************************

n = 0
for ID in df_ARCs.index:
    print(ID)

    # RC and altimetry, compute discharge from RC
    Q_quant = (
        df_ARCs
        .loc[ID][[f'Q_meanMC_{i}' for i in range(0, 101)]].to_list()
    )
    Q_quant_u = (
        (df_ARCs
         .loc[ID][[f'Q_u_meanMC_{i}' for i in range(0, 101)]]/2).to_list()
    )
    WSE_quant = (
        df_ARCs
        .loc[ID][[f'WSE_meanMC_{i}' for i in range(0, 101)]].to_list()
    )
    WSE = height[n].dropna()
    WSE_u = height_u[n].dropna()
    WSE = remove_uncertain_wse(WSE, WSE_u, threshold=1)
    WSE = remove_outliers(WSE, 3)
    WSE_u = WSE_u[WSE_u.index.isin(WSE.index)]
    # Discharge computation from NPQM
    discharge_NPQM = (
        interp1d(
            WSE_quant,
            Q_quant,
            kind='linear',
            fill_value='extrapolate'
        )(WSE.to_list())
    )
    discharge_NPQM_minu = (
        interp1d(
            WSE_quant,
            [a - b for a, b in zip(Q_quant, Q_quant_u)],
            kind='linear',
            fill_value='extrapolate'
        )((WSE-WSE_u).to_list())
    )
    discharge_NPQM_maxu = (
        interp1d(
            WSE_quant,
            [a + b for a, b in zip(Q_quant, Q_quant_u)],
            kind='linear',
            fill_value='extrapolate'
        )((WSE+WSE_u).to_list())
    )
    if np.isfinite(discharge_NPQM).any():
        discharge_NPQM = replace_inf_with_min(discharge_NPQM)
        discharge_NPQM_minu = replace_inf_with_min(discharge_NPQM_minu)
        discharge_NPQM_maxu = replace_inf_with_min(discharge_NPQM_maxu)

    ##########
    # Plotting
    ##########

    fig, ax1 = plt.subplots(figsize=(12, 6))

    if np.isfinite(discharge_NPQM).any():
        x = pd.Series(index=WSE.index, data=discharge_NPQM).index
        y = pd.Series(index=WSE.index, data=discharge_NPQM)
        y1 = pd.Series(index=WSE.index, data=discharge_NPQM_minu)
        y2 = pd.Series(index=WSE.index, data=discharge_NPQM_maxu)
        try:
            ax1.plot(
                x, y, color='tab:red',
                label=(
                    'Virtual station ID ' + str(ID) + ' on '
                    + df_ARCs[basin_name_db][ID] + '_'
                    + df_ARCs[river_name_db][ID] + '_KM'
                    + str(df_ARCs[distance_name_db][ID])
                    + ": Width = " + df_ARCs[width_db][ID] + " m ("
                    + df_ARCs[satvar][ID] + ")"
                    + ' fitted on MeanDRS Q at '
                    + ID_Q + ' ' + str(df_ARCs[ID_Q][ID])
                )
            )
        except:
            try:
                ax1.plot(
                    x, y, color='tab:red',
                    label=(
                        'Virtual station ID ' + str(ID) + ' on '
                        + df_ARCs[basin_name_db][ID] + '_'
                        + df_ARCs[river_name_db][ID] + '_KM'
                        + str(df_ARCs[distance_name_db][ID])
                        + ": Width = " + str(df_ARCs[width_db][ID]) + " m ("
                        + df_ARCs[satvar][ID] + ")"
                        + ' fitted on MeanDRS Q at '
                        + ID_Q + ' ' + str(df_ARCs[ID_Q][ID])
                    )
                )
            except:
                ax1.plot(
                    x, y, color='tab:red',
                    label='Virtual station ID ' + str(ID) + ' : no info '
                )
        ax1.fill_between(x, y1.tolist(), y2.tolist(), color='salmon')

    ax1.set_ylabel('Streamflow ($m^3.s^{-1}$)', color='tab:red')
    # Add legend
    lines, labels = ax1.get_legend_handles_labels()
    ax1.legend(lines, labels, loc='upper left')
    # Ensure both axes have the same y-max scale
    if np.isfinite(discharge_NPQM).any():
        ax1.set_ylim(min(discharge_NPQM)*0.90, max(discharge_NPQM)*1.10)

    # Plot the mean MC rating curve with uncertainty as an inset plot
    if np.isfinite(discharge_NPQM).any():
        ax_inset = inset_axes(
            ax1, width="25%",
            height="35%",
            loc='upper left',
            bbox_to_anchor=(0.07, -0.1, 1., 1.),
            bbox_transform=ax1.transAxes
        )
        ax_inset.plot(
            WSE_quant[1:-1],
            Q_quant[1:-1],
            label='Mean MC rating curve'
        )
        ax_inset.fill_between(
            # X-axis values
            WSE_quant[1:-1],
            # Lower bound of the shaded area
            [a - b for a, b in zip(Q_quant[1:-1], Q_quant_u[1:-1])],
            # Upper bound of the shaded area
            [a + b for a, b in zip(Q_quant[1:-1], Q_quant_u[1:-1])],
            color='gray', alpha=0.3, label='Uncertainty interval'
        )
        ax_inset.legend()
        ax_inset.set_xlabel('WSE (m)')
        ax_inset.set_ylabel('Discharge ($m^3.s^{-1}$)')

        # ARC metrics against MeanDRS
        kge_ = df_ARCs.loc[ID]['KGE']
        corr_ = df_ARCs.loc[ID]['Corr']
        nbias_ = df_ARCs.loc[ID]['NBIAS']
        nstderr_ = df_ARCs.loc[ID]['NSTDERR']
        nrmse_ = df_ARCs.loc[ID]['NRMSE']
        prmse_ = df_ARCs.loc[ID]['PRMSE']
        rrmse_ = df_ARCs.loc[ID]['RRMSE']

        ax1.set_title(
            "On monthly seasonality: KGE: " + str(kge_)
            + " ; Corr: " + str(corr_)
            + " ; NBIAS: " + str(nbias_)
            + " ; NSTDERR: " + str(nstderr_)
            + " ; NRMSE: " + str(nrmse_)
            + " ; PRMSE: " + str(prmse_)
            + " ; RRMSE: " + str(rrmse_)
        )

    # Show the plots
    plt.tight_layout()

    # **************************************************************************
    # Export results
    # Build folder path
    output_dir = extract_folder
    # Build full file path
    fig_path = output_dir / f"{df_ARCs[station_db][ID]}_ID{ID}.png"
    # Save figure
    plt.savefig(fig_path, dpi=300, bbox_inches="tight")
    # Save time series
    series_path = output_dir / f"{df_ARCs[station_db][ID]}_ID{ID}.csv"
    pd.DataFrame(
        [y.values, y1.values, y2.values],
        columns=x.values,
        index=(
            [f"{ID}_discharge", f"{ID}_discharge_minu", f"{ID}_discharge_maxu"]
        )
    ).to_csv(series_path)
    # **************************************************************************

    n += 1
