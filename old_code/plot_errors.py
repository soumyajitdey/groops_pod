"""Orbit error plots: options A, B, C minus the published GRACE-FO GNV1B orbit (JPL).

Differences are rotated into radial (R), along-track (T), cross-track (N) using the GNV1B
position and velocity. One PNG per day; statistics are returned for the report.
Note: GNV1B is not independent of B and C (it is their a priori orbit; see README).
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import config
from compare import _match, _rtn
from groops_io import read_orbit

# Categorical slots 1-3 of the reference palette (validated: CVD and normal-vision separation pass).
COLORS = {"A": "#2a78d6", "B": "#eb6834", "C": "#1baf7a"}
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e6e5e0"


def errors_vs_gnv1b(run_dir, gnv1b_dir, day):
    """Return hours since midnight and R/T/N differences [cm] of one run vs GNV1B."""
    f = f"{day}/{config.SATELLITE}_orbit_{day}.txt"
    t, p, _ = read_orbit(Path(run_dir) / "output" / f)
    tg, pg, vg = read_orbit(Path(gnv1b_dir) / "output" / day / f"{config.SATELLITE}_gnv1b_{day}.txt")
    i, j = _match(t, tg)
    rtn = _rtn(p[i] - pg[j], pg[j], vg[j]) * 100
    return (t[i] - np.floor(t[0])) * 24, rtn


def plot_session(session_dir, methods, out_dir):                     # CHANGED: output folder given by caller
    session_dir = Path(session_dir)
    out_dir = Path(out_dir)                                           # CHANGED
    out_dir.mkdir(parents=True, exist_ok=True)                        # CHANGED
    lines = ["", "=== orbit minus published GNV1B (cm) ===",
             f"{'day':10} {'opt':3} {'epochs':>6} {'R mean':>7} {'T mean':>7} {'N mean':>7} "
             f"{'R RMS':>7} {'T RMS':>7} {'N RMS':>7} {'3D RMS':>7}"]
    for day in config.DAYS:
        data = {m: errors_vs_gnv1b(session_dir / m, session_dir / "GNV1B", day) for m in methods}
        allv = np.concatenate([np.abs(e).ravel() for _, e in data.values()])
        lim = max(np.percentile(allv, 99.9) * 1.1, 0.1)                # keep cm-level visible; outliers counted
        # one column per option (small multiples), rows R/T/N, shared axes
        fig, axes = plt.subplots(3, len(data), figsize=(4.2 * len(data), 7.5), sharex=True, sharey=True,
                                 squeeze=False)
        for c, (m, (h, e)) in enumerate(data.items()):
            axes[0, c].set_title(f"{m}: {config.METHODS[m]['label']}", color=INK, fontsize=10, loc="left")
            for k, comp in enumerate(["Radial", "Along-track", "Cross-track"]):
                ax = axes[k, c]
                ax.plot(h, e[:, k], lw=0.8, color=COLORS[m])
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
            axes[-1, c].set_xlabel("Hours of day (GPS time)", color=INK)
        n_out = int((allv > lim).sum())
        fig.suptitle(f"GRACE-FO C {day}: orbit minus published GNV1B orbit"
                     + (f"  ({n_out} values beyond axis)" if n_out else ""), color=INK, x=0.01, ha="left")
        fig.tight_layout()
        fig.savefig(out_dir / f"orbit_error_vs_gnv1b_{day}.png", dpi=150)
        plt.close(fig)
        for m, (h, e) in data.items():
            mean, rms = e.mean(0), np.sqrt((e**2).mean(0))
            lines.append(f"{day:10} {m:3} {len(h):6d} " + " ".join(f"{x:7.2f}" for x in mean) + " "
                         + " ".join(f"{x:7.2f}" for x in rms) + f" {np.sqrt((e**2).sum(1).mean()):7.2f}")
    return lines
