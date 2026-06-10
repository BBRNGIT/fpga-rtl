#!/usr/bin/env python3
"""gen_mac_net.py — EMITTER: writes mac.net.json.

Emits the netlist for the 125 MHz MAC sample clock: a free-running counter (the
NIC sample RATE) that emits one edge strobe per powered tick. The NIC samples on
MAC_EDGE. Structure mirrors taisoc (oscillator family). gennet.py generates the
device C from this netlist; the device tick is never hand-written.
"""
import json

NET = {
    "device": "mac",
    "window_base": "0x1D00000",
    "kind": "oscillator",
    "comment": (
        "mac — the 125 MHz MAC sample clock. A free-running counter (the NIC "
        "sample/copy RATE) emitting one edge strobe per powered tick. MAC = the "
        "sample RATE, a SEPARATE clock from TAI (the timestamp VALUE) and from "
        "internal (the pipeline metronome). The NIC samples on MAC_EDGE."
    ),

    "config_nodes": [
        {"name": "MAC_POWER", "type": "bit",
         "comment": "power bit: counter self-runs while bit0 = 1 (set once by starter)"},
        {"name": "MAC_RUN_UNTIL", "type": "u64",
         "comment": "configured self-run stop count (set once by starter)"}
    ],

    "dff_nodes": [
        {"name": "MAC_CYCLE", "type": "u64",
         "comment": "free-running 125 MHz cycle count; += 1 per powered tick"},
        {"name": "MAC_EDGE", "type": "bit",
         "comment": "MAC sample edge: 1 every powered tick (the NIC samples on it)"}
    ],

    "counter": {"reg": "MAC_CYCLE", "power": "MAC_POWER"},
    "edge": {"reg": "MAC_EDGE", "power": "MAC_POWER"},
    "run_power": "MAC_POWER",
    "run_bound": {"count": "MAC_CYCLE", "limit": "MAC_RUN_UNTIL"}
}


def main():
    with open("mac.net.json", "w") as f:
        json.dump(NET, f, indent=2)
        f.write("\n")
    print("emitted mac.net.json")


if __name__ == "__main__":
    main()
