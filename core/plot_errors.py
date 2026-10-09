"""Orbit error plots vs a reference orbit (mission-independent).

Differences ours - reference are rotated into radial (R), along-track (T), cross-track (N) using the
reference position and velocity. If the reference has no velocity (kinematic orbit), the velocity
for the frame is taken from numerical differentiation of the reference positions (only orients the
frame; a few cm of position noise over 10 s changes the axes by ~1e-6 rad).
One PNG per reference over the whole date range (CHANGED); statistics per day are returned for the report.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from core.compare import _match, _rtn
from core.groops_io import read_orbit
from core.settings import METHODS

# Categorical slots 1-3 of the reference palette (validated: CVD and normal-vision separation pass).
COLORS = {"A": "#2a78d6", "B": "#eb6834", "C": "#1baf7a"}
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e6e5e0"


def _frame_velocity(t, p, v):
    if v is not None and np.any(v):
        return v
    return np.gradient(p, t * 86400.0, axis=0)


def errors_vs_reference(run_dir, sat, day, ref, own=None):                         # CHANGED: own
    """Hours since midnight and R/T/N differences [cm] of one run vs a reference (t, pos, vel|None).
    own: (t, pos, vel) of our orbit for that day; default: <run_dir>/output/<day>/<sat>_orbit_<day>.txt."""
    t, p, _ = own if own is not None else read_orbit(Path(run_dir) / "output" / day / f"{sat}_orbit_{day}.txt")  # CHANGED
    tr, pr, vr = ref
    vr = _frame_velocity(tr, pr, vr)
    i, j = _match(t, tr)
    rtn = _rtn(p[i] - pr[j], pr[j], vr[j]) * 100
    return (t[i] - np.floor(t[0])) * 24, rtn


def plot_vs_reference(results_dir, methods, sat, days, ref_name, ref_loader, out_dir, title_sat,
                      own_loader=None):                                                 # CHANGED
    """ref_loader(day) -> (t [MJD], pos [m], vel [m/s] or None) or None if unavailable that day.
    own_loader(method, day) -> our orbit (t, pos, vel) of that day (default: daily output files)."""
    results_dir, out_dir = Path(results_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = ref_name.split()[0].replace("/", "-")
    lines = ["", f"=== orbit minus {ref_name} (cm) ===",
             f"{'day':10} {'opt':3} {'epochs':>6} {'R mean':>7} {'T mean':>7} {'N mean':>7} "
             f"{'R RMS':>7} {'T RMS':>7} {'N RMS':>7} {'3D RMS':>7}"]
    full = {}                                                           # CHANGED: whole date range per option
    for i, day in enumerate(days):                                      # CHANGED
        ref = ref_loader(day)
        if ref is None:
            lines.append(f"{day:10} reference not available")
            continue
        for m in methods:
            h, e = errors_vs_reference(results_dir / m, sat, day, ref,
                                       own_loader(m, day) if own_loader else None)     # CHANGED
            if not len(h):
                lines.append(f"{day:10} {m:3} no common epochs with reference")
                continue
            full.setdefault(m, ([], []))                                # CHANGED
            full[m][0].append(h + 24 * i)                               # CHANGED: hours since first day 00:00
            full[m][1].append(e)                                        # CHANGED
            mean, rms = e.mean(0), np.sqrt((e**2).mean(0))
            lines.append(f"{day:10} {m:3} {len(h):6d} " + " ".join(f"{x:7.2f}" for x in mean) + " "
                         + " ".join(f"{x:7.2f}" for x in rms) + f" {np.sqrt((e**2).sum(1).mean()):7.2f}")
    if not full:                                                        # CHANGED: one plot, all days
        return lines
    data = {m: (np.concatenate(h), np.concatenate(e)) for m, (h, e) in full.items()}
    allv = np.concatenate([np.abs(e).ravel() for _, e in data.values()])
    lim = max(np.percentile(allv, 99.9) * 1.1, 0.1)                    # keep cm-level visible; outliers counted
    fig, axes = plt.subplots(3, len(data), figsize=(4.2 * len(data) + 2 * (len(days) - 1), 7.5),
                             sharex=True, sharey=True, squeeze=False)
    for c, (m, (h, e)) in enumerate(data.items()):
        axes[0, c].set_title(f"{m}: {METHODS[m]}", color=INK, fontsize=10, loc="left")
        for k, comp in enumerate(["Radial", "Along-track", "Cross-track"]):
            ax = axes[k, c]
            ax.plot(h, e[:, k], lw=0.6, color=COLORS[m])
            for i in range(1, len(days)):                               # day boundaries
                ax.axvline(24 * i, color=MUTED, lw=0.6, ls=":")
            rms = np.sqrt((e[:, k] ** 2).mean())
            ax.text(0.02, 0.95, f"RMS {rms:.2f} cm", transform=ax.transAxes, va="top",
                    fontsize=8, color=INK, bbox=dict(fc="white", ec="none", alpha=0.8))
            ax.set_ylim(-lim, lim)
            ax.grid(color=GRID, lw=0.8)
            ax.tick_params(colors=MUTED, labelsize=8)
            for s in ax.spines.values():
                s.set_color(GRID)
            if c == 0:
                ax.set_ylabel(f"{comp} [cm]", color=INK)
        axes[-1, c].set_xlabel(f"Hours since {days[0]} 00:00 (GPS time)", color=INK)
    n_out = int((allv > lim).sum())
    span = days[0] if len(days) == 1 else f"{days[0]}_to_{days[-1]}"
    fig.suptitle(f"{title_sat} {span.replace('_to_', ' to ')}: orbit minus {ref_name}"
                 + (f"  ({n_out} values beyond axis)" if n_out else ""), color=INK, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(out_dir / f"orbit_error_vs_{tag}_{span}.png", dpi=150)
    plt.close(fig)
    return lines
