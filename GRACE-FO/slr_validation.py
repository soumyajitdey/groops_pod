"""SLR validation of the A/B/C orbits with GROOPS (SlrProcessing). Used by validate.py.

SLR is used ONLY for validation; the POD stays GPS-only.

Steps (all GROOPS programs; Python only writes the XML, downloads files and plots):
 1. Normal points: EDC (DGFI-TUM) daily CRD files -> GROOPS format (Crd2NormalPoints).
 2. Satellite metadata: GROOPS data.zip has no SLR satellite file for GRACE-FO, so one is created with
    GROOPS PlatformCreate: laser retroreflector (LRR) at the JPL VSL1B offset (vector from the satellite
    frame origin to the LRR; GRACE-FO L1 handbook Sect. 2.5.6). The frame origin is the accelerometer
    proof mass, within 0.1 mm of the centre of mass (handbook Sect. 3.2.3), so no reference point is set.
 3. Residuals (observed - computed range) for each orbit with SlrProcessing, orbit held fixed:
    one estimate step with no unknown parameters, no reweighting. Station models (GROOPS settings as
    documented for station networks, gnssReceiverGeneratorStationNetwork.h): SLRF2020 positions,
    solid Earth tide, FES2014b ocean tide loading (minDegree 1), pole tide, ocean pole tide;
    troposphere Mendes & Pavlis (2004) with the CRD meteorological data; elevation cut-off 5 deg.
    No range/time biases: GROOPS notes the ILRS biases are only suitable for passive satellites
    (slrParametrizationRangeBiasStationApriori.h).
 4. Plots + statistics.

The XML scripts written here are NOT from TU Graz; they only combine GROOPS programs/classes.
"""
import re
import sys
import tarfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from core import download, run_groops                                  # CHANGED: shared core
from core.plot_errors import COLORS, GRID, INK, MUTED                  # CHANGED
from core.settings import METHODS, WORK                                # CHANGED


class config:                                                          # CHANGED: GRACE-FO SLR settings (were in config.py)
    DAYS = ["2020-01-01", "2020-01-02"]
    SATELLITE = "gracefo1"
    WORK = WORK
    SLR_SATELLITE = "gracefo1"                       # ILRS/EDC name of GRACE-FO C
    SLR_NPT_URL = "https://edc.dgfi.tum.de/pub/slr/data/npt_crd/{sat}/{year}/{sat}_{ymd}.npt"
    L1B_URL = "https://isdc-data.gfz.de/grace-fo/Level-1B/JPL/INSTRUMENT/RL04/{year}/gracefo_1B_{day}_RL04.ascii.noLRI.tgz"
    L1B_SAT_LETTER = "C"
    LRR_POSITION = None          # [m]; None = read from JPL VSL1B (GRACE-FO L1 handbook, Sect. 2.5.6)
    LRR_RANGE_CORRECTION = 0.0   # [m] NOT SOURCED yet

GPS_EPOCH_MJD = 51544.5   # GRACE-FO L1B gps_time = seconds since 2000-01-01 12:00 (GNV1B header epoch_time)


def _write(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text)
    return Path(path)


def _groops_xml(programs):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<groops>\n'
            '  <global><filename label="groopsDataDir">/set/by/--global</filename></global>\n'
            + programs + '\n</groops>\n')


# ---------------- 1. normal points ----------------

def get_normal_points(day):
    y, ymd = day[:4], day.replace("-", "")
    url = config.SLR_NPT_URL.format(sat=config.SLR_SATELLITE, year=y, ymd=ymd)
    return download.fetch_url([url], config.WORK / "downloads" / "slr" / Path(url).name)


# ---------------- 2. LRR position ----------------

def _yaml_variables(lines):
    names, on = [], False
    for ln in lines:
        if ln.strip().startswith("variables:"):
            on = True
            continue
        if on:
            m = re.match(r"^\s{4}- (\w+):", ln)
            if m:
                names.append(m.group(1))
            if "End of YAML" in ln:
                break
    return names


