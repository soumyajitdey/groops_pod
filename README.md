# LEO POD with GROOPS (TU Graz scripts, one folder per mission)

All processing is done by the GROOPS executable (release `2025-11-15`). The Python code downloads
inputs, writes TU Graz's XML scripts with the minimum changes per mission, runs GROOPS, and compares
the results with reference orbits. No GROOPS calculation is reimplemented.

## Options (same for every mission)

| Option | Method | GROOPS scripts |
|---|---|---|
| **A** | Kinematic: one position per epoch, no force model | TU Graz kinematic scenario `01`–`03` |
| **B** | Reduced-dynamic, fitted directly to GPS observations | TU Graz reduced-dynamic scenario `01`–`04` |
| **C** | Reduced-dynamic, fitted to the kinematic positions of A | `01`, `02` + `03groopsKinematicOrbitFit.xml` (generated from TU Graz `03groopsVariational.xml`, `core/script_c.py`) |

Option C script = TU Graz `03groopsVariational.xml` with the fit's input switched to A's kinematic positions and
covariances, plus one added `InstrumentSynchronize` that splits them into the arcs of the variational equations
(required by `PreprocessingVariationalEquationOrbitFit`, GROOPS docs; without it a day with a data gap fails with
"cannot interpolate at ...").

C needs a finished A run: A of the same call, else the latest earlier A run (same mission and
products), else A is run first.

## Run (Ubuntu / WSL, in this folder)

```
python3 run_pipeline.py --mission CHAMP --method all                    # A, B, C + validation
python3 run_pipeline.py --mission CHAMP --method B --products final     # one option, IGS final products
python3 run_pipeline.py --mission GRACE-FO --method all
python3 validate.py --mission CHAMP                                     # validation only, latest CHAMP results
python3 validate.py --mission CHAMP --results CHAMP_20261003_210000     # validation of one results folder
```

`--mission` = name of a mission folder. `--products repro3|final|ultra` (default `repro3`; GRACE-FO: repro3 only).
`--groops-bin /path/to/groops` uses an existing GROOPS build.

Requirements: Python 3.8+ with numpy, matplotlib, requests
(`sudo apt-get install python3-numpy python3-matplotlib python3-requests`). To build GROOPS:
`sudo apt-get install g++ gfortran cmake libexpat1-dev libopenblas-dev zlib1g-dev`.
CDDIS downloads need an Earthdata login in `~/.netrc` (GFZ ISDC and SOPAC do not)
(`machine urs.earthdata.nasa.gov login <user> password <pass>`).

## Folders

```
run_pipeline.py, validate.py    entry points (mission-independent)
core/                           shared code: downloads, GROOPS build/run, option-C script, comparison, plots
GRACE-FO/mission.py             GRACE-FO C, 2020-01-01/02 (TU Graz scenarios, unchanged)
GRACE-FO/slr_validation.py      SLR residuals (GRACE-FO only)
CHAMP/mission.py                CHAMP, 2010-05-01 .. 05
work/                           downloads, GROOPS data, inputs, results (shared)
```

A new mission = a new folder with `mission.py` (NAME, SATELLITE, DAYS, PRODUCTS, `setup`, `run_files`,
`validate`). No other file changes.

## Output (nothing is overwritten)

Each call creates `work/results/<MISSION>_<YYYYmmdd>_<HHMMSS>/`:

| Folder / file | Content |
|---|---|
| `A/`, `B/`, `C/` | Scripts, GROOPS `log/`, intermediates `data/`, orbits `output/<day>/<sat>_orbit_<day>.txt`. `RUN_OK` = finished (with products used). `C/kinematic_input.txt` names the A run used. |
| `RSO/` (CHAMP), `GNV1B/` (GRACE-FO) | Reference orbit converted by GROOPS into the frame of our orbits. A failed conversion is kept; the next try uses a new folder. |
| `report.txt` | Mission, days, products, GROOPS release, data folder. |
| `validation/<YYYYmmdd_HHMMSS>/` | `orbit_error_vs_<reference>_<day>.png` (radial / along-track / cross-track, one column per option) and `validation_report.txt`. |

## CHAMP: changes to TU Graz's scripts

Generated at run time from the downloaded scenarios (`CHAMP/mission.py`); all other settings unchanged.

| Script | Change | Reason |
|---|---|---|
| all | `gracefo1`/`gracefo` → `champ` | uses TU Graz CHAMP metadata in `data.zip` (`gnss/receiverLowEarthOrbiter/champ/`, `satelliteModel/champ_satelliteModel.xml`) |
| all | dates via `--global timeStart=55317 timeEnd=55322` | XML unchanged |
| 02 | RINEX input: GFZ CH-OG-1-SST (RINEX 2.10), type mapping `02observationTypes.champ.txt` | |
| 02 | `GraceL1b2Orbit` → `Sp3Format2Orbit` (GFZ RSO, satellite `L06`) + `InstrumentConcatenate` (sort, remove duplicate epochs) | RSO = a priori orbit of all options; RSO arcs overlap |
| 02 | `GraceL1b2StarCamera` → `Champ2AccStar` (GFZ CH-OG-2-ACC) | star camera attitude |
| 03/04 | `wavelengthFactor` 0.5 → 1 | CHAMP RINEX header: `WAVELENGTH FACT L1/2 = 1 1` |
| 01, 03/04 | only for `--products final/ultra` (below) | |

Products (`core/gnss_products.py`):

