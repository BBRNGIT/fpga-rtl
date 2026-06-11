#!/usr/bin/env python3
"""gen_candle_net.py — candle's netlist emitter (thin wrapper).

The real emitter is the GENERIC meta-tool ../gen_module_net.py. This wrapper
just runs it on candle_logic.yaml so the per-component build flow
(`python3 gen_candle_net.py > candle.net.json`) is preserved and clean-room
reproducible. The netlist (candle.net.json) is a TOOL OUTPUT — never hand-edited.

    python3 gen_candle_net.py > candle.net.json
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GENERIC = os.path.join(HERE, "..", "gen_module_net.py")
LOGIC = os.path.join(HERE, "candle_logic.yaml")


def main():
    # Invoke the generic emitter exactly as the CLI would; it writes the netlist
    # JSON to stdout (which the Makefile redirects into candle.net.json).
    sys.argv = [GENERIC, LOGIC]
    runpy.run_path(GENERIC, run_name="__main__")


if __name__ == "__main__":
    main()
