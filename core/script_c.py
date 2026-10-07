"""Option C script, generated from a variational-equation script of TU Graz (mission-independent).

Input: 03groopsVariational.xml of the TU Graz reduced-dynamic scenario (for other missions, the
mission's copy of it). Program 1 (PreprocessingVariationalEquation: force-model integration) is kept
unchanged. Program 2 (PreprocessingVariationalEquationOrbitFit) is kept with all its settings
(20-min stochastic pulses, degrees, iterations); only its observations change:
  inputfileOrbit              a priori orbit -> kinematic positions of option A
  inputfileCovariancePodEpoch (new)          -> 3x3 epoch covariances of option A
  outputfileOrbit             (new)          -> output/<day>/<sat>_orbit_<day>.txt
  outputfileVariational       renamed so it does not overwrite the program-1 file
Added before program 2 (CHANGED 2026-10-04): InstrumentSynchronize that splits the kinematic positions
and covariances into the arcs of the variational equations (arcs of the program-1 a priori orbit).
GROOPS docs of PreprocessingVariationalEquationOrbitFit: the observed orbit "must be splitted in the same
arcs as the variational equations ... (use irregularData in InstrumentSynchronize)". Without it, a day
with more than one arc (data gap) fails with "cannot interpolate at <time>".
"""
import xml.etree.ElementTree as ET

DAY = "{loopTime:%D}"


def _set(parent, tag, text, after=None):
    """Set child text; create the child (after element `after`) if missing."""
    el = parent.find(tag)
    if el is None:
        el = ET.Element(tag)
        kids = list(parent)
        idx = kids.index(parent.find(after)) + 1 if after is not None and parent.find(after) is not None else len(kids)
        parent.insert(idx, el)
    el.text = text
    return el


def make_script_c(variational_xml_text, sat):
    """Return the option-C XML text. sat = file prefix used by the mission scripts (e.g. gracefo1, champ)."""
    root = ET.fromstring(variational_xml_text)
    loop = root.find("program/LoopPrograms")
    progs = loop.findall("program")
    ET.SubElement(progs[0].find("FileCreateDirectories"), "directory").text = f"output/{DAY}"
    fit = progs[2].find("PreprocessingVariationalEquationOrbitFit")
    if fit is None:
        raise RuntimeError("PreprocessingVariationalEquationOrbitFit not found in the variational script")
    kin = "{kinematicDir}/output/" + DAY + f"/{sat}_"
    data = f"data/{DAY}/{sat_dir(variational_xml_text)}/{sat}_"
    _set(fit, "outputfileVariational", data + f"variationalKinematicFit_{DAY}.dat")
    _set(fit, "outputfileOrbit", f"output/{DAY}/{sat}_orbit_{DAY}.txt", after="outputfileVariational")
    _set(fit, "inputfileOrbit", data + f"orbitKinematicArcs_{DAY}.dat")                          # CHANGED: arc-split copy
    _set(fit, "inputfileCovariancePodEpoch", data + f"covarianceKinematicArcs_{DAY}.dat", after="inputfileOrbit")  # CHANGED
    apriori = progs[1].find("PreprocessingVariationalEquation/inputfileOrbit").text              # CHANGED: arcs of the
    sync = ET.fromstring(f"""<program comment="option C: kinematic positions split into the arcs of the variational equations">
<InstrumentSynchronize>
<data><inputfileInstrument>{apriori}</inputfileInstrument></data>
<margin>1e-5</margin>
<minArcLength>1</minArcLength>
<irregularData><outputfileInstrument>{data}orbitKinematicArcs_{DAY}.dat</outputfileInstrument><inputfileInstrument>{kin}orbit_{DAY}.txt</inputfileInstrument></irregularData>
<irregularData><outputfileInstrument>{data}covarianceKinematicArcs_{DAY}.dat</outputfileInstrument><inputfileInstrument>{kin}covarianceEpoch3x3_{DAY}.txt</inputfileInstrument></irregularData>
</InstrumentSynchronize>
</program>""")                                                                                    # CHANGED: variational eq.
    loop.insert(list(loop).index(progs[2]), sync)                                                 # CHANGED
    progs[2].set("comment", f"output/{DAY}/{sat}_orbit_{DAY}.txt (option C: fit to kinematic positions)")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


def sat_dir(variational_xml_text):
    """Mission data folder used by the script (first FileCreateDirectories entry: data/{day}/<folder>)."""
    root = ET.fromstring(variational_xml_text)
    d = root.find("program/LoopPrograms/program/FileCreateDirectories/directory").text
    return d.rstrip("/").split("/")[-1]
