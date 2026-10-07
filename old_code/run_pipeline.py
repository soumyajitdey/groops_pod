"""One-command runner. Choose the processing option:

  A  kinematic                               (TU Graz kinematic scenario, unchanged)
  B  reduced-dynamic fitted to GPS            (TU Graz reduced-dynamic scenario, unchanged)
  C  reduced-dynamic fitted to kinematic      (TU Graz scripts + one generated script; uses A's output)

Usage:
  python run_pipeline.py --method A            # or B, C
  python run_pipeline.py --method all          # validation run: A, B, C in separate folders
  python run_pipeline.py --groops-bin /path/to/groops   # use an existing GROOPS build

Each call creates work/sessions/<YYYYmmdd-HHMMSS>/ with one folder per option (A/, B/, C/) and
report.txt, then runs validate.py on it (GNV1B/, validation/<time>/). Nothing is overwritten.
Validation alone, on an existing session: python validate.py   # CHANGED
"""
import argparse
import time

import build_groops
import config
import download
import run_groops
import validate                                                       # CHANGED


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", choices=["A", "B", "C", "all"], required=True)
    ap.add_argument("--groops-bin", default=None)
    a = ap.parse_args()
    methods = ["A", "B", "C"] if a.method == "all" else [a.method]

    scenarios = {n: download.get_scenario(n) for n in config.SCENARIOS}
    data_dir = download.get_groops_data(list(scenarios.values()))  # CHANGED: extracts only needed files
    exe = build_groops.get_groops(a.groops_bin)

    session = config.WORK / "sessions" / time.strftime("%Y%m%d-%H%M%S")
    session.mkdir(parents=True)
    report = [f"GROOPS {config.GROOPS_TAG}, data {data_dir}", f"session {session}"]

    kin_dir = None
    for m in methods:
        if m == "C" and kin_dir is None:                      # C needs a finished A run
            kin_dir = run_groops.latest_ok_run("A")
            if kin_dir is None:
                print("[run] no finished option-A run found; running A first")
                kin_dir = run_groops.run_method("A", session, scenarios, data_dir, exe)
            report.append(f"option C uses kinematic orbit from {kin_dir}")
        run_dir = run_groops.run_method(m, session, scenarios, data_dir, exe, kinematic_dir=kin_dir)
        if m == "A":
            kin_dir = run_dir

    (session / "report.txt").write_text("\n".join(report) + "\n")    # CHANGED: POD info only
    print("\n".join(report))
    print(f"[done] POD finished: {session}")
    validate.validate(session, scenarios, data_dir, exe)              # CHANGED: validation moved to validate.py


if __name__ == "__main__":
    main()
