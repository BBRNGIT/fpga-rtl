#!/usr/bin/env python3
"""gen_dom_bus_net.py — dom_bus netlist emitter (thin wrapper over the generic
meta-tool ../gen_module_net.py on dom_bus_logic.yaml). Output is a TOOL artifact.
    python3 gen_dom_bus_net.py > dom_bus.net.json
"""
import os, runpy, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.argv = [os.path.join(HERE, "..", "gen_module_net.py"), os.path.join(HERE, "dom_bus_logic.yaml")]
runpy.run_path(sys.argv[0], run_name="__main__")
