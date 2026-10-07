"""Get the GROOPS executable: clone the pinned release and build it (Linux/macOS/WSL).

Build follows the Ubuntu steps in GROOPS INSTALL.md. zlib is required here because the
scenario scripts read .gz product files directly.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path                                         # CHANGED

import config

SRC = Path.home() / "groops_build" / "groops"                  # CHANGED: Linux home, not work/ (git cannot chmod on Windows drives /mnt/*)
INSTALL = Path.home() / "groops_build" / "groops_install"      # CHANGED
EXE = INSTALL / "bin" / "groops"


def _run(cmd, cwd=None):
    print("[build] " + " ".join(map(str, cmd)))
    subprocess.run(cmd, cwd=cwd, check=True)


def get_groops(groops_bin=None):
    """Return path to a GROOPS executable. groops_bin: use an existing one instead of building."""
    if groops_bin:
        if not shutil.which(str(groops_bin)) and not os.path.isfile(groops_bin):
            sys.exit(f"[build] GROOPS executable not found: {groops_bin}")
        return str(groops_bin)
    if EXE.is_file():
        return str(EXE)
    for tool in ("git", "cmake", "make", "g++", "gfortran"):
        if not shutil.which(tool):
            sys.exit(f"[build] '{tool}' not found. Ubuntu: sudo apt-get install g++ gfortran cmake "
                     "libexpat1-dev libopenblas-dev zlib1g-dev")
    if not SRC.exists():
        SRC.parent.mkdir(parents=True, exist_ok=True)              # CHANGED
        _run(["git", "clone", "--depth", "1", "--branch", config.GROOPS_TAG, config.GROOPS_GIT, str(SRC)])
    build = SRC / "source" / "build"
    build.mkdir(exist_ok=True)
    _run(["cmake", "..", "-DCMAKE_BUILD_TYPE=Release", f"-DCMAKE_INSTALL_PREFIX={INSTALL}"], cwd=build)
    cache = (build / "CMakeCache.txt").read_text()
    if "LIB_Z:FILEPATH=LIB_Z-NOTFOUND" in cache or "LIB_Z:FILEPATH=" not in cache:
        sys.exit("[build] zlib not found; GROOPS could not read the .gz products. "
                 "Ubuntu: sudo apt-get install zlib1g-dev, then delete ~/groops_build/groops/source/build")
    _run(["make", f"-j{os.cpu_count() or 2}"], cwd=build)
    _run(["make", "install"], cwd=build)
    return str(EXE)


if __name__ == "__main__":
    print(get_groops())
