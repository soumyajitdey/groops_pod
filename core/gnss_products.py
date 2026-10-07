"""GPS orbit/clock/attitude/bias products for the GROOPS scripts (mission-independent).

--products repro3 (default): TU Graz IGS repro3 (TUG0R03FIN), the product set the TU Graz scripts are
    written for (orbits 5 min, clocks 30 s, attitude 30 s, code+phase signal biases).
    Sources, in order:
      1. NASA CDDIS repro3 weekly folders (needs an Earthdata login in ~/.netrc).
         Per TU Graz IFG, TUG0R03FIN_* files are in the IGS data centres' repro3 subdirectories.
      2. TU Graz repository (DOI 10.3217/dataset-4528-0723-0867): one zip per product for 1994-2020
         (orbits 3.4 GB, clocks 27.5 GB, biases 2.6 GB, attitude 46.2 GB). Only the needed daily files
         are read from the zips with HTTP range requests; the zips are NOT downloaded.
--products final: IGS final orbits + 30-s clocks (igsWWWWD.sp3/.clk_30s), downloaded with the
    leo-gps-pod code (core/legacy_download.py). No attitude, no signal biases.
--products ultra: IGS ultra-rapid (iguWWWWD_00.sp3 of the next day: observed half covers the day).
    Orbits AND clocks at 15-min sampling (IGS products page). No attitude, no signal biases.

Files are written to <dest>/ with the names the (mission) scripts expect; existing files are skipped.
"""
import gzip
import io
import sys
import urllib.request
import zipfile
from datetime import date, timedelta
from pathlib import Path

from core import settings

GPS0 = date(1980, 1, 6)

REPRO3_KINDS = {   # file name part -> TU Graz repository zip
    "01D_05M_ORB.SP3": "https://repository.tugraz.at/records/ebamh-r3860/files/TUG0R03FIN_1994-2020_01D_05M_ORB.SP3.zip?download=1",
    "01D_30S_CLK.CLK": "https://repository.tugraz.at/records/4r4fn-bx093/files/TUG0R03FIN_1994-2020_01D_30S_CLK.CLK.zip?download=1",
    "01D_30S_ATT.OBX": "https://repository.tugraz.at/records/hrm5k-3nf90/files/TUG0R03FIN_1994-2020_01D_30S_ATT.OBX.zip?download=1",
    "01D_01D_OSB.BIA": "https://repository.tugraz.at/records/xxr3e-tgt91/files/TUG0R03FIN_1994-2020_01D_01D_OSB.BIA.zip?download=1",
}
REPRO3_LOCAL = settings.WORK / "downloads" / "repro3"   # CHANGED: put the four TU Graz zips here (any download tool)
CDDIS_REPRO3 = "https://cddis.nasa.gov/archive/gnss/products/{wk}/repro3/{name}"   # CHANGED: path confirmed by user 2026-10-04


def ydoy(d):
    return f"{d.year}{d.timetuple().tm_yday:03d}"


def week(d):
    return (d - GPS0).days // 7


# ---------------- repro3 ----------------

class HttpRangeFile(io.RawIOBase):
    """Seekable read-only view of a remote file through HTTP range requests (for zipfile)."""

    def __init__(self, url):
        self.url, self.pos = url, 0
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Range": "bytes=0-0"}), timeout=120) as r:
            cr = r.headers.get("Content-Range")
            if r.status != 206 or not cr:                                                # CHANGED: report details
                raise IOError(f"no range support: status {r.status}, Content-Range {cr}, "
                              f"Accept-Ranges {r.headers.get('Accept-Ranges')}, final URL {r.geturl()}")
            self.size = int(cr.split("/")[-1])

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]
        return self.pos

    def readinto(self, b):
        if self.pos >= self.size:
            return 0
        end = min(self.pos + len(b), self.size) - 1
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{end}"})
        with urllib.request.urlopen(req, timeout=300) as r:
            data = r.read()
        b[:len(data)] = data
        self.pos += len(data)
        return len(data)


_ZIPS = {}