def lrr_position():
    """LRR offset in the satellite frame [m]: config.LRR_POSITION, else JPL VSL1B."""
    if config.LRR_POSITION is not None:
        return np.array(config.LRR_POSITION, float), "config.LRR_POSITION"
    out = config.WORK / "downloads" / "gracefo_l1b"
    for day in config.DAYS:
        cached = out / f"VSL1B_{day}_{config.L1B_SAT_LETTER}.txt"
        if not cached.is_file():
            url = config.L1B_URL.format(year=day[:4], day=day)
            tgz = download.fetch_url([url], out / Path(url).name)
            with tarfile.open(tgz) as tf:
                m = [x for x in tf.getmembers() if "VSL1B" in x.name and f"_{config.L1B_SAT_LETTER}_" in x.name]
                if not m:
                    names = sorted({Path(x.name).name.split("_")[0] for x in tf.getmembers()})
                    print(f"[slr] no VSL1B in {tgz.name}; products in archive: {', '.join(names)}")
                    continue
                cached.write_bytes(tf.extractfile(m[0]).read())
        lines = cached.read_text().splitlines()
        var = _yaml_variables(lines)
        end = next(i for i, l in enumerate(lines) if "End of YAML" in l)
        rows = [l.split() for l in lines[end + 1:] if l.strip()]
        if not rows:
            continue
        rec = dict(zip(var, rows[-1]))
        if all(k in rec for k in ("mag", "cosx", "cosy", "cosz")):
            v = float(rec["mag"]) * np.array([float(rec["cosx"]), float(rec["cosy"]), float(rec["cosz"])])
        else:
            sys.exit(f"[slr] unknown VSL1B format in {cached}: variables {var}")
        return v, f"JPL VSL1B ({cached.name}, gps_time {rec.get('gps_time')})"
    sys.exit("[slr] VSL1B not found in the GRACE-FO L1B archives; set config.LRR_POSITION from a sourced value")


def make_satellite_info(slr_dir, exe, data_dir):
    pos, src = lrr_position()
    sat = config.SLR_SATELLITE
    info = slr_dir / "metadata" / f"satelliteInfo.{sat}.xml"
    if not info.is_file():
        xml = _groops_xml(f"""  <program comment="SLR metadata {sat} (LRR from {src})">
    <PlatformCreate>
      <outputfilePlatform>{info}</outputfilePlatform>
      <markerName>{sat}</markerName>
      <equipment>
        <laserRetroReflector>
          <name>GFZ</name>
          <comment>position from {src}</comment>
          <positionX>{pos[0]:.6f}</positionX>
          <positionY>{pos[1]:.6f}</positionY>
          <positionZ>{pos[2]:.6f}</positionZ>
          <range>{config.LRR_RANGE_CORRECTION}</range>
        </laserRetroReflector>
      </equipment>
    </PlatformCreate>
  </program>""")
        _write(slr_dir / "metadata" / "platformCreate.xml", xml)
        run_groops.run_scripts(slr_dir / "metadata", ["platformCreate.xml"], data_dir, exe)
    _write(slr_dir / "metadata" / "satelliteList.txt", sat + "\n")
    return info, pos, src


# ---------------- 3. residuals ----------------

def _station_position_dir(data_dir):
    base = Path(data_dir) / "slr" / "stations" / "position"
    dirs = sorted(d.name for d in base.iterdir() if d.is_dir()) if base.is_dir() else []
    for name in ["slrf2020_CM"] + [d for d in dirs if "slrf2020" in d.lower()]:
        if (base / name).is_dir():
            return name
    sys.exit(f"[slr] no SLRF2020 station position folder in {base}; found: {dirs}")


def _station_list(data_dir):
    base = Path(data_dir) / "slr" / "stations"
    for name in ["stationList.slrf2020.txt", "stationList.txt"]:
        if (base / name).is_file():
            return name
    sys.exit(f"[slr] no station list in {base}")


def convert_normal_points(slr_dir, day, data_dir, exe):
    np_dir = slr_dir / "normalPoints" / day
    if (np_dir / run_groops.OK).is_file():
        return np_dir
    npt = get_normal_points(day)
    xml = _groops_xml(f"""  <program>
    <Crd2NormalPoints>
      <outputfileNormalPoints>normalPoints_{{station}}.dat</outputfileNormalPoints>
      <outputfileMeteorological>meteorological_{{station}}.dat</outputfileMeteorological>
      <inputfileSlrData>{npt.resolve()}</inputfileSlrData>
    </Crd2NormalPoints>
  </program>""")
    _write(np_dir / "crd2NormalPoints.xml", xml)
    run_groops.run_scripts(np_dir, ["crd2NormalPoints.xml"], data_dir, exe)
    (np_dir / run_groops.OK).write_text(npt.name + "\n")
    return np_dir


