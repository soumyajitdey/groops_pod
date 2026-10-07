"""CHAMP (2010-05-01 .. 2010-05-05) with the TU Graz GRACE-FO scenario scripts, minimum changes.

Script changes vs TU Graz (all others unchanged; generated at run time from the downloaded scenarios):
  all scripts   mission names: gracefo1 -> champ, folder gracefo -> champ. This points the scripts to
                TU Graz's CHAMP metadata (gnss/receiverLowEarthOrbiter/champ/...) and satellite model
                (satelliteModel/champ_satelliteModel.xml) in data.zip.
  dates         timeStart/timeEnd passed with groops --global (XML unchanged)
  02 convert    RINEX input = GFZ CH-OG-1-SST (RINEX 2.10), mapping file 02observationTypes.champ.txt
                GraceL1b2Orbit      -> Sp3Format2Orbit (GFZ RSO, SP3, satellite L06) + InstrumentConcatenate
                                       (sort, remove duplicate epochs of overlapping RSO arcs)
                GraceL1b2StarCamera -> Champ2AccStar (GFZ CH-OG-2-ACC, star camera only)
  03/04 GNSS    wavelengthFactor 0.5 -> 1 (CHAMP RINEX header: WAVELENGTH FACT L1/2 = 1 1)
  products      repro3: none. final/ultra: see core/gnss_products.py and _products_01() below.
A priori orbit (all options): GFZ RSO (decision 2026-10-02).
Continuous run (CHANGED 2026-10-06): each option is ONE GROOPS run over START 00:00 .. END+1 00:00
  (daily loop -> one loop: sampling 1 -> timeEnd-timeStart; InstrumentSynchronize: one time bin).
  Daily inputs are joined inside GROOPS (several input files per converter; ORBEX per day +
  InstrumentConcatenate; duplicate epochs removed). One OSB file per run: the day in the middle.
  Output: <option>/output/<START>/champ_orbit_<START>.txt (whole period, one file).
"""
import gzip
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, timedelta
from pathlib import Path

from core import download, gnss_products, plot_errors, run_groops, script_c, settings
from core.groops_io import read_orbit, read_orbit_table

NAME = "CHAMP"
SATELLITE = "champ"
START, END = "2010-05-01", "2010-05-02"        # CHANGED: first and last day to process (both included)
DAYS = [str(date.fromisoformat(START) + timedelta(days=k))                                    # CHANGED
        for k in range((date.fromisoformat(END) - date.fromisoformat(START)).days + 1)]       # CHANGED
TIME_START = (date.fromisoformat(START) - date(1858, 11, 17)).days    # CHANGED: MJD of START 00:00
TIME_END = TIME_START + len(DAYS)                                     # CHANGED: MJD of END+1 00:00 (exclusive)
PRODUCTS = ["repro3", "final", "ultra"]
RSO_ID = "L06"                                 # satellite identifier in the GFZ RSO SP3 files
# CHAMP RINEX 2.10 types -> RINEX 3 (receiver definition: TU Graz champ_receiverDefinition.xml)
OBS_TYPES = """# CHAMP RINEX 2.10 (GFZ CH-OG-1-SST) -> RINEX 3 types
# Source: GFZ (Koehler 2001), "RINEX format observable extensions for CHAMP SST Data" (CH-RINEX-EXT):
#   L1  = carrier phase on C/A channel, always available -> L1C
#   LP1 = phase measurement on L1, output only if P1 enabled -> L1W
#   SA  = SNR of C/A channel -> S1C; S1/S2 "as in standard RINEX" -> S1W/S2W (P channel: inferred, not stated)
  C1      C1C
  P1      C1W
  P2      C2W
  L1      L1C
  LP1     L1W
  L2      L2W
  SA      S1C
  S1      S1W
  S2      S2W
"""
# GROOPS data used by these scripts but not by the TU Graz scenario scripts (optional; checked before runs)
EXTRA_DATA = ["gnss/receiverLowEarthOrbiter/champ", "satelliteModel/champ_satelliteModel.xml",
              "gnss/transmitter/attitudeInfo", "gnss/transmitter/transmitterInfo/igs/igs20"]
