#!/usr/bin/env python3
"""
assemble.py — DEPRECATED entry point; delegates to integrate.py.

Historically assemble.py built library.json from primitives.json + templates.py ONLY,
ignoring blocks/*.json. integrate.py is the strict superset: it folds in blocks/*.json,
validates the whole library via netc, and cross-checks ports vs the PDF (specgen). Having
two emitters write the same device/library.json caused a silent-drop drift hazard — if
assemble.py ran AFTER integrate.py it would overwrite library.json without the blocks/*.json
blocks. (M3, Inspector audit.)

To kill the drift while preserving this entry point (docstrings / realize.py still name
"assemble -> library.json"), assemble.py now simply DELEGATES to integrate.py. There is one
emitter of library.json. Library generation is deterministic and order-independent: running
assemble.py and integrate.py in any order yields the same library.json.

Edit blocks via templates.py (decomposition builders) or blocks/*.json (extracted blocks),
never library.json by hand. Usage: assemble.py [--check]   Exit codes from integrate.run().
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import integrate

if __name__ == "__main__":
    print("assemble: delegating to integrate.py (single library.json emitter)")
    sys.exit(integrate.run("--check" in sys.argv))
