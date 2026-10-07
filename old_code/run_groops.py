"""Run GROOPS scripts for options A, B, C in separate folders of one session.

TU Graz XML files are copied byte-for-byte. Settings are passed only as GROOPS global
variables (--global), which override the XML values (GROOPS config.cpp):
  groopsDataDir  path of the GROOPS data directory (all options)
  kinematicDir   folder of the option-A run whose kinematic orbit option C fits (option C only)
Nothing is deleted: every session gets a new time-stamped folder.
"""
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import config
import script_c

_DATA_REF = re.compile(r"\{groopsDataDir\}/([^<>\s]+)")
OK = "RUN_OK"   # marker written after a method finished without error


def required_data_files(script):
    """Paths below groopsDataDir referenced by the enabled programs of one XML script."""
    def walk(node):
        if node.get("disabled") == "1":
            return
        if node.text:
            yield from _DATA_REF.findall(node.text)
        for child in node:
            yield from walk(child)
    return sorted(set(walk(ET.parse(script).getroot())))


def check_data(scripts, data_dir):
    """Stop with a list of every missing groopsDataDir file before GROOPS starts."""
    data_dir = Path(data_dir)
    prn_list = data_dir / "gnss/transmitter/transmitterList.gps.txt"
    prns = prn_list.read_text().split() if prn_list.is_file() else []
    missing = []
    for s in scripts:
        for rel in required_data_files(s):
            paths = [rel.replace("{prn}", p) for p in prns] if "{prn}" in rel else [rel]
            paths = [p if "{" not in p else p[:p.index("{")].rsplit("/", 1)[0] for p in paths]  # CHANGED: {station} templates -> check folder
            missing += [f"{Path(s).name}: {p}" for p in paths if not (data_dir / p).exists()]
    if missing or not prns:
        sys.exit("[run] missing in GROOPS data directory " + str(data_dir) + ":\n  "
                 + "\n  ".join(missing or ["gnss/transmitter/transmitterList.gps.txt"]))


def _prepare(run_dir, scenario_dir, scripts):
    """New run folder with the scripts + inputs from the pristine scenario (no data/ or output/)."""
    if run_dir.exists():
        sys.exit(f"[run] {run_dir} exists; refusing to overwrite")
    run_dir.mkdir(parents=True)
    for item in scripts + config.SCENARIO_INPUTS:
        _copy(Path(scenario_dir) / item, run_dir / item)              # CHANGED: content-only copy


def _copy(src, dst):
    """CHANGED: copy file contents only (byte-identical). shutil.copy2/copytree also copy timestamps,
    which Windows drives under /mnt/* (WSL) can refuse with 'Operation not permitted'."""
    if src.is_dir():
        for f in sorted(src.rglob("*")):
            out = dst / f.relative_to(src)
            if f.is_dir():
                out.mkdir(parents=True, exist_ok=True)
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, out)
    else:
        shutil.copyfile(src, dst)


def _run_scripts(run_dir, scripts, data_dir, groops_exe, extra_globals=None):
    paths = [run_dir / s for s in scripts]
    check_data(paths, data_dir)
    log_dir = run_dir / "log"
    log_dir.mkdir(exist_ok=True)
    glob = {"groopsDataDir": str(Path(data_dir).resolve()), **(extra_globals or {})}
    for s in paths:
        print(f"[run] {run_dir.name}: {s.name}")
        cmd = [groops_exe, "--log", str(log_dir / (s.stem + ".log"))]
        for k, v in glob.items():
            cmd += ["--global", f"{k}={v}"]
        if subprocess.run(cmd + [s.name], cwd=run_dir).returncode != 0:
            sys.exit(f"[run] GROOPS failed on {s.name}; see {log_dir / (s.stem + '.log')}")


def run_method(method, session_dir, scenarios, data_dir, groops_exe, kinematic_dir=None):
    """Run option A, B or C into session_dir/<method>. Returns the run folder."""
    m = config.METHODS[method]
    run_dir = Path(session_dir) / method
    _prepare(run_dir, scenarios[m["scenario"]], m["scripts"])
    scripts, extra = list(m["scripts"]), {}
    if "generated" in m:                                      # option C
        if not kinematic_dir or not (Path(kinematic_dir) / OK).is_file():
            sys.exit("[run] option C needs a finished option-A run")
        script_c.make_script_c(Path(scenarios["reducedDynamic"]) / "03groopsVariational.xml",
                               run_dir / m["generated"])
        scripts.append(m["generated"])
        extra["kinematicDir"] = str(Path(kinematic_dir).resolve())
        (run_dir / "kinematic_input.txt").write_text(f"option C fitted to kinematic orbit of: {kinematic_dir}\n")
    _run_scripts(run_dir, scripts, data_dir, groops_exe, extra)
    (run_dir / OK).write_text(m["label"] + "\n")
    return run_dir


def run_gnv1b_reference(session_dir, scenarios, data_dir, groops_exe):
    """Convert the published GNV1B orbit to the GROOPS frame/time scale (session_dir/GNV1B/output)."""
    run_dir = Path(session_dir) / "GNV1B"
    _prepare(run_dir, scenarios["kinematic"], [])
    script_c.make_script_gnv1b(Path(scenarios["kinematic"]) / "02groopsConvertGracefo.xml",
                               run_dir / "gnv1bReference.xml")
    _run_scripts(run_dir, ["gnv1bReference.xml"], data_dir, groops_exe)
    (run_dir / OK).write_text("GNV1B in GROOPS frame\n")
    return run_dir


def latest_ok_run(method):
    """Most recent finished run of a method from earlier sessions, or None."""
    runs = sorted((config.WORK / "sessions").glob(f"*/{method}/{OK}"))
    return runs[-1].parent if runs else None
