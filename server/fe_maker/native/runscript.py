"""`python runscript.py script.py args...` runs script.py as `python script.py args...` would, its folder first in
sys.path. The native build's $(PYTHON) (make_command): the Python of FE Maker's Windows installer is the embeddable
one, whose ._pth file leaves the script's folder out of sys.path, so a decomp script importing its neighbour
(scripts/gfxtools/tsa_generator.py: `from tsa2 import ...`) failed there (ticket 82).
"""

import os
import runpy
import sys

if __name__ == "__main__":
    script = sys.argv[1]
    sys.argv = sys.argv[1:]
    sys.path.insert(0, os.path.dirname(os.path.abspath(script)))
    runpy.run_path(script, run_name="__main__")