| `--products` | Files | Source | Script changes |
|---|---|---|---|
| `repro3` | TUG repro3 orbit, clock (30 s), attitude (OBX), biases (OSB) | 1. the four TU Graz zips downloaded by hand into `work/downloads/repro3/` (only the needed days are extracted); 2. CDDIS `archive/gnss/products/<week>/repro3/` (Earthdata login); 3. TU Graz repository by HTTP range requests (server does not support them as of 2026-10-04) | none |
| `final` | IGS final orbit (15 min) + clock (30 s) | SOPAC / CDDIS (code from leo-gps-pod) | file names; OBX and OSB conversion disabled; TU Graz simulated GPS attitude enabled; no transmitter biases; `supportsIntegerAmbiguities` 0 |
| `ultra` | IGS ultra-rapid, observed half (file of day+1, 00 h) | CDDIS | as `final`; clocks from the SP3 file (15 min) |

Inputs per day in `work/inputs/CHAMP/champ/`: `CH-OG-1-SST_<day>.rnx`, `ACC_<day>.dat`, `RSO_<day>.sp3`
(RSO arcs of the day's and next day's folder, joined without their `EOF` lines: GROOPS `Sp3Format2Orbit` stops
reading at the first `EOF`, so with them only the first ~14-h arc was used). Existing files are not downloaded again.

## Validation

| Mission | Reference | Note |
|---|---|---|
| GRACE-FO | TU Graz scenario results (A, B) | reproduction check |
| GRACE-FO | JPL GNV1B (A, B, C) | not independent: a priori orbit of B, C |
| GRACE-FO | SLR residuals | needs SLR files (later) |
| CHAMP | GFZ RSO (A, B, C) | not independent: a priori orbit of all options |
| CHAMP | TU Graz published kinematic and reduced-dynamic CHAMP orbits | independent processing by TU Graz |

## Checks done (2026-10-03, without access to GFZ, CDDIS, TU Graz servers)

- GROOPS `2025-11-15` accepts all generated CHAMP scripts (no unknown elements; stops only at missing data).
- With the CHAMP sample files: `RinexObservation2GnssReceiver` gives `C1CG C1WG C2WG L1CG L1WG L2WG S1CG S1WG S2WG`;
  `Champ2AccStar` reads the ACC file; `Sp3Format2Orbit` + `InstrumentConcatenate` removes duplicate RSO epochs.
- RSO reference script accepted by GROOPS (stopped only at the empty test EOP file).
- Range-request reading of a zip tested against a local server.
- Both missions end-to-end (folders, A→C hand-off, validation, plots) with a stand-in GROOPS executable.
- **Not run:** real GROOPS processing, real downloads.

## Open issues

1. **CHAMP observation types (resolved for L1/LP1/SA).** GFZ CH-RINEX-EXT (Köhler 2001): L1 = C/A-channel
   phase (always present) → L1C; LP1 = L1 phase output only when P1 is enabled → L1W; SA = C/A SNR → S1C.
   S1/S2 → S1W/S2W is inferred (document: "as in standard RINEX"). The document also states that LLI and
   anti-spoofing flags are blank in CHAMP RINEX (BlackJack does not provide them), so cycle slips are found
   from the data only. leo-gps-pod combined L1 (C/A phase) with P1/P2 codes.
2. **CH-OG-2-ACC content checked only at run time.** The pipeline stops if the header time reference is
   UTC (`Champ2AccStar` does no UTC→GPS conversion) or if no `att` records exist.
3. **repro3 downloads not tested** on the real servers (CDDIS needs Earthdata login; TU Graz zips are 2.6–46 GB,
   only the needed bytes are read).
4. **final / ultra are weaker than repro3:** IGS final 2010 uses `igs05` antenna model, scripts use repro3
   transmitter metadata (`igsR3`) → mismatch; no satellite phase biases → float ambiguities only;
   simulated GPS attitude; ultra clocks only every 15 min (30-s LEO data need interpolated clocks).
5. **TU Graz GRACE-FO settings kept for CHAMP** (noise models, pulses, force models) except the changes above.
6. **RSO is not an independent check** (a priori of all options). RSO file header states SLR RMS 25 cm.
7. **Time system of TU Graz published CHAMP orbits assumed GPS** (not confirmed from a header).
8. **Overlapping RSO arcs:** the first arc's epoch is kept (`keepFirst`).
9. **No pass/fail threshold** (none published).
10. GRACE-FO items from the previous README (repro3 latency, GROOPS version difference to TU Graz
    references, option C without bias/scale parameters, SLR items) still apply.

## Sources

- GROOPS: Mayer-Gürr et al. 2021, Comput. Geosci. 155, 104864; GROOPS source (release 2025-11-15):
  `sp3Format2Orbit.cpp`, `champ2AccStar.cpp`, `rinexObservation2GnssReceiver.cpp`, `instrumentConcatenate.cpp`, `config.cpp`.
- Kinematic method: Zehentner & Mayer-Gürr 2016, J. Geod. 90:275–286.
- TU Graz LEO orbit processing: Suesser-Rechberger et al. 2022, Adv. Space Res. 69(10):3559–3570.
- TU Graz scenarios `scenarioLeoKinematicOrbit.zip`, `scenarioLeoReducedDynamicOrbit.zip`.
- CHAMP RINEX types: W. Köhler (GFZ), "RINEX format observable extensions for CHAMP SST Data", 26 June 2001
  (op.gfz-potsdam.de/champ/docs_CHAMP/CH-RINEX-EXT.html).
- CHAMP data: GFZ ISDC (CH-OG-1-SST, CH-OG-2-ACC, RSO L06); TU Graz CHAMP orbits:
  ftp.tugraz.at/pub/ITSG/satelliteOrbitProducts/operational/CHAMP/.
- Repro3: TUG repro3 product record, repository.tugraz.at; IGS repro3 at CDDIS.
- Download code for IGS / CHAMP: github.com/soumyajitdey/leo-gps-pod (`champ_download.py`, commit 3ba6bf3).
