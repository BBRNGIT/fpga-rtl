#!/usr/bin/env python3
"""gen_internal_net.py — EMITTER: writes internal.net.json.

Emits the netlist for the 250 MHz pipeline metronome: a free-running counter
emitting one edge strobe per powered tick. Structure mirrors taiosc/mac
(oscillator family). gennet.py generates the device C; the device tick is
never hand-written.
"""
import json

NET = {
    "device": "internal",
    "window_base": "0x1E00000",
    "kind": "oscillator",
    "comment": (
        "internal — the 250 MHz pipeline metronome. A free-running counter "
        "emitting one edge strobe per powered tick; pipeline modules fire on "
        "INTERNAL_EDGE. A SEPARATE oscillator from MAC (125 MHz) and from the "
        "TAI timebase. Same-domain reads need no CDC."
    ),

    "config_nodes": [
        {"name": "INTERNAL_POWER", "type": "bit",
         "comment": "power bit: counter self-runs while bit0 = 1 (set once by starter)"},
        {"name": "INTERNAL_RUN_UNTIL", "type": "u64",
         "comment": "configured self-run stop count (set once by starter)"}
    ],

    "dff_nodes": [
        {"name": "INTERNAL_CYCLE", "type": "u64",
         "comment": "free-running 250 MHz cycle count; += 1 per powered tick"},
        {"name": "INTERNAL_EDGE", "type": "bit",
         "comment": "pipeline metronome edge: 1 every powered tick"}
    ],

    "counter": {"reg": "INTERNAL_CYCLE", "power": "INTERNAL_POWER"},
    "edge": {"reg": "INTERNAL_EDGE", "power": "INTERNAL_POWER"},
    "run_power": "INTERNAL_POWER",
    "run_bound": {"count": "INTERNAL_CYCLE", "limit": "INTERNAL_RUN_UNTIL"}
}


def main():
    with open("internal.net.json", "w") as f:
        json.dump(NET, f, indent=2)
        f.write("\n")
    print("emitted internal.net.json")


if __name__ == "__main__":
    main()