TUG_ORBITS = "https://ftp.tugraz.at/pub/ITSG/satelliteOrbitProducts/operational/CHAMP/{kind}/2010/CHAMP_{kind}_{day}.txt.gz"
INPUTS = settings.WORK / "inputs" / "CHAMP"
D = "{loopTime:%D}"


# ---------------- inputs ----------------

def _first_member(zpath, test):
    with zipfile.ZipFile(zpath) as z:
        for m in z.infolist():
            text = z.read(m).decode("ascii", "replace")
            if test(text):
                return text
    sys.exit(f"[{NAME}] no usable file in {zpath}")


def _no_eof(text):                                                     # CHANGED: new
    """Remove 'EOF' lines from concatenated SP3 arcs: GROOPS Sp3Format2Orbit stops reading a file at
    the first EOF line (sp3Format2Orbit.cpp), so only the first arc was read. Repeated header lines
    of the following arcs are skipped by Sp3Format2Orbit."""
    return "".join(l for l in text.splitlines(True) if not l.startswith("EOF"))


def _get_inputs():
    """Per day in INPUTS/champ/: CH-OG-1-SST_<day>.rnx, ACC_<day>.dat, RSO_<day>.sp3 (existing files kept)."""
    from core import legacy_download as L
    out = INPUTS / "champ"
    out.mkdir(parents=True, exist_ok=True)
    dl = settings.WORK / "downloads" / "champ"
    for k in ("RINEX", "ACC", "RSO"):
        (dl / k).mkdir(parents=True, exist_ok=True)
    rep = L.Report()
    for day in DAYS:
        d = date.fromisoformat(day)
        rnx = out / f"CH-OG-1-SST_{day}.rnx"
        if not rnx.is_file():
            z = L.fetch_champ_rinex(d, str(dl / "RINEX"), rep)
            if not z:
                sys.exit(f"[{NAME}] RINEX {day} failed: " + "; ".join(r[3] for r in rep.failed()))
            rnx.write_text(_first_member(z, L._is_rnx))
        acc = out / f"ACC_{day}.dat"
        if not acc.is_file():
            z = L.fetch_champ_acc(d, str(dl / "ACC"), rep)
            if not z:
                sys.exit(f"[{NAME}] ACC {day} failed: " + "; ".join(r[3] for r in rep.failed()))
            text = _first_member(z, L._is_asc)
            head = "\n".join(l for l in text.splitlines()[:60] if l.startswith("+"))
            if "+reference" in head and "utc" in head.split("+reference")[1].split("\n")[0].lower():
                sys.exit(f"[{NAME}] {z}: time reference is UTC; GROOPS Champ2AccStar expects GPS time. Stopped.")
            if "\natt " not in text:
                sys.exit(f"[{NAME}] {z}: no attitude ('att') records; Champ2AccStar would give no star camera data.")
            acc.write_text(text)
        rso = out / f"RSO_{day}.sp3"
        if rso.is_file() and "\nEOF" in rso.read_text():                  # CHANGED: file from the earlier version
            rso.write_text(_no_eof(rso.read_text()))                        # CHANGED
        if not rso.is_file():                       # arcs of the day's and the next day's folder
            arcs = []
            for dd in (d, d + timedelta(days=1)):
                arcs += L.fetch_champ_rso(dd, str(dl / "RSO"), rep)
            if not arcs:
                sys.exit(f"[{NAME}] RSO {day} failed: " + "; ".join(r[3] for r in rep.failed()))
            rso.write_text(_no_eof("".join(gzip.open(a, "rt").read() for a in sorted(set(arcs)))))   # CHANGED
    return out


# ---------------- scripts ----------------

def _names(text):
    return text.replace("gracefo1", SATELLITE).replace("gracefo", SATELLITE)


