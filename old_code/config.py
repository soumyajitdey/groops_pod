"""Fixed settings for the GRACE-FO GROOPS pipeline.

Everything mission-specific lives here so the CHAMP step later only edits this file
(plus metadata), never the TU Graz XML scripts.
"""
from pathlib import Path

# GROOPS release. Pinned because master (after 2025-11-15) renamed a config element
# used by 01groopsConvert.xml (GnssSinexBias2SignalBias/inputfileGlonassSignalDefinition).
GROOPS_GIT = "https://github.com/groops-devs/groops.git"
GROOPS_TAG = "2025-11-15"

# TU Graz server. First URL is the one in the GROOPS README/INSTALL; second is a mirror path.
TUG_BASES = [
    "https://ftp.tugraz.at/outgoing/ITSG/groops",
    "https://ftp.tugraz.at/pub/ITSG/groops",
]
DATA_ZIP = "data.zip"  # general GROOPS data: EOP, gravity, tides, JB2008/HWM14, CERES, satellite models, LEO metadata

# TU Graz example scenarios (GRACE-FO C, 2020-01-01/02). Each zip holds the XML scripts,
# GRACE-FO L1B input, TUG repro3 GPS products and TU Graz reference results in output/.
SCENARIOS = {
    "kinematic": {"zip": "scenario/scenarioLeoKinematicOrbit.zip", "dir": "scenarioLeoKinematicOrbit"},
    "reducedDynamic": {"zip": "scenario/scenarioLeoReducedDynamicOrbit.zip", "dir": "scenarioLeoReducedDynamicOrbit"},
}
# Input files/folders each run needs next to its scripts (copied from the scenario).
SCENARIO_INPUTS = ["02observationTypes.txt", "gracefo", "igs"]

# CHANGED: three processing options. Each runs in its own folder of a session (never overwritten).
METHODS = {
    "A": {"label": "kinematic",                          # TU Graz kinematic scenario, unchanged
          "scenario": "kinematic",
          "scripts": ["01groopsConvert.xml", "02groopsConvertGracefo.xml", "03groopsGnssProcessing.xml"]},
    "B": {"label": "reduced-dynamic, fitted to GPS",     # TU Graz reduced-dynamic scenario, unchanged
          "scenario": "reducedDynamic",
          "scripts": ["01groopsConvert.xml", "02groopsConvertGracefo.xml",
                      "03groopsVariational.xml", "04groopsGnssProcessing.xml"]},
    "C": {"label": "reduced-dynamic, fitted to kinematic",  # TU Graz scripts 01, 02 + generated 03 (see script_c.py)
          "scenario": "reducedDynamic",
          "scripts": ["01groopsConvert.xml", "02groopsConvertGracefo.xml"],
          "generated": "03groopsKinematicOrbitFit.xml",
          "needs": "A"},
}

DAYS = ["2020-01-01", "2020-01-02"]   # fixed by the scenario scripts (timeStart=58849, timeEnd=timeStart+2)
SATELLITE = "gracefo1"                 # output file prefix used by the scripts
GNV1B = "gracefo/GNV1B_{day}_C_04.txt"  # CHANGED: published GRACE-FO C orbit (JPL), used for the error plots

WORK = Path(__file__).resolve().parent / "work"

# CHANGED: SLR validation (validate.py). SLR is used ONLY to validate orbits, never in the POD.
SLR_SATELLITE = "gracefo1"                       # ILRS/EDC name of GRACE-FO C
SLR_NPT_URL = "https://edc.dgfi.tum.de/pub/slr/data/npt_crd/{sat}/{year}/{sat}_{ymd}.npt"   # EUROLAS Data Center (DGFI-TUM), CRD normal points
L1B_URL = "https://isdc-data.gfz.de/grace-fo/Level-1B/JPL/INSTRUMENT/RL04/{year}/gracefo_1B_{day}_RL04.ascii.noLRI.tgz"  # GFZ ISDC, JPL L1B RL04
L1B_SAT_LETTER = "C"                             # GRACE-FO C = gracefo1
# LRR position in the satellite frame [m]. None = read from JPL VSL1B (GRACE-FO L1 handbook, Sect. 2.5.6).
LRR_POSITION = None
LRR_RANGE_CORRECTION = 0.0                       # [m] NOT SOURCED yet (see README open issues)
# GROOPS data files used by the SLR step (not referenced by the TU Graz scenario scripts).
# Defaults of the GROOPS classes (tidesPole.cpp, tidesOceanPole.cpp, slrStationGeneratorStations.cpp).
EXTRA_DATA = ["slr/stations", "tides/secularPole2018.xml", "tides/oceanPoleTide_desai2004.dat",
              "loading/deformationLoveNumbers_CM_Gegout97.txt", "loading/loadLoveNumbers_Gegout97.txt"]