def _repro3_from_tugraz(kind, d, out):
    local = REPRO3_LOCAL / Path(REPRO3_KINDS[kind].split("?")[0]).name               # CHANGED: zip downloaded by hand
    if kind not in _ZIPS and local.is_file():                                          # CHANGED
        print(f"[products] reading {local}")                                           # CHANGED
        _ZIPS[kind] = zipfile.ZipFile(local)                                           # CHANGED
    if kind not in _ZIPS:
        print(f"[products] reading index of TU Graz repro3 zip ({kind})")
        url = REPRO3_KINDS[kind]
        urls = [url]
        if "/records/" in url and "/files/" in url:                                     # CHANGED: also InvenioRDM API URL
            rec, name = url.split("/records/")[1].split("?")[0].split("/files/")
            urls.append(f"https://repository.tugraz.at/api/records/{rec}/files/{name}/content")
        errors = []
        for u in urls:
            try:
                _ZIPS[kind] = zipfile.ZipFile(io.BufferedReader(HttpRangeFile(u), 1 << 20))
                break
            except Exception as e:
                errors.append(f"{u}: {e}")
        else:
            raise IOError("; ".join(errors))
    zf = _ZIPS[kind]
    stem = f"TUG0R03FIN_{ydoy(d)}0000_{kind}"
    hit = [n for n in zf.namelist() if Path(n).name.startswith(stem)]
    if not hit:
        raise IOError(f"{stem} not in TU Graz zip")
    data = zf.read(hit[0])
    out.write_bytes(data if data[:2] == b"\x1f\x8b" else gzip.compress(data))


def _repro3_day(d, dest):
    from core import download, legacy_download
    for kind in REPRO3_KINDS:
        name = f"TUG0R03FIN_{ydoy(d)}0000_{kind}.gz"
        out = Path(dest) / name
        if out.is_file():
            continue
        errors = []
        if (REPRO3_LOCAL / Path(REPRO3_KINDS[kind].split("?")[0]).name).is_file():   # CHANGED: 0. local zip first
            _repro3_from_tugraz(kind, d, out)                                         # CHANGED
            print(f"[products] {name} from local zip")                                # CHANGED
            continue                                                                  # CHANGED
        try:                                                     # 1. CDDIS (Earthdata login)
            b = legacy_download.get(CDDIS_REPRO3.format(wk=week(d), name=name), timeout=120)
            if b[:2] != b"\x1f\x8b":
                raise IOError("not a .gz file")
            out.write_bytes(b)
            print(f"[products] {name} from CDDIS")
            continue
        except Exception as e:
            errors.append(f"CDDIS: {e}")
        try:                                                     # 2. TU Graz repository (range requests)
            _repro3_from_tugraz(kind, d, out)
            print(f"[products] {name} from TU Graz repository")
        except Exception as e:
            errors.append(f"TU Graz repository: {e}")
            sys.exit(f"[products] {name} not available:\n  " + "\n  ".join(errors))


# ---------------- final / ultra (leo-gps-pod download code) ----------------

def _final_day(d, dest):
    from core import legacy_download as L
    names = {"sp3": f"IGS0FIN_{ydoy(d)}_ORB.SP3", "clk_30s": f"IGS0FIN_{ydoy(d)}_CLK.CLK"}
    if all((Path(dest) / n).is_file() for n in names.values()):
        return
    cache = settings.WORK / "downloads" / "gnss" / "igs_final"
    cache.mkdir(parents=True, exist_ok=True)
    rep = L.Report()
    paths = L.fetch_igs(d, str(cache), rep)
    for k, n in names.items():
        if k not in paths:
            sys.exit(f"[products] IGS final {k} for {d} failed: " + "; ".join(r[3] for r in rep.failed()))
        (Path(dest) / n).write_bytes(Path(paths[k]).read_bytes())


def _ultra_day(d, dest):
    from core import legacy_download as L
    out = Path(dest) / f"IGU_{ydoy(d)}_ORB.SP3"
    if out.is_file():
        return
    cache = settings.WORK / "downloads" / "gnss" / "igs_ultra"
    cache.mkdir(parents=True, exist_ok=True)
    rep = L.Report()
    p = L.fetch_igu(d, str(cache), rep)
    if not p:
        sys.exit(f"[products] IGS ultra-rapid for {d} failed: " + "; ".join(r[3] for r in rep.failed()))
    out.write_bytes(Path(p).read_bytes())


def get_products(kind, days, dest):
    """Place the GPS products for the days into dest (folder `igs` of the runs)."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    fn = {"repro3": _repro3_day, "final": _final_day, "ultra": _ultra_day}[kind]
    for day in days:
        fn(date.fromisoformat(day), dest)
    return dest
