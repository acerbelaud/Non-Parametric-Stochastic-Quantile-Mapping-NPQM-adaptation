# Discharge_altimetry_NPQM_ratingcurve
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19006996.svg)](https://doi.org/10.5281/zenodo.19006996)

[![License (3-Clause BSD)](https://img.shields.io/badge/license-BSD%203--Clause-yellow.svg)](https://github.com/acerbelaud/Discharge_altimetry_NPQM_ratingcurve/blob/main/LICENSE)

Discharge_altimetry_NPQM_ratingcurve is a collection of Python scripts and iPython notebooks that transforms global observations of river water surface elevation (WSE) provided by nadir altimetry satellite missions (and obtained via the Hydroweb.next platform; https://hydroweb.next.theia-land.fr/) into estimates of river discharge worldwide. For this, we derive non parametric stochastic quantile mapping (NPQM) altimetric rating curves (ARCs) using the Mean Discharge and River Storage dataset (MeanDRS, Collins et al., 2024, https://doi.org/10.1038/s41561-024-01421-5) as reference long-term gauge-corrected monthly discharge (Qref). The NPQM code is heavily adapted from a previously published matlab version: Elmi et al, 2023, https://doi.org/10.18419/DARUS-3558.

The rated discharge (Qrated) obtained in the process at a given virtual station/MERIT reach pair thus reflects real observed water levels obtained from altimetry but also mirrors gauge-corrected simulated monthly discharge values.

Discharge_altimetry_NPQM_ratingcurve aims to:

1. Download and prepare nadir altimetry WSE data from Hydroweb.next.
2. Calibrate ARCs leveraging the translation between the location of virtual stations (where WSE is) and of the MERIT-Basin river reaches (where Qref is).
3. Compute river discharge (Qrated) by applying the calibrated ARCs to WSE observations downloaded from a Hydroweb.next API call.

Regions of the world that were not gauge-corrected in MeanDRS (e.g., Nile, Yangtze) were NOT processed here, even though altimetry virtual stations are available there. Please refer to Collins et al. (2024) for the exact watersheds that were bias-corrected and therefore where ARCs were calibrated. WSE data is quality filtered using the Hydroweb.next WSE uncertainty and outlier detection techniques. Please refer to Cerbelaud et al. (TBD) for a full description of the materials and methods, filters, and validation of the dataset.

## Python Script Documentation 
The Python scripts in the `/src/` folder represent individual computational steps used to obtain altimetric rating curves and produce river discharge estimates from nadir altimetry WSE observations and reference discharge.

**`ARC_preprocess_Hydroweb.ipynb`**

  * Inputs:  
    * Folder containing WSE from individual virtual stations `.txt` downloaded from Hydroweb.next

  * Outputs:  
    * Global clean dataset containing the header information and WSE time series of all the virtual stations in the folder (`.csv`)  

This notebook allows pre-processing the raw `.txt` files downloaded from Hydroweb.next to create one large, global, clean dataset, ready for training ARCs using `ARC_fitting_NPQM.ipynb`.

&nbsp;

**`ARC_fitting_NPQM.ipynb`**  

  * Inputs:  
    * Global clean dataset containing the header information and WSE time series of all the virtual stations in the folder (`.csv`)
      This dataset needs to be complemented with a snapping of the virtual station location to the river network used for the underlying reference discharge (e.g. a 0.005 degree buffer nearest-neighbor snapping). See the corresponding Zenodo repo for snapping information on MERIT Basins (https://doi.org/10.5281/zenodo.19006996).
    * Reference discharge files used for rating curve calibration (`.nc`). Here we use MeanDRS.

  * Outputs:  
    * Global input dataset with the addition of the ARCs (mean Monte Carlo quantile mapping function, with uncertainty), and their performance metrics (`.csv`)  

This notebook allows training the ARCs using the pre-processed WSE data and a reference discharge product.

&nbsp;

**`Q_prod_from_ARC.py`**

  * Inputs:  
    None needed

  * Outputs:  
    * WSE data downloaded from Hydroweb.next (`.txt`)
    * calculated discharge time series with uncertainty (`.csv`) from the ARCs
    * plot of calculated discharge time series with uncertainty, and corresponding ARC with its performance metrics (`.png`)

Please follow these steps to run this code that produces discharge from the calibrated ARCs and up-to-date WSE data:

1. Clone the repo and check the Python package requirements.
2. Add to your .env variables a HYDROWEBNEXT_API_KEY obtained from creating a free account on Hydroweb.next.
3. To produce discharge at several virtual stations, or for all virtual stations on a given river, run in terminal: python Q_prod_from_ARC.py arg1 arg2 arg3 arg4 arg5
arg1 is the folder where the discharge estimates will be produced. E.G. "your_folder/AMAZONAS_data/".
arg2 is either (i) the identifier(s) of the virtual station(s) in Hydroweb.next (IDs can be obtained by browsing the Choose_river_ARC_hydroweb_ope_MeanDRS.xlsx dictionary from the corresponding Zenodo repo), E.G. 138,139,140 ; or (ii) the river name, E.G. "AMAZONAS".
arg3 is the KGE min threshold for the performance of the ARC at the virtual station. E.G. 0.0.
arg4 and arg5 are the start and end dates. E.G. "2000-01-01" and "2026-03-01".

If not found, the code 'Q_prod_from_ARC.py' will automatically download the rating curve dataset "ARC_NPQM_hydroweb_ope_MeanDRS_flags.pkl" from the Zenodo repository (https://doi.org/10.5281/zenodo.19006998), which will be stored in the parent folder of the code repository. Keep it there for future use.

The code allows computing discharge directly from WSE data at 20,000+ MERIT-Basins river reaches, corresponding to 20,000+ ongoing virtual stations reported in Hydroweb.next. Validation metrics against GRDC (grdc.bafg.de/) in situ gauges will be provided at approximately 1400 virtual stations (Cerbelaud et al.; TBD).

&nbsp;

**`API_hydrowebnext.py`**

This code is called by `Q_prod_from_ARC.py` to download data from Hydroweb.next API service.

### Install Python packages
Python packages from the Python Package Index (PyPI) are summarized in [requirements.pip](https://github.com/acerbelaud/Discharge_altimetry_NPQM_ratingcurve/blob/main/requirements.pip) and can be installed with `pip`. First, make sure that the latest version of `pip` is installed.