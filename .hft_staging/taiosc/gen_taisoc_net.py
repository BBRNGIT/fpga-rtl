#!/usr/bin/env python3
"""gen_taisoc_net.py — EMITTER: writes taisoc.net.json.

This python file is the real deliverable (DESIGN_GUIDE step 3): it emits the
netlist describing the taisoc oscillator-reference clock as addressed register
nodes wired as cells — branchless. gennet.py then GENERATES the device C from
this netlist; the device tick is never hand-written.

taisoc is a free-running counter (the TAI rate reference) that emits one edge
strobe per powered tick. Structure: a power input lane, a 64-bit counter dff,
and a 1-bit edge dff. The increment is the structural cell_addsub adder.
"""
import json

NET = {
    "device": "taisoc",
    "window_base": "0x1B00000",
    "kind": "oscillator",
    "comment": (
        "taisoc — the TAI oscillator REFERENCE. A free-running counter (the TAI "
        "rate) that emits one edge strobe per powered tick. No discipline, no "
        "timestamp value: it only produces the rate. tai counts TAISOC_EDGE. "
        "Separate oscillator from MAC and internal (CLAUDE.md two-clock model)."
    ),

    # --- input lanes (driven from outside the netlist: set by the starter). ---
    "config_nodes": [
        {"name": "TAISOC_POWER", "type": "bit",
         "comment": "power bit: counter self-runs while bit0 = 1 (set once by starter)"},
        {"name": "TAISOC_RUN_UNTIL", "type": "u64",
         "comment": "configured stop count: self-run bound (set once by starter; the "
                    "clock self-oscillates while CYCLE < this, like the adapter's buffer bound)"}
    ],

    # --- registered outputs (the device's sole writes). -----------------------
    "dff_nodes": [
        {"name": "TAISOC_CYCLE", "type": "u64",
         "comment": "free-running cycle count; += 1 per powered tick"},
        {"name": "TAISOC_EDGE", "type": "bit",
         "comment": "oscillator edge strobe: 1 every powered tick (tai counts this)"}
    ],

    # --- the counter spec: which dff is the counter, gated by which power bit. -
    "counter": {
        "reg": "TAISOC_CYCLE",   # the counter register (incremented)
        "power": "TAISOC_POWER"  # advance only while this bit is set
    },

    # --- the edge strobe: high whenever powered (1:1 with the oscillator). -----
    "edge": {
        "reg": "TAISOC_EDGE",
        "power": "TAISOC_POWER"
    },

    # --- the free-running loop runs while this power bit is set. ---------------
    "run_power": "TAISOC_POWER",

    # --- bounded self-run: oscillate while CYCLE < RUN_UNTIL (configured stop). -
    "run_bound": {"count": "TAISOC_CYCLE", "limit": "TAISOC_RUN_UNTIL"}
}


def main():
    with open("taisoc.net.json", "w") as f:
        json.dump(NET, f, indent=2)
        f.write("\n")
    print("emitted taisoc.net.json")


if __name__ == "__main__":
    main()
