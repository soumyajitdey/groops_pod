"""Readers for GROOPS text output files (instrument and signal-bias formats).

Instrument text layout (checked on the TU Graz reference outputs):
  line 1  groops instrument version=...
  line 2  # ORBIT  /  # COVARIANCE3D
  line 3  <type> <flag>
  line 4  # column header
  line 5  # =====
  line 6  <number of epochs>
  line 7+ MJD data0 data1 ...
"""
import numpy as np


def read_instrument(path):
    """Return (kind, data). Column 0 is time [MJD]."""
    with open(path) as f:
        lines = f.readlines()
    kind = lines[1].strip("# \n")
    n = int(lines[5])
    data = np.loadtxt(lines[6:], ndmin=2)
    if data.shape[0] != n:
        raise ValueError(f"{path}: header says {n} epochs, found {data.shape[0]}")
    return kind, data


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
