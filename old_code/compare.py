"""Compare our GROOPS results with TU Graz's reference results shipped in each scenario's output/.

Reported per day:
- epoch counts (ours, reference, common)
- orbit difference ours - reference: mean and RMS in radial/along-track/cross-track, 3D RMS, 3D max
- kinematic only: median formal 3D sigma, ours and reference
- receiver signal biases: difference per signal type
No pass/fail threshold is applied (none is published for this comparison).
"""
from pathlib import Path

import numpy as np

import config
from groops_io import read_covariance3d, read_orbit, read_signal_bias


def _match(t1, t2):
    """Indices of common epochs (rounded to 1 ms)."""
    k1 = np.round(t1 * 86400e3).astype(np.int64)
    k2 = np.round(t2 * 86400e3).astype(np.int64)
    _, i1, i2 = np.intersect1d(k1, k2, return_indices=True)
    return i1, i2


def _rtn(dpos, pos, vel):
    """Rotate position differences into radial / along-track (T) / cross-track (N)."""
    r = pos / np.linalg.norm(pos, axis=1)[:, None]
    n = np.cross(pos, vel)
    n /= np.linalg.norm(n, axis=1)[:, None]
    t = np.cross(n, r)
    return np.c_[(dpos * r).sum(1), (dpos * t).sum(1), (dpos * n).sum(1)]


def compare_day(name, run_dir, ref_dir, day, frame_orbit=None):
    """frame_orbit: optional reference orbit file with velocities, used for the RTN frame of a kinematic orbit."""
    sat = config.SATELLITE
    lines = [f"--- {name} {day}"]
    f = f"{day}/{sat}_orbit_{day}.txt"
    t, p, _ = read_orbit(Path(run_dir) / "output" / f)
    tr, pr, vr = read_orbit(Path(ref_dir) / "output" / f)
    i, j = _match(t, tr)
    lines.append(f"epochs ours/ref/common: {len(t)} / {len(tr)} / {len(i)}")
    d = p[i] - pr[j]
    if not np.any(vr):                                  # kinematic reference: velocity columns are zero
        vr = None
        if frame_orbit and Path(frame_orbit).is_file():
            tf, pf, vf = read_orbit(frame_orbit)
            k, m = _match(tr[j], tf)
            i, j, d = i[k], j[k], d[k]
            vr_sel, pr_sel = vf[m], pr[j]
        else:
            pr_sel = None
    else:
        vr_sel, pr_sel = vr[j], pr[j]
    if pr_sel is not None:
        rtn = _rtn(d, pr_sel, vr_sel) * 1000
        lines.append("R/T/N mean [mm]: " + " / ".join(f"{x:.2f}" for x in rtn.mean(0)))
        lines.append("R/T/N RMS  [mm]: " + " / ".join(f"{x:.2f}" for x in np.sqrt((rtn**2).mean(0))))
    d3 = np.linalg.norm(d, axis=1) * 1000
    lines.append(f"3D RMS / max [mm]: {np.sqrt((d3**2).mean()):.2f} / {d3.max():.2f}")

    cov = Path(run_dir) / "output" / f"{day}/{sat}_covarianceEpoch3x3_{day}.txt"
    cov_ref = Path(ref_dir) / "output" / f"{day}/{sat}_covarianceEpoch3x3_{day}.txt"
    if cov.is_file() and cov_ref.is_file():
        s = [np.median(np.sqrt(np.trace(read_covariance3d(c)[1], axis1=1, axis2=2))) * 1000 for c in (cov, cov_ref)]
        lines.append(f"median formal 3D sigma ours/ref [mm]: {s[0]:.2f} / {s[1]:.2f}")

    for b in sorted((Path(ref_dir) / "output" / day).glob(f"signalBias_{day}.*.txt")):
        ours = Path(run_dir) / "output" / day / b.name
        if ours.is_file():
            bo, br = read_signal_bias(ours), read_signal_bias(b)
            lines.append(f"signal bias {b.name.split('.')[-2]} ours-ref [mm]: " + ", ".join(
                f"{k} {1000*(bo[k]-br[k]):+.2f}" for k in br if k in bo))
    return lines


def compare_scenario(name, run_dir, ref_dir, frame_ref_dir=None):
    lines = []
    for day in config.DAYS:
        frame = None
        if frame_ref_dir:
            frame = Path(frame_ref_dir) / "output" / day / f"{config.SATELLITE}_orbit_{day}.txt"
        lines += compare_day(name, run_dir, ref_dir, day, frame)
    return lines