def slr_script(run_dir, day, np_dir, info, slr_dir, data_dir):
    sat = config.SLR_SATELLITE
    pos_dir = _station_position_dir(data_dir)
    st_list = _station_list(data_dir)
    D = "{groopsDataDir}"
    mjd0 = (np.datetime64(day) - np.datetime64("1858-11-17")).astype(int)
    orbit = Path(run_dir) / "output" / day / f"{config.SATELLITE}_orbit_{day}.txt"
    att = Path(run_dir) / "data" / day / "gracefo" / f"{config.SATELLITE}_starCamera_{day}.dat"
    eop = f"""<earthRotation><file><inputfileEOP>{D}/earthRotation/timeSeries_EOP_rapid_IAU2000_desai.dat</inputfileEOP><interpolationDegree>3</interpolationDegree></file></earthRotation>"""
    eph = f"""<ephemerides><jpl><inputfileEphemerides>{D}/tides/ephemerides_JPL_DE432.dat</inputfileEphemerides><origin><earth/></origin></jpl></ephemerides>"""
    return _groops_xml(f"""  <program comment="SLR residuals, {sat} {day}">
    <SlrProcessing>
      <timeSeries><uniformSampling><timeStart>{mjd0}</timeStart><timeEnd>{mjd0 + 1}</timeEnd><sampling>10/1440</sampling></uniformSampling></timeSeries>
      <satellite>
        <satellites>
          <inputfileSatelliteList>{slr_dir / 'metadata' / 'satelliteList.txt'}</inputfileSatelliteList>
          <inputfileSatelliteInfo>{info}</inputfileSatelliteInfo>
          <inputfileOrbit>{orbit}</inputfileOrbit>
          <inputfileAttitude>{att}</inputfileAttitude>
          <interpolationDegree>7</interpolationDegree>
        </satellites>
      </satellite>
      <station>
        <stations>
          <inputfileStationList>{D}/slr/stations/{st_list}</inputfileStationList>
          <inputfileStationInfo>{D}/slr/stations/stationInfo/stationInfo.{{station}}.xml</inputfileStationInfo>
          <inputfileStationPosition>{D}/slr/stations/position/{pos_dir}/stationPosition.{{station}}.dat</inputfileStationPosition>
          <disableStationWithoutPosition>1</disableStationWithoutPosition>
          <inputfileObservations>{np_dir}/normalPoints_{{station}}.dat</inputfileObservations>
          <accuracy>if(abs(residual)&gt;30, NAN, accuracy)</accuracy>
          <tidalDisplacement><earthTide><inputfileEarthtide>{D}/tides/earthAnelastic2003.xml</inputfileEarthtide></earthTide></tidalDisplacement>
          <tidalDisplacement><doodsonHarmonicTide>
            <inputfileTides>{D}/tides/oceanTide_fes2014b_n180_version20170520.dat</inputfileTides>
            <inputfileAdmittance>{D}/tides/oceanTide_fes2014b_admittance_linear_linear.txt</inputfileAdmittance>
            <minDegree>1</minDegree>
          </doodsonHarmonicTide></tidalDisplacement>
          <tidalDisplacement><poleTide><inputfileMeanPole>{D}/tides/secularPole2018.xml</inputfileMeanPole></poleTide></tidalDisplacement>
          <tidalDisplacement><oceanPoleTide>
            <inputfileOceanPole>{D}/tides/oceanPoleTide_desai2004.dat</inputfileOceanPole>
            <inputfileMeanPole>{D}/tides/secularPole2018.xml</inputfileMeanPole>
          </oceanPoleTide></tidalDisplacement>
          {eph}
          <inputfileDeformationLoadLoveNumber>{D}/loading/deformationLoveNumbers_CM_Gegout97.txt</inputfileDeformationLoadLoveNumber>
          <inputfilePotentialLoadLoveNumber>{D}/loading/loadLoveNumbers_Gegout97.txt</inputfilePotentialLoadLoveNumber>
          <elevationCutOff>5</elevationCutOff>
          <interpolationDegree>7</interpolationDegree>
        </stations>
      </station>
      {eop}
      <parametrization>
        <troposphere>
          <name>parameter.troposphere</name>
          <selectStations><all/></selectStations>
          <troposphere><mendesAndPavlis><inputfileStationMeteorology>{np_dir}/meteorological_{{station}}.dat</inputfileStationMeteorology></mendesAndPavlis></troposphere>
        </troposphere>
      </parametrization>
      <processingStep>
        <estimate>
          <computeResiduals>1</computeResiduals>
          <adjustSigma0>0</adjustSigma0>
          <computeWeights>0</computeWeights>
          <maxIterationCount>1</maxIterationCount>
        </estimate>
      </processingStep>
      <processingStep>
        <writeResiduals>
          <selectStations><all/></selectStations>
          <selectSatellites><all/></selectSatellites>
          <outputfileResiduals>residuals/{day}/residuals_{{station}}.{{satellite}}.txt</outputfileResiduals>
        </writeResiduals>
      </processingStep>
      <processingStep><printResidualStatistics/></processingStep>
    </SlrProcessing>
  </program>""")


def read_residuals(path):
    """Rows of a GROOPS SATELLITELASERRANGING text file: MJD, residual (data0) [m], ..., elevation (data6)."""
    rows = []
    for ln in Path(path).read_text().splitlines():
        p = ln.split()
        if len(p) >= 8 and not ln.lstrip().startswith("#"):
            try:
                v = [float(x) for x in p[:8]]
            except ValueError:
                continue
            if v[0] > 40000:
                rows.append(v)
    return np.array(rows).reshape(-1, 8)


