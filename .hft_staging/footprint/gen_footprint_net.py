#!/usr/bin/env python3
"""gen_footprint_net.py — footprint's netlist emitter (thin wrapper).

The real emitter is the GENERIC meta-tool ../gen_module_net.py. This wrapper runs
it on footprint_logic.yaml so the per-component flow
(`python3 gen_footprint_net.py > footprint.net.json`) is preserved and clean-room
reproducible. The netlist is a TOOL OUTPUT — never hand-edited.

    python3 gen_footprint_net.py > footprint.net.json
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GENERIC = os.path.join(HERE, "..", "gen_module_net.py")
LOGIC = os.path.join(HERE, "footprint_logic.yaml")


def main():
    sys.argv = [GENERIC, LOGIC]
    runpy.run_path(GENERIC, run_name="__main__")


if __name__ == "__main__":
    main()
