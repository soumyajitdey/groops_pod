"""Generate the two XML scripts that are not shipped by TU Graz, from TU Graz's own scripts.

1. Option C script (03groopsKinematicOrbitFit.xml), from 03groopsVariational.xml of the
   reduced-dynamic scenario. Program 1 (PreprocessingVariationalEquation: force-model integration)
   is kept unchanged. Program 2 (PreprocessingVariationalEquationOrbitFit) is kept with all its
   settings (20-min stochastic pulses, degrees, iterations); only its observations change:
     inputfileOrbit              GNV1B orbit  -> kinematic positions of option A
     inputfileCovariancePodEpoch (new)        -> 3x3 epoch covariances of option A
     outputfileOrbit             (new)        -> output/<day>/gracefo1_orbit_<day>.txt
     outputfileVariational       renamed so it does not overwrite the program-1 file
2. GNV1B reference script (gnv1bReference.xml), from 02groopsConvertGracefo.xml: only the
   GraceL1b2Orbit program, writing a text file. This puts the published GNV1B orbit (Earth-fixed)
   into the same frame and time scale as the GROOPS outputs, using the same GROOPS program and
   Earth-rotation settings as the scenario.
"""
import xml.etree.ElementTree as ET

DAY = "{loopTime:%D}"


def _programs(loop):
    return [p for p in loop.findall("program")]


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


def make_script_c(tug_variational_xml, out_path):
    tree = ET.parse(tug_variational_xml)
    loop = tree.getroot().find("program/LoopPrograms")
    progs = _programs(loop)
    # output folder for the fitted orbit
    ET.SubElement(progs[0].find("FileCreateDirectories"), "directory").text = f"output/{DAY}"
    fit = progs[2].find("PreprocessingVariationalEquationOrbitFit")
    if fit is None:
        raise RuntimeError("PreprocessingVariationalEquationOrbitFit not found in " + str(tug_variational_xml))
    kin = "{kinematicDir}/output/" + DAY + "/gracefo1_"
    _set(fit, "outputfileVariational", f"data/{DAY}/gracefo/gracefo1_variationalKinematicFit_{DAY}.dat")
    _set(fit, "outputfileOrbit", f"output/{DAY}/gracefo1_orbit_{DAY}.txt", after="outputfileVariational")
    _set(fit, "inputfileOrbit", kin + f"orbit_{DAY}.txt")
    _set(fit, "inputfileCovariancePodEpoch", kin + f"covarianceEpoch3x3_{DAY}.txt", after="inputfileOrbit")
    progs[2].set("comment", f"output/{DAY}/gracefo1_orbit_{DAY}.txt (option C: fit to kinematic positions)")
    tree.write(out_path, encoding="UTF-8", xml_declaration=True)


def make_script_gnv1b(tug_convert_gracefo_xml, out_path):
    tree = ET.parse(tug_convert_gracefo_xml)
    loop = tree.getroot().find("program/LoopPrograms")
    for p in _programs(loop):
        if p.find("GraceL1b2Orbit") is None and p.find("FileCreateDirectories") is None:
            loop.remove(p)
    for p in _programs(loop):
        if p.find("FileCreateDirectories") is not None:
            p.find("FileCreateDirectories/directory").text = f"output/{DAY}"
        else:
            p.find("GraceL1b2Orbit/outputfileOrbit").text = f"output/{DAY}/gracefo1_gnv1b_{DAY}.txt"
    tree.write(out_path, encoding="UTF-8", xml_declaration=True)