def _xml(root):
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


def _programs_with(root, tag):
    return [p for p in root.iter("program") if p.find(tag) is not None]


def _products_01(text, products):
    """TU Graz 01groopsConvert.xml for the product type (repro3: unchanged)."""
    if products == "repro3":
        return text
    root = ET.fromstring(text)
    name = {"final": "IGS0FIN", "ultra": "IGU"}[products]
    for p in _programs_with(root, "Sp3Format2Orbit"):
        sp3 = p.find("Sp3Format2Orbit")
        sp3.find("inputfile").text = f"igs/{name}_{{loopTime:%y%03O}}_ORB.SP3"
        if products == "ultra":                     # clocks are in the ultra-rapid SP3 file
            ET.SubElement(sp3, "outputfileClock").text = f"data/{D}/clock/clock_{D}.{{prn}}.dat"
    for p in _programs_with(root, "GnssClockRinex2InstrumentClock"):
        if products == "final":
            p.find("GnssClockRinex2InstrumentClock/inputfileClockRinex").text = f"igs/{name}_{{loopTime:%y%03O}}_CLK.CLK"
        else:
            p.set("disabled", "1")
    for tag in ("GnssOrbex2StarCamera", "GnssSinexBias2SignalBias"):   # no attitude / biases in these products
        for p in _programs_with(root, tag):
            p.set("disabled", "1")
    for p in root.iter("program"):                  # TU Graz's own alternative: simulated GPS attitude
        if p.get("comment", "").startswith("(alternative) simulated satellite attitude"):
            p.attrib.pop("disabled", None)
    return _xml(root)


def _convert_02(text):
    """TU Graz 02groopsConvertGracefo.xml with the CHAMP converters."""
    root = ET.fromstring(text)
    for p in _programs_with(root, "RinexObservation2GnssReceiver"):
        r = p.find("RinexObservation2GnssReceiver")
        r.find("inputfileRinexObservation").text = f"champ/CH-OG-1-SST_{D}.rnx"
        r.find("inputfileSpecialObservationTypes").text = "02observationTypes.champ.txt"
    loop = root.find("program/LoopPrograms")
    for p in _programs_with(root, "GraceL1b2Orbit"):
        g = p.find("GraceL1b2Orbit")
        out = g.find("outputfileOrbit").text
        tmp = out.replace("_orbit_", "_orbitRso_")
        p.remove(g)
        s = ET.SubElement(p, "Sp3Format2Orbit")
        ET.SubElement(s, "outputfileOrbit").text = tmp
        ET.SubElement(s, "satelliteIdentifier").text = RSO_ID
        s.append(g.find("earthRotation"))
        ET.SubElement(s, "inputfile").text = f"champ/RSO_{D}.sp3"
        cat = ET.Element("program", {"comment": out + " (RSO arcs sorted, duplicate epochs removed)"})
        c = ET.SubElement(cat, "InstrumentConcatenate")
        ET.SubElement(c, "outputfile").text = out
        ET.SubElement(c, "inputfile").text = tmp
        ET.SubElement(c, "sort").text = "1"
        rd = ET.SubElement(c, "removeDuplicates")
        ET.SubElement(ET.SubElement(rd, "keepFirst"), "margin").text = "1e-5"
        loop.insert(list(loop).index(p) + 1, cat)
    for p in _programs_with(root, "GraceL1b2StarCamera"):
        g = p.find("GraceL1b2StarCamera")
        out = g.find("outputfileStarCamera").text
        p.remove(g)
        c = ET.SubElement(p, "Champ2AccStar")
        ET.SubElement(c, "outputfileStarCamera").text = out
        ET.SubElement(c, "inputfile").text = f"champ/ACC_{D}.dat"
    return _xml(root)


