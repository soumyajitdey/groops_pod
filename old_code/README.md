# GRACE-FO POD with GROOPS (TU Graz scenarios, run as end users)

Step 1 of the CHAMP plan: reproduce TU Graz's GRACE-FO orbits with GROOPS, in three options,
and validate them. CHAMP comes next.

**What this code does NOT do:** it does not reimplement any GROOPS calculation. All processing is
done by the GROOPS executable. TU Graz's XML scripts are used unchanged; the one script TU Graz
does not provide (option C) is generated from their own script with only its inputs/outputs switched.

## Options

| Option | Method | GROOPS programs | Scripts |
|---|---|---|---|
| **A** | Kinematic: one position per epoch, no force model | `GnssProcessing` + `kinematicPositions` | TU Graz kinematic scenario, unchanged |
| **B** | Reduced-dynamic, fitted directly to GPS observations | `PreprocessingVariationalEquation`, `GnssProcessing` + `leoDynamicOrbits` | TU Graz reduced-dynamic scenario, unchanged |
| **C** | Reduced-dynamic, fitted to the kinematic positions of A | `PreprocessingVariationalEquation`, `PreprocessingVariationalEquationOrbitFit` | TU Graz `01`, `02` unchanged + generated `03groopsKinematicOrbitFit.xml` |

Option C script (`script_c.py`) = TU Graz `03groopsVariational.xml` with these edits only:
- `inputfileOrbit`: GNV1B orbit → option-A kinematic positions
- `inputfileCovariancePodEpoch` (added): option-A 3×3 epoch covariances
- `outputfileOrbit` (added): `output/<day>/gracefo1_orbit_<day>.txt`
- `outputfileVariational`: renamed so it does not overwrite the force-model file
- one extra output folder created

Force models, 20-min stochastic pulses, integration/interpolation degrees and iteration count are
TU Graz's settings, unchanged. C needs a finished A run: from the same session, else the latest
earlier one, else A is run first.

## Run

```
python run_pipeline.py --method A        # or B, C
python run_pipeline.py --method all      # validation run: A, B, C, each in its own folder
python run_pipeline.py --method all --groops-bin /path/to/groops   # use an existing GROOPS build
```

Requirements: Python 3.8+ with numpy and matplotlib; to build GROOPS: git, cmake, make, g++, gfortran,
expat, OpenBLAS, zlib. Ubuntu / WSL:
`sudo apt-get install g++ gfortran cmake libexpat1-dev libopenblas-dev zlib1g-dev`.
Windows: run inside WSL, or pass `--groops-bin` to a Windows GROOPS build (MSYS2, see GROOPS INSTALL.md).

## Output (nothing is overwritten)

Each call creates `work/sessions/<YYYYmmdd-HHMMSS>/`:

| Folder / file | Content |
|---|---|
| `A/`, `B/`, `C/` | One run per option: scripts, GROOPS `log/`, intermediates `data/`, results `output/<day>/`. `RUN_OK` marks a finished run. `C/kinematic_input.txt` names the A run it used. |
| `GNV1B/output/` | Published GRACE-FO C orbit (JPL GNV1B) converted by GROOPS `GraceL1b2Orbit` into the same frame and time scale as our orbits (same Earth-rotation settings as the scenario). |
| `report.txt` | POD run info. |
| `validation/<YYYYmmdd-HHMMSS>/` | From `validate.py` (run automatically after the POD, or alone: `python3 validate.py [--session <name>]`): `orbit_error_vs_gnv1b_<day>.png` (radial / along-track / cross-track, one column per option) and `validation_report.txt` (reproduction check vs TU Graz references for A, B; statistics vs GNV1B for A, B, C). |

## Validation

1. **Reproduction (A, B):** ours minus TU Graz's reference results shipped in each scenario's
   `output/`: epoch counts, R/T/N mean and RMS, 3D RMS and max, formal sigma (A), receiver signal biases.
   Option C has no TU Graz reference.
2. **External orbit (A, B, C):** ours minus published GNV1B, with plots and statistics.
   GNV1B is **not independent** of B and C: it is their a priori orbit (force-model integration
   and the starting orbit in B's script `03`). It is the only published orbit available for all three.
3. **SLR residuals (A, B, C)** — independent of GPS (`slr_validation.py`). SLR is used for validation
   only; the POD stays GPS-only. All computation is GROOPS:
   - normal points: EUROLAS Data Center (DGFI-TUM) daily CRD files `gracefo1_YYYYMMDD.npt` → `Crd2NormalPoints`
   - satellite metadata: not in GROOPS `data.zip`, so created with GROOPS `PlatformCreate`: laser
     retroreflector at the JPL VSL1B offset (GRACE-FO L1 handbook Sect. 2.5.6), read from the GFZ ISDC daily
     L1B archive (`..._RL04.ascii.noLRI.tgz`, 140 MB, first day only). Satellite frame origin = CoM within
     0.1 mm (handbook Sect. 3.2.3). Override with `config.LRR_POSITION`.
   - residuals: `SlrProcessing`, orbit fixed, no unknowns, no reweighting; SLRF2020 station positions;
     station tides as documented by GROOPS for station networks (solid Earth, FES2014b loading minDegree 1,
     pole, ocean pole); Mendes & Pavlis troposphere with CRD meteo data; 5° cut-off; no range/time biases
     (GROOPS: ILRS biases only suitable for passive satellites).
   - output: `slr_residuals_<day>.png`, statistics per day/option and per station in `validation_report.txt`.
   - SLR files are created once per session in `<session>/SLR/`. If SLR fails, steps 1–2 are still reported.

## What gets downloaded automatically (into `work/`)

| Item | Source | Contents |
|---|---|---|
| GROOPS source, release `2025-11-15` | github.com/groops-devs/groops | built into `work/groops_install/bin/groops` |
| `data.zip` | ftp.tugraz.at/outgoing/ITSG/groops/ | Earth rotation (EOP), GOCO06s gravity, FES2014b ocean tides, solid Earth tides, DE432 ephemerides, JB2008 + HWM14 thermosphere, CERES albedo / longwave, satellite macro models, GNSS transmitter metadata, LEO receiver metadata |
| both scenario zips | ftp.tugraz.at/outgoing/ITSG/groops/scenario/ | XML scripts, GRACE-FO C L1B (GPS1B RINEX, GNV1B, SCA1B) for 2020-01-01/02, TUG repro3 GPS products, TU Graz reference results |

Nothing that exists is downloaded or extracted again, and nothing is deleted:
- finished downloads are skipped; an interrupted download resumes (HTTP range request)
- only the files the scripts reference are extracted from `data.zip` into `work/groopsData/`;
  files already there (same size) are skipped, including an earlier full unpack
- `data.zip` is only opened if needed files are missing, so it can be deleted once extracted
- GROOPS is built once in `~/groops_build/` (Linux home; git cannot set permissions on Windows drives)

## Files

| File | Step |
|---|---|
| `run_pipeline.py` | One-command runner, `--method A/B/C/all` |
| `download.py` | Downloads and unpacks `data.zip` and both scenarios; skips files already present |
| `build_groops.py` | Clones GROOPS `2025-11-15` and builds it (stops if zlib is missing; scripts read `.gz`) |
| `run_groops.py` | Creates run folders, checks all `{groopsDataDir}` files exist, runs GROOPS with `--global` |
| `script_c.py` | Generates the option-C script and the GNV1B conversion script from TU Graz's scripts |
| `compare.py` | Ours vs TU Graz references |
| `plot_errors.py` | Ours vs GNV1B: plots + statistics |
| `validate.py` | Validation of a finished session (run by `run_pipeline.py`, or alone) |
| `slr_validation.py` | SLR residuals with GROOPS (`PlatformCreate`, `Crd2NormalPoints`, `SlrProcessing`) |
| `groops_io.py` | Readers for GROOPS text outputs |
| `config.py` | URLs, GROOPS release, option definitions. The only file to change for another mission. |

## Checks done while writing this (2026-10-02, without TU Graz server access)

- GROOPS `2025-11-15` builds with `build_groops.py` (zlib found, ERFA not found).
- `--global groopsDataDir=...` overrides the XML value (confirmed from the GROOPS error path).
- `RinexObservation2GnssReceiver` (script 02) reproduces TU Graz's shipped
  `gracefo1_gnssReceiver_2020-01-01.dat` byte-for-byte.
- Generated option-C script: diff against TU Graz's `03groopsVariational.xml` shows only the edits listed above.
- Session handling, folder separation, A→C hand-off, comparison and plots tested with a stand-in
  executable that copies TU Graz's reference outputs.
- **Not run:** GROOPS processing itself (needs `data.zip`; TU Graz server not reachable from the test
  machine). The option-C and GNV1B scripts have therefore not been executed by GROOPS yet.

Reference values: TU Graz kinematic vs their reduced-dynamic reference = 19.3 mm (2020-01-01) and
29.6 mm (2020-01-02) 3D RMS; the 2020-01-02 kinematic reference has epochs up to 1.55 m off.

## Open issues

1. **GPS products are TUG repro3 (to be solved later).** Repro3 is a reanalysis (1994–2020, released
   2022). Fine for GRACE-FO 2020 and CHAMP 2010, but not available in near-real time. The flight
   pipeline needs products with ~3–6 h latency; accuracy with those is not yet assessed.
2. **Exact match not guaranteed.** Reference outputs were written Feb/Apr 2022 by an older GROOPS
   version with the `data.zip` of that time. This pipeline uses GROOPS `2025-11-15` and today's
   `data.zip`. Size of the difference unknown until the first run.
3. **No pass/fail threshold yet.** None is published for these comparisons; to be decided after the first run.
4. **Option C differs from TU Graz's published method.** Suesser-Rechberger et al. 2022 (Sect. 5)
   also estimate constant acceleration bias and scale factors; option C keeps the scenario's settings
   (pulses only). Kinematic outliers (up to 1.55 m in the reference) enter C's fit; whether
   `PreprocessingVariationalEquationOrbitFit` downweights them is not verified.
5. **A priori orbit.** B and C use GNV1B as a priori. For CHAMP this role goes to the GFZ RSO
   (decision 2026-10-02), with no other use of RSO.
6. **Shipped intermediate files differ between scenarios** (GPS attitude files in `data/`, written on
   different dates). Not used here; all intermediates are regenerated. Reason unknown.
7. **ERFA not required.** The scripts use the EOP time-series file for Earth rotation.
8. **SLR — LRR range correction not sourced.** Set to 0 m (`config.LRR_RANGE_CORRECTION`). Which point
   the VSL1B vector refers to (optical centre / invariant point) is not stated in the L1 handbook.
9. **SLR — VSL1B availability not verified.** The handbook calls VSL1B a calibration product "not produced
   on a daily basis"; if the daily archive has no VSL1B, SLR is skipped with a message. The ILRS GRACE-FO
   page lists an LRR reference point (−600, −327.5, +221) mm in "spacecraft coordinates", but its frame
   definition there is unclear, so it is not used automatically.
10. **SLR — settings are ours, not TU Graz's.** No TU Graz SLR scenario exists. Deviations from GROOPS docs:
   FES2014b n180 loading (docs suggest n720), no atmospheric tidal loading (needs AOD1B).
11. **SLR — option A** has no velocities and has gaps; GROOPS interpolates positions (degree 7) to the
   laser epochs.
12. **SLR for CHAMP (later):** 2010 normal points not found yet in EDC's CRD folder (only 2017 listed);
   older formats (CSTG/MERIT) have GROOPS converters. CHAMP LRR position also needed.

## Sources

- GROOPS: Mayer-Gürr et al. 2021, Comput. Geosci. 155, 104864; GROOPS INSTALL.md, README.md, `source/groops.cpp`, `source/config/config.cpp`, `preprocessingVariationalEquationOrbitFit.cpp` (release 2025-11-15).
- Kinematic method: Zehentner & Mayer-Gürr 2016, J. Geod. 90:275–286.
- TU Graz LEO orbit processing (Method C basis): Suesser-Rechberger et al. 2022, Adv. Space Res. 69(10):3559–3570.
- Scenario scripts and READMEs: TU Graz `scenarioLeoKinematicOrbit.zip`, `scenarioLeoReducedDynamicOrbit.zip`.
- GNV1B: GRACE-FO Level-1B product file header (scenario `gracefo/GNV1B_*.txt`).
- SLR: GROOPS `slrProcessing.cpp`, `slrStationGeneratorStations.cpp`, `slrSatellite.h`, `platformCreate.cpp`, `crd2NormalPoints.cpp`, `gnssReceiverGeneratorStationNetwork.h`, `slrParametrizationRangeBiasStationApriori.h`; GRACE-FO Level-1 Data Product User Handbook (2019-09-11) Sects. 2.5.6, 3.2.3; ILRS GRACE-FO mission pages; EDC (DGFI-TUM); Mendes & Pavlis 2004 (as cited in GROOPS, not read).
- Repro3: IGS, "Repro3 Solutions Now Available"; TUG repro3 product record, repository.tugraz.at/records/ddmkp-3bc83.
