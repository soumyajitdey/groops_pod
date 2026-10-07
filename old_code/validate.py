"""Validation of a finished POD session. Runs without redoing the POD.

  python validate.py                              # latest session in work/sessions/
  python validate.py --session 20261003-180000    # a specific session
  python validate.py --groops-bin /path/to/groops

Steps (on whichever of A, B, C finished in the session):
  1. Reproduction: A and B vs TU Graz's reference results shipped with the scenarios.
     C has no TU Graz reference.
  2. A, B, C vs the published GRACE-FO C orbit (JPL GNV1B): radial / along-track / cross-track
     differences, plots + statistics. GNV1B is converted to the GROOPS frame by GROOPS
     GraceL1b2Orbit (once per session, in <session>/GNV1B/).
     GNV1B is NOT independent of B and C (it is their a priori orbit).
  3. CHANGED: SLR residuals for A, B, C with GROOPS SlrProcessing (see slr_validation.py),
     independent of GPS. Plots + statistics. If SLR fails, steps 1-2 are still reported.

Output: <session>/validation/<YYYYmmdd-HHMMSS>/ (plots + validation_report.txt). Nothing is overwritten.
"""
import argparse
import sys
import time
from pathlib import Path

import build_groops
import compare
import config
import download
import plot_errors
import run_groops
import slr_validation                                                 # CHANGED


def validate(session, scenarios, data_dir, exe):
    """Run all validation steps on one session folder. Returns the output folder."""
    session = Path(session)
    done = [m for m in ["A", "B", "C"] if (session / m / run_groops.OK).is_file()]
    if not done:
        sys.exit(f"[validate] no finished option (A/B/C) in {session}")
    out = session / "validation" / time.strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True)
    report = [f"session {session}", f"options validated: {', '.join(done)}"]

    # 1. reproduction of TU Graz reference results (A and B only)
    for m in [x for x in ["A", "B"] if x in done]:
        sc = config.METHODS[m]["scenario"]
        frame = scenarios["reducedDynamic"] if m == "A" else None
        report += compare.compare_scenario(f"{m} vs TU Graz reference", session / m, scenarios[sc], frame)

    # 2. vs published GNV1B orbit, with plots
    if not (session / "GNV1B" / run_groops.OK).is_file():
        run_groops.run_gnv1b_reference(session, scenarios, data_dir, exe)
    report += plot_errors.plot_session(session, done, out)

    # 3. SLR residuals (independent check; SLR used for validation only)          # CHANGED
    try:
        report += slr_validation.run(session, done, out, data_dir, exe)
    except SystemExit as e:                                                      # CHANGED: SLR failure must not hide steps 1-2
        report += ["", f"=== SLR residuals: SKIPPED ({e}) ==="]

    (out / "validation_report.txt").write_text("\n".join(report) + "\n")
    print("\n".join(report))
    print(f"[validate] results: {out}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default=None, help="session folder name in work/sessions (default: latest)")
    ap.add_argument("--groops-bin", default=None)
    a = ap.parse_args()
    sessions = config.WORK / "sessions"
    if a.session:
        session = sessions / a.session
    else:
        found = sorted(p.parent.parent for p in sessions.glob(f"*/*/{run_groops.OK}") if p.parent.name in ("A", "B", "C"))
        if not found:
            sys.exit(f"[validate] no finished session in {sessions}")
        session = found[-1]
    if not session.is_dir():
        sys.exit(f"[validate] {session} not found")

    scenarios = {n: download.get_scenario(n) for n in config.SCENARIOS}   # reuses existing files
    data_dir = download.get_groops_data(list(scenarios.values()))          # reuses existing files
    exe = build_groops.get_groops(a.groops_bin)                            # reuses existing build
    validate(session, scenarios, data_dir, exe)


if __name__ == "__main__":
    main()