def _gnss(text, products):
    """TU Graz GNSS processing script for CHAMP."""
    root = ET.fromstring(text)
    for leo in root.iter("lowEarthOrbiter"):
        leo.find("wavelengthFactor").text = "1"              # CHAMP RINEX header: full-cycle L1/L2
        if products != "repro3":
            leo.find("supportsIntegerAmbiguities").text = "0"  # no satellite phase biases -> float only
    if products != "repro3":
        for sb in root.iter("signalBiases"):
            e = sb.find("inputfileSignalBiasTransmitter")
            if e is not None:
                sb.remove(e)
    return _xml(root)


def setup(products):
    if products not in PRODUCTS:
        sys.exit(f"[{NAME}] unknown --products {products}")
    sc = {n: download.get_scenario(n) for n in ("kinematic", "reducedDynamic")}
    champ = _get_inputs()
    igs = gnss_products.get_products(products, DAYS, INPUTS / f"igs_{products}")
    kin, rd = sc["kinematic"], sc["reducedDynamic"]
    s01 = _products_01((kin / "01groopsConvert.xml").read_text(), products)
    s02 = _names(_convert_02((kin / "02groopsConvertGracefo.xml").read_text()))
    var = _names((rd / "03groopsVariational.xml").read_text())
    scripts = {
        "01groopsConvert.xml": s01,
        "02groopsConvertChamp.xml": s02,
        "03groopsGnssProcessing.xml": _names(_gnss((kin / "03groopsGnssProcessing.xml").read_text(), products)),
        "03groopsVariational.xml": var,
        "04groopsGnssProcessing.xml": _names(_gnss((rd / "04groopsGnssProcessing.xml").read_text(), products)),
        "03groopsKinematicOrbitFit.xml": script_c.make_script_c(var, SATELLITE),
    }
    return {"scenarios": sc, "template_dirs": [kin, rd], "extra_data": EXTRA_DATA, "products": products,
            "globals": {"timeStart": str(TIME_START), "timeEnd": str(TIME_END)},
            "scripts": scripts, "champ": champ, "igs": igs}


# ---------------- continuous run (CHANGED 2026-10-06: new) ----------------

def _mjd(day):
    return (date.fromisoformat(day) - date(1858, 11, 17)).days


