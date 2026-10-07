"""Mission-independent settings (GROOPS, TU Graz data, work folder).

Mission-specific settings live in <MISSION>/mission.py. Adding a mission never edits this file.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"                      # downloads, GROOPS data, results (shared by all missions)
RESULTS = WORK / "results"                # one folder per run: <MISSION>_<YYYYmmdd>_<HHMMSS>

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

# TU Graz example scenarios (GRACE-FO C, 2020-01-01/02): XML scripts used as templates by all missions.
SCENARIOS = {
    "kinematic": {"zip": "scenario/scenarioLeoKinematicOrbit.zip", "dir": "scenarioLeoKinematicOrbit"},
    "reducedDynamic": {"zip": "scenario/scenarioLeoReducedDynamicOrbit.zip", "dir": "scenarioLeoReducedDynamicOrbit"},
}

# Processing options (same for every mission)
METHODS = {
    "A": "kinematic",
    "B": "reduced-dynamic, fitted to GPS",
    "C": "reduced-dynamic, fitted to kinematic",
}
