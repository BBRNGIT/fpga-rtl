#!/usr/bin/env python3
"""gen_fpga_main_net.py — fpga-main blank emitter (thin wrapper over the meta tool
../gen_fpga_blank.py on ../device_profiles/fpga-main.yaml). Output is a TOOL artifact.
    python3 gen_fpga_main_net.py > fpga_main.net.json
"""
import os, runpy, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.argv = [os.path.join(HERE, "..", "gen_fpga_blank.py"),
            os.path.join(HERE, "..", "device_profiles", "fpga-main.yaml")]
runpy.run_path(sys.argv[0], run_name="__main__")