def _day(mjd):
    return str(date(1858, 11, 17) + timedelta(days=int(mjd // 1)))


def _sub(text, day):
    """Daily file name template -> file name of one day."""
    d = date.fromisoformat(day)
    return text.replace("{loopTime:%y%03O}", f"{d.year}{d.timetuple().tm_yday:03d}").replace("{loopTime:%D}", day)


def _concat(out, inputs):
    """GROOPS program: InstrumentConcatenate (sort, remove duplicate epochs) of instrument files."""
    p = ET.Element("program", {"comment": out + " (joined, sorted, duplicate epochs removed)"})
    c = ET.SubElement(p, "InstrumentConcatenate")
    ET.SubElement(c, "outputfile").text = out
    for i in inputs:
        ET.SubElement(c, "inputfile").text = i
    ET.SubElement(c, "sort").text = "1"
    ET.SubElement(ET.SubElement(ET.SubElement(c, "removeDuplicates"), "keepFirst"), "margin").text = "1e-5"
    return p


def _window(text, t0, t1):
    """TU Graz script -> one GROOPS loop over [t0, t1) [MJD] with the daily inputs of all days in it."""
    import copy
    root = ET.fromstring(text)
    parent = {c: p for p in root.iter() for c in p}
    days = [_day(m) for m in range(int(t0 // 1), int(-(-t1 // 1)))]
    center = _day((t0 + t1) / 2)
    for u in root.iter("uniformSampling"):                       # daily loop -> one loop over the window
        if u.find("timeStart") is not None and u.find("timeStart").get("link") == "timeStart":
            u.find("sampling").text = "timeEnd-timeStart"
    for sync in root.iter("InstrumentSynchronize"):              # one time bin = the window (cuts data to it)
        for u in sync.iter("uniformSampling"):
            u.find("sampling").text = "loopTimeEnd-loopTime"
    multi = {"Sp3Format2Orbit": "inputfile", "GnssClockRinex2InstrumentClock": "inputfileClockRinex",
             "RinexObservation2GnssReceiver": "inputfileRinexObservation", "Champ2AccStar": "inputfile"}
    for tag, field in multi.items():                             # converters with several input files
        for prog in root.iter(tag):
            for e in [e for e in prog.findall(field) if "{loopTime:" in (e.text or "")]:
                i = list(prog).index(e)
                prog.remove(e)
                for k, day in enumerate(days):
                    n = ET.Element(field)
                    n.text = _sub(e.text, day)
                    prog.insert(i + k, n)
    for tag, field in (("Sp3Format2Orbit", "outputfileOrbit"), ("Champ2AccStar", "outputfileStarCamera"),
                       ("RinexObservation2GnssReceiver", "outputfileGnssReceiver")):
        for prog in list(root.iter(tag)):                        # day boundaries: sort, remove duplicates
            p = parent[prog]
            out = prog.find(field).text
            nxt = list(parent[p])[list(parent[p]).index(p) + 1:]
            if nxt and nxt[0].find("InstrumentConcatenate") is not None:
                continue                                         # already followed by a concatenation (RSO)
            parent[p].insert(list(parent[p]).index(p) + 1, _concat(out, [out]))
    for prog in list(root.iter("GnssSinexBias2SignalBias")):     # one bias file per run: day of window center
        prog.find("inputfileSinexBias").text = _sub(prog.find("inputfileSinexBias").text, center)
    for g in list(root.iter("GnssOrbex2StarCamera")):            # ORBEX: one program per day + join per PRN
        p = parent[g]
        if p.get("disabled") == "1":
            continue
        loop, out, inp = parent[p], g.find("outputfileStarCamera").text, g.find("inputfileOrbex").text
        i = list(loop).index(p)
        loop.remove(p)
        parts = []
        for k, day in enumerate(days):
            q = copy.deepcopy(p)
            q.find("GnssOrbex2StarCamera/outputfileStarCamera").text = out.replace(".dat", f"_part{k}.dat")
            q.find("GnssOrbex2StarCamera/inputfileOrbex").text = _sub(inp, day)
            loop.insert(i + k, q)
            parts.append(out.replace(".dat", f"_part{k}.{{prn}}.dat"))
        prn_loop = copy.deepcopy(next(parent[s] for s in loop.iter("program") if s.find("Sp3Format2Orbit") is not None
                                      and parent[s].tag == "LoopPrograms"))
        for q in prn_loop.findall("program"):
            prn_loop.remove(q)
        prn_loop.append(_concat(out.replace(".dat", ".{prn}.dat"), parts))
        holder = ET.Element("program", {"comment": "attitude per PRN joined over the window"})
        holder.append(prn_loop)
        loop.insert(i + len(days), holder)
    return _xml(root)



ORDER = {"A": ["01groopsConvert.xml", "02groopsConvertChamp.xml", "03groopsGnssProcessing.xml"],
         "B": ["01groopsConvert.xml", "02groopsConvertChamp.xml", "03groopsVariational.xml", "04groopsGnssProcessing.xml"],
         "C": ["01groopsConvert.xml", "02groopsConvertChamp.xml", "03groopsKinematicOrbitFit.xml"]}


def run_files(method, ctx):
    scripts = ORDER[method]
    files = {s: _window(ctx["scripts"][s], TIME_START, TIME_END) for s in scripts}             # CHANGED: one run
    files.update({"02observationTypes.champ.txt": OBS_TYPES, "champ": ctx["champ"], "igs": ctx["igs"]})
    return files, list(scripts), dict(ctx["globals"])


# ---------------- validation ----------------

def _rso_reference(results, ctx, data_dir, exe):
    """GFZ RSO converted by GROOPS (Sp3Format2Orbit + InstrumentConcatenate), as in script 02."""
    done_dirs = sorted(results.glob(f"RSO*/{run_groops.OK}"))
    if done_dirs:                                   # converted earlier for this results folder
        return done_dirs[-1].parent
    rdir = results / "RSO"
    if rdir.exists():                               # earlier conversion failed: new folder, old one kept
        import time
        rdir = results / f"RSO_{time.strftime('%Y%m%d_%H%M%S')}"
    eop = "{groopsDataDir}/earthRotation/timeSeries_EOP_rapid_IAU2000_desai.dat"
    progs = ""
    for day in DAYS:
        progs += f"""  <program><FileCreateDirectories><directory>output/{day}</directory></FileCreateDirectories></program>
  <program><Sp3Format2Orbit>
    <outputfileOrbit>output/{day}/rso_tmp.dat</outputfileOrbit>
    <satelliteIdentifier>{RSO_ID}</satelliteIdentifier>
    <earthRotation><file><inputfileEOP>{eop}</inputfileEOP><interpolationDegree>3</interpolationDegree></file></earthRotation>
    <inputfile>champ/RSO_{day}.sp3</inputfile>
  </Sp3Format2Orbit></program>
  <program><InstrumentConcatenate>
    <outputfile>output/{day}/{SATELLITE}_rso_{day}.txt</outputfile>
    <inputfile>output/{day}/rso_tmp.dat</inputfile>
    <sort>1</sort><removeDuplicates><keepFirst><margin>1e-5</margin></keepFirst></removeDuplicates>
  </InstrumentConcatenate></program>
"""
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<groops>\n  <global><filename label="groopsDataDir">x</filename></global>\n'
           + progs + "</groops>\n")
    run_groops.prepare(rdir, {"rsoReference.xml": xml, "champ": ctx["champ"]})
    run_groops.run_scripts(rdir, ["rsoReference.xml"], data_dir, exe)
    (rdir / run_groops.OK).write_text("GFZ RSO in GROOPS frame\n")
    return rdir


def _tug_loader(kind):
    def load(day):
        url = TUG_ORBITS.format(kind=kind, day=day)
        try:
            p = download.fetch_url([url], settings.WORK / "downloads" / "champ" / "TUG" / Path(url).name)
            return read_orbit_table(p)
        except SystemExit as e:
            print(f"[validate] {e}")
            return None
    return load


def _own_loader(results):                                              # CHANGED: new
    """Our orbit of one day, cut from the run's single output file."""
    cache = {}
    def load(m, day):
        if m not in cache:
            cache[m] = read_orbit(results / m / "output" / START / f"{SATELLITE}_orbit_{START}.txt")
        t, p, v = cache[m]
        k = (t >= _mjd(day)) & (t < _mjd(day) + 1)
        return t[k], p[k], v[k]
    return load


def validate(results, done, out, ctx, data_dir, exe):
    lines = []
    own = _own_loader(results)                                        # CHANGED
    try:
        rdir = _rso_reference(results, ctx, data_dir, exe)
        rso = lambda day: read_orbit(rdir / "output" / day / f"{SATELLITE}_rso_{day}.txt")
        lines += plot_errors.plot_vs_reference(results, done, SATELLITE, DAYS,
                                               "RSO (GFZ, a priori orbit of all options)", rso, out, NAME, own)   # CHANGED
    except SystemExit as e:                         # one failed reference does not stop the others
        lines += ["", f"=== vs RSO: SKIPPED ({e}) ==="]
    lines += plot_errors.plot_vs_reference(results, done, SATELLITE, DAYS,
                                           "TUG-kinematic (TU Graz published kinematic orbit)",
                                           _tug_loader("kinematicOrbit"), out, NAME, own)              # CHANGED
    lines += plot_errors.plot_vs_reference(results, done, SATELLITE, DAYS,
                                           "TUG-reduced-dynamic (TU Graz published reduced-dynamic orbit)",
                                           _tug_loader("reducedDynamicOrbit"), out, NAME, own)         # CHANGED
    return lines