# ---------------- 4. driver + plots ----------------

def run(session, methods, out_dir, data_dir, exe):
    session, out_dir = Path(session), Path(out_dir)
    slr_dir = session / "SLR"
    info, pos, src = make_satellite_info(slr_dir, exe, data_dir)
    lines = ["", "=== SLR residuals, observed - computed (cm), orbit fixed ===",
             f"LRR position [m]: {pos[0]:.4f} {pos[1]:.4f} {pos[2]:.4f}  (source: {src})",
             f"LRR range correction [m]: {config.LRR_RANGE_CORRECTION} (NOT SOURCED)",
             f"{'day':10} {'opt':3} {'NP':>4} {'stations':>8} {'mean':>7} {'RMS':>7} {'median|r|':>9}"]
    res = {}
    for day in config.DAYS:
        np_dir = convert_normal_points(slr_dir, day, data_dir, exe)
        for m in methods:
            rd = slr_dir / m
            if not (rd / f"{run_groops.OK}_{day}").is_file():
                rd.mkdir(parents=True, exist_ok=True)
                name = f"slrProcessing_{day}.xml"
                _write(rd / name, slr_script(session / m, day, np_dir, info, slr_dir, data_dir))
                run_groops.run_scripts(rd, [name], data_dir, exe)
                (rd / f"{run_groops.OK}_{day}").write_text("done\n")
            files = sorted((rd / "residuals" / day).glob("residuals_*.txt"))
            per = [(f.name.split("_", 1)[1].split(".")[0], read_residuals(f)) for f in files]
            per = [(s, a) for s, a in per if len(a)]
            res[(day, m)] = per
            r = np.concatenate([a[:, 1] for _, a in per]) * 100 if per else np.array([])
            if len(r):
                lines.append(f"{day:10} {m:3} {len(r):4d} {len(per):8d} {r.mean():7.2f} "
                             f"{np.sqrt((r**2).mean()):7.2f} {np.median(np.abs(r)):9.2f}")
            else:
                lines.append(f"{day:10} {m:3}    0  no residuals written (see {rd}/log)")
    lines.append("per station, all days: station NP RMS[cm] for each option")
    for m in methods:
        by_station = {}
        for (day, mm), per in res.items():
            if mm == m:
                for s, a in per:
                    by_station.setdefault(s, []).append(a[:, 1] * 100)
        lines.append(f"  {m}: " + ", ".join(
            f"{s} {len(np.concatenate(v))} {np.sqrt((np.concatenate(v) ** 2).mean()):.1f}"
            for s, v in sorted(by_station.items())))
    _plot(res, methods, out_dir)
    return lines


def _plot(res, methods, out_dir):
    for day in config.DAYS:
        fig, axes = plt.subplots(1, len(methods), figsize=(4.2 * len(methods), 3.6), sharey=True, squeeze=False)
        allr = [a[:, 1] * 100 for m in methods for _, a in res.get((day, m), [])]
        lim = max(np.percentile(np.abs(np.concatenate(allr)), 99) * 1.2, 1.0) if allr else 10
        for c, m in enumerate(methods):
            ax = axes[0, c]
            per = res.get((day, m), [])
            n = 0
            for s, a in per:
                h = (a[:, 0] - np.floor(a[0, 0])) * 24
                ax.plot(h, a[:, 1] * 100, "o", ms=3.5, color=COLORS[m], alpha=0.8)
                n += len(a)
            r = np.concatenate([a[:, 1] for _, a in per]) * 100 if per else np.array([])
            txt = f"RMS {np.sqrt((r**2).mean()):.2f} cm, {n} NP, {len(per)} stations" if n else "no residuals"
            ax.axhline(0, color=MUTED, lw=0.8)
            ax.set_ylim(-lim, lim)
            ax.set_xlim(0, 24)
            ax.set_title(f"{m}: {METHODS[m]}\n{txt}", color=INK, fontsize=9, loc="left")
            ax.set_xlabel("Hours of day", color=INK)
            ax.grid(color=GRID, lw=0.8)
            ax.tick_params(colors=MUTED, labelsize=8)
            for sp in ax.spines.values():
                sp.set_color(GRID)
        axes[0, 0].set_ylabel("SLR residual [cm]", color=INK)
        fig.suptitle(f"GRACE-FO C {day}: SLR residuals (observed - computed), orbit fixed",
                     color=INK, x=0.01, ha="left")
        fig.tight_layout()
        fig.savefig(Path(out_dir) / f"slr_residuals_{day}.png", dpi=150)
        plt.close(fig)
