"""One-command runner for any mission folder (GRACE-FO/, CHAMP/, ...).

  python3 run_pipeline.py --mission CHAMP --method all                    # A, B, C + validation
  python3 run_pipeline.py --mission CHAMP --method A --products ultra
  python3 run_pipeline.py --mission GRACE-FO --method B
  options: --products repro3|final|ultra (default repro3), --groops-bin /path/to/groops

Methods: A kinematic | B reduced-dynamic fitted to GPS | C reduced-dynamic fitted to A's kinematic orbit.
Each call creates work/results/<MISSION>_<YYYYmmdd>_<HHMMSS>/ with A/, B/, C/, report.txt and
validation/<time>/. Nothing is overwritten. Validation alone: python3 validate.py --mission <MISSION>.
A new mission = a new folder with mission.py; nothing else changes.
"""
import argparse
import importlib.util
import sys
import time
from pathlib import Path

from core import build_groops, download, run_groops, settings

ROOT = Path(__file__).resolve().parent


def missions():
    return sorted(p.parent.name for p in ROOT.glob("*/mission.py"))


def load_mission(name):
    folder = ROOT / name
    if not (folder / "mission.py").is_file():
        sys.exit(f"unknown mission {name}; available: {', '.join(missions())}")
    sys.path.insert(0, str(folder))                     # mission-local helper modules
    spec = importlib.util.spec_from_file_location(f"mission_{name.replace('-', '_')}", folder / "mission.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def latest_ok_run(mission, method, products):
    """Most recent finished run of a method (same mission and products) in earlier results."""
    runs = sorted(settings.RESULTS.glob(f"{mission.NAME}_*/{method}/{run_groops.OK}"))
    runs = [r for r in runs if f"products={products}" in r.read_text()]
    return runs[-1].parent if runs else None


def run_method(mission, method, results, ctx, data_dir, exe, kinematic_dir=None):
    files, scripts, globals_ = mission.run_files(method, ctx)
    if method == "C":
        if not kinematic_dir or not (Path(kinematic_dir) / run_groops.OK).is_file():
            sys.exit("[run] option C needs a finished option-A run")
        globals_["kinematicDir"] = str(Path(kinematic_dir).resolve())
        files["kinematic_input.txt"] = f"option C fitted to kinematic orbit of: {kinematic_dir}\n"
    run_dir = run_groops.prepare(results / method, files)
    run_groops.run_scripts(run_dir, scripts, data_dir, exe, globals_)
    (run_dir / run_groops.OK).write_text(f"{settings.METHODS[method]}\nproducts={ctx['products']}\n")
    return run_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mission", required=True, choices=missions())
    ap.add_argument("--method", choices=["A", "B", "C", "all"], required=True)
    ap.add_argument("--products", choices=["repro3", "final", "ultra"], default="repro3")
    ap.add_argument("--groops-bin", default=None)
    a = ap.parse_args()
    mission = load_mission(a.mission)
    methods = ["A", "B", "C"] if a.method == "all" else [a.method]

    ctx = mission.setup(a.products)
    data_dir = download.get_groops_data(ctx["template_dirs"], ctx["extra_data"])
    exe = build_groops.get_groops(a.groops_bin)

    results = settings.RESULTS / f"{mission.NAME}_{time.strftime('%Y%m%d_%H%M%S')}"
    results.mkdir(parents=True)
    report = [f"mission {mission.NAME}, days {mission.DAYS[0]} .. {mission.DAYS[-1]}, products {a.products}",
              f"GROOPS {settings.GROOPS_TAG}, data {data_dir}", f"results {results}"]

    kin_dir = None
    for m in methods:
        if m == "C" and kin_dir is None:                    # C needs a finished A run
            kin_dir = latest_ok_run(mission, "A", a.products)
            if kin_dir is None:
                print("[run] no finished option-A run found; running A first")
                kin_dir = run_method(mission, "A", results, ctx, data_dir, exe)
            report.append(f"option C uses kinematic orbit from {kin_dir}")
        run_dir = run_method(mission, m, results, ctx, data_dir, exe, kinematic_dir=kin_dir)
        if m == "A":
            kin_dir = run_dir

    (results / "report.txt").write_text("\n".join(report) + "\n")
    print("\n".join(report))
    print(f"[done] POD finished: {results}")
    import validate
    validate.validate(mission, results, ctx, data_dir, exe)


if __name__ == "__main__":
    main()
