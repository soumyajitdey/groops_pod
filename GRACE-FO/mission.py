"""GRACE-FO (GRACE-FO C, 2020-01-01/02): TU Graz example scenarios, run unchanged.

A: scenarioLeoKinematicOrbit scripts 01-03      B: scenarioLeoReducedDynamicOrbit scripts 01-04
C: scenarioLeoReducedDynamicOrbit 01, 02 + option-C script generated from its 03 (core/script_c.py)
Inputs (GRACE-FO L1B, TUG repro3 products) come with the scenario zips.

Validation: (1) A, B vs TU Graz's reference results in the scenarios' output/ folders,
(2) A, B, C vs JPL GNV1B (not independent of B, C: it is their a priori orbit), (3) SLR residuals.
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from core import compare, download, plot_errors, run_groops, script_c

NAME = "GRACE-FO"
SATELLITE = "gracefo1"                       # file prefix used by the scripts
DAYS = ["2020-01-01", "2020-01-02"]          # fixed by the scenario scripts (timeStart=58849, timeEnd=timeStart+2)
PRODUCTS = ["repro3"]                        # products shipped with the scenarios
SCENARIO_INPUTS = ["02observationTypes.txt", "gracefo", "igs"]
# GROOPS data used by the SLR step (not referenced by the scenario scripts); optional.
EXTRA_DATA = ["slr/stations", "tides/secularPole2018.xml", "tides/oceanPoleTide_desai2004.dat",
              "loading/deformationLoveNumbers_CM_Gegout97.txt", "loading/loadLoveNumbers_Gegout97.txt"]
SCRIPTS = {
    "A": ("kinematic", ["01groopsConvert.xml", "02groopsConvertGracefo.xml", "03groopsGnssProcessing.xml"]),
    "B": ("reducedDynamic", ["01groopsConvert.xml", "02groopsConvertGracefo.xml",
                             "03groopsVariational.xml", "04groopsGnssProcessing.xml"]),
    "C": ("reducedDynamic", ["01groopsConvert.xml", "02groopsConvertGracefo.xml"]),
}


def setup(products):
    if products not in PRODUCTS:
        sys.exit(f"[{NAME}] --products {products} not available (scenario ships repro3 products only)")
    sc = {n: download.get_scenario(n) for n in ("kinematic", "reducedDynamic")}
    return {"scenarios": sc, "template_dirs": list(sc.values()), "extra_data": EXTRA_DATA, "globals": {},
            "products": products}


def run_files(method, ctx):
    """Files for a run folder, the script order and extra GROOPS globals."""
    scen, scripts = SCRIPTS[method]
    src = ctx["scenarios"][scen]
    files = {s: src / s for s in scripts}
    files.update({i: src / i for i in SCENARIO_INPUTS})
    scripts = list(scripts)
    if method == "C":
        name = "03groopsKinematicOrbitFit.xml"
        files[name] = script_c.make_script_c((src / "03groopsVariational.xml").read_text(), SATELLITE)
        scripts.append(name)
    return files, scripts, dict(ctx["globals"])


# ---------------- validation ----------------

def _gnv1b_script(convert_xml):
    """Only GraceL1b2Orbit of TU Graz script 02, writing GNV1B (same frame/time as our orbits) to output/."""
    root = ET.parse(convert_xml).getroot()
    loop = root.find("program/LoopPrograms")
    for p in loop.findall("program"):
        if p.find("GraceL1b2Orbit") is None and p.find("FileCreateDirectories") is None:
            loop.remove(p)
    for p in loop.findall("program"):
        if p.find("FileCreateDirectories") is not None:
            p.find("FileCreateDirectories/directory").text = "output/{loopTime:%D}"
        else:
            p.find("GraceL1b2Orbit/outputfileOrbit").text = "output/{loopTime:%D}/gracefo1_gnv1b_{loopTime:%D}.txt"
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


def validate(results, done, out, ctx, data_dir, exe):
    sc = ctx["scenarios"]
    lines = []
    # 1. reproduction of TU Graz reference results (A and B only)
    for m, scen, frame in (("A", "kinematic", sc["reducedDynamic"]), ("B", "reducedDynamic", None)):
        if m in done:
            lines += compare.compare_scenario(f"{m} vs TU Graz reference", results / m, sc[scen], DAYS, SATELLITE, frame)
    # 2. vs published GNV1B orbit (converted once per results folder)
    done_dirs = sorted(results.glob(f"GNV1B*/{run_groops.OK}"))
    gdir = done_dirs[-1].parent if done_dirs else results / "GNV1B"
    if not done_dirs:
        if gdir.exists():                           # earlier conversion failed: new folder, old one kept
            import time
            gdir = results / f"GNV1B_{time.strftime('%Y%m%d_%H%M%S')}"
        files = {"gnv1bReference.xml": _gnv1b_script(sc["kinematic"] / "02groopsConvertGracefo.xml"),
                 "gracefo": sc["kinematic"] / "gracefo"}
        run_groops.prepare(gdir, files)
        run_groops.run_scripts(gdir, ["gnv1bReference.xml"], data_dir, exe)
        (gdir / run_groops.OK).write_text("GNV1B in GROOPS frame\n")
    from core.groops_io import read_orbit
    loader = lambda day: read_orbit(gdir / "output" / day / f"gracefo1_gnv1b_{day}.txt")
    lines += plot_errors.plot_vs_reference(results, done, SATELLITE, DAYS, "GNV1B (JPL, a priori of B and C)",
                                           loader, out, "GRACE-FO C")
    # 3. SLR residuals (independent; validation only)
    import slr_validation
    try:
        lines += slr_validation.run(results, done, out, data_dir, exe)
    except SystemExit as e:
        lines += ["", f"=== SLR residuals: SKIPPED ({e}) ==="]
    return lines
