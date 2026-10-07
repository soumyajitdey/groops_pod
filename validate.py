"""Validation of a finished run (any mission). Runs without redoing the POD.

  python3 validate.py --mission CHAMP                               # latest CHAMP results
  python3 validate.py --mission CHAMP --results CHAMP_20261003_210000
  option: --groops-bin /path/to/groops

The checks are defined by the mission (<MISSION>/mission.py, function validate):
  GRACE-FO: A, B vs TU Graz scenario references; A, B, C vs JPL GNV1B; SLR residuals.
  CHAMP:    A, B, C vs GFZ RSO; vs TU Graz published CHAMP kinematic and reduced-dynamic orbits.
Output: <results>/validation/<YYYYmmdd_HHMMSS>/ (plots + validation_report.txt). Nothing is overwritten.
"""
import argparse
import sys
import time
from pathlib import Path

from core import build_groops, download, run_groops, settings


def validate(mission, results, ctx, data_dir, exe):
    results = Path(results)
    done = [m for m in ["A", "B", "C"] if (results / m / run_groops.OK).is_file()]
    if not done:
        sys.exit(f"[validate] no finished option (A/B/C) in {results}")
    out = results / "validation" / time.strftime("%Y%m%d_%H%M%S")
    out.mkdir(parents=True)
    report = [f"results {results}", f"mission {mission.NAME}, options validated: {', '.join(done)}"]
    report += mission.validate(results, done, out, ctx, data_dir, exe)
    (out / "validation_report.txt").write_text("\n".join(report) + "\n")
    print("\n".join(report))
    print(f"[validate] results: {out}")
    return out


def main():
    from run_pipeline import load_mission, missions
    ap = argparse.ArgumentParser()
    ap.add_argument("--mission", required=True, choices=missions())
    ap.add_argument("--results", default=None, help="folder name in work/results (default: latest of the mission)")
    ap.add_argument("--groops-bin", default=None)
    a = ap.parse_args()
    mission = load_mission(a.mission)
    if a.results:
        results = settings.RESULTS / a.results
    else:
        found = sorted({p.parent.parent for p in settings.RESULTS.glob(f"{mission.NAME}_*/*/{run_groops.OK}")
                        if p.parent.name in ("A", "B", "C")})
        if not found:
            sys.exit(f"[validate] no finished {mission.NAME} results in {settings.RESULTS}")
        results = found[-1]
    if not results.is_dir():
        sys.exit(f"[validate] {results} not found")
    products = "repro3"
    for m in ("A", "B", "C"):
        ok = results / m / run_groops.OK
        if ok.is_file() and "products=" in ok.read_text():
            products = ok.read_text().split("products=")[1].split()[0]
    ctx = mission.setup(products)                                          # reuses existing files
    data_dir = download.get_groops_data(ctx["template_dirs"], ctx["extra_data"])
    exe = build_groops.get_groops(a.groops_bin)
    validate(mission, results, ctx, data_dir, exe)


if __name__ == "__main__":
    main()
