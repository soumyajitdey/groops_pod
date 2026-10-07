"""Readers for GROOPS text output files (instrument and signal-bias formats).

Instrument text layout (checked on the TU Graz reference outputs):
  line 1  groops instrument version=...
  line 2  # ORBIT  /  # COVARIANCE3D
  line 3  <type> <flag>
  line 4  # column header
  line 5  # =====
  line 6  <number of epochs of arc 1>, then its epochs: MJD data0 data1 ...
          further arcs follow the same way (<number of epochs>, epochs)
"""
import numpy as np


def read_instrument(path):
    """Return (kind, data). Column 0 is time [MJD]."""
    with open(path) as f:
        lines = f.readlines()
    kind = lines[1].strip("# \n")
    arcs, i = [], 5                                                     # CHANGED: files with several arcs:
    while i < len(lines) and lines[i].strip():                          # CHANGED: <count> + epochs, per arc
        n = int(lines[i])                                               # CHANGED
        arcs.append(np.loadtxt(lines[i + 1:i + 1 + n], ndmin=2))        # CHANGED
        if arcs[-1].shape[0] != n:                                      # CHANGED
            raise ValueError(f"{path}: arc header says {n} epochs, found {arcs[-1].shape[0]}")
        i += 1 + n                                                      # CHANGED
    return kind, np.vstack(arcs)                                        # CHANGED


def read_orbit(path):
    """Return t [MJD], pos [m] (N,3), vel [m/s] (N,3; zeros in kinematic orbits)."""
    kind, d = read_instrument(path)
    if kind != "ORBIT":
        raise ValueError(f"{path}: expected ORBIT, got {kind}")
    return d[:, 0], d[:, 1:4], d[:, 4:7]


def read_covariance3d(path):
    """Return t [MJD], cov [m^2] (N,3,3) from columns xx yy zz xy xz yz."""
    kind, d = read_instrument(path)
    if kind != "COVARIANCE3D":
        raise ValueError(f"{path}: expected COVARIANCE3D, got {kind}")
    xx, yy, zz, xy, xz, yz = d[:, 1:7].T
    cov = np.stack([np.stack([xx, xy, xz], -1),
                    np.stack([xy, yy, yz], -1),
                    np.stack([xz, yz, zz], -1)], -2)
    return d[:, 0], cov


def read_orbit_table(path):
    """Orbit from any text table (optionally .gz) whose numeric rows are MJD x y z [vx vy vz] [m, m/s].
    Header/comment lines are skipped. Returns t, pos, vel (None if the file has no velocity columns)."""
    import gzip
    op = gzip.open if str(path).endswith(".gz") else open
    rows = []
    with op(path, "rt") as f:
        for ln in f:
            p = ln.split()
            if len(p) < 4 or ln.lstrip().startswith("#"):
                continue
            try:
                v = [float(x) for x in p]
            except ValueError:
                continue
            if v[0] > 40000:
                rows.append(v[:7])
    n = min(len(r) for r in rows) if rows else 0
    d = np.array([r[:n] for r in rows])
    if not len(d):
        raise ValueError(f"{path}: no orbit rows found")
    return d[:, 0], d[:, 1:4], (d[:, 4:7] if n >= 7 else None)


def read_signal_bias(path):
    """Return {signal type: bias [m]} from a GROOPS gnssSignalBias text file."""
    out = {}
    with open(path) as f:
        for line in f.readlines()[2:]:
            if line.startswith("#") or not line.strip():
                continue
            typ, val = line.split()
            out[typ] = float(val)
    return out
