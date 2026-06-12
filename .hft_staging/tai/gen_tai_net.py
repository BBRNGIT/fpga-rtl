#!/usr/bin/env python3
"""gen_tai_net.py — EMITTER: writes tai.net.json.

Emits the netlist for the authoritative TAI timestamp counter. tai is CLOCKED BY
taisoc: one taisoc edge == one tai tick == TAI_NS += 1. In the flip-flop model it
is a free-running counter (the taisoc edge is its clock); NO discipline, NO PPS,
NO PI loop (settled law). Structure mirrors taisoc/mac/internal but with NO edge
output (the consumer tai_cdc samples the VALUE, not an edge). gennet.py generates
the device C; the device tick is never hand-written.
"""
import json

NET = {
    "device": "tai",
    "kind": "counter",
    "comment": (
        "tai — the authoritative TAI timestamp. A 64-bit counter CLOCKED BY taisoc "
        "(one taisoc edge = one tick = TAI_NS += 1). NO discipline/PPS/PI loop: "
        "taisoc is the reference by definition. The timestamp VALUE (separate clock "
        "from MAC the sample RATE). tai_cdc samples TAI_NS into the MAC domain."
    ),

    "config_nodes": [
        {"name": "TAI_POWER", "type": "bit",
         "comment": "power bit: counter runs on the taisoc clock while bit0 = 1 (set once)"},
        {"name": "TAI_RUN_UNTIL", "type": "u64",
         "comment": "configured self-run stop count (set once by starter)"}
    ],

    "dff_nodes": [
        {"name": "TAI_NS", "type": "u64",
         "comment": "authoritative 64-bit timestamp; += 1 per taisoc edge"}
    ],

    "counter": {"reg": "TAI_NS", "power": "TAI_POWER"},
    # no "edge": the consumer (tai_cdc) samples the counter VALUE, not a strobe.
    "run_power": "TAI_POWER",
    "run_bound": {"count": "TAI_NS", "limit": "TAI_RUN_UNTIL"}
}


def main():
    with open("tai.net.json", "w") as f:
        json.dump(NET, f, indent=2)
        f.write("\n")
    print("emitted tai.net.json")


if __name__ == "__main__":
    main()
