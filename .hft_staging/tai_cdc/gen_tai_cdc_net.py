#!/usr/bin/env python3
"""gen_tai_cdc_net.py — EMITTER: writes tai_cdc.net.json.

Emits the netlist for the TAI clock-domain-crossing: a gray-code 2-FF
synchronizer (Cummings) that brings the TAI counter VALUE from the taisoc/tai
domain into the MAC domain, metastability-safe. The NIC stamps packets with the
MAC-domain output (TAI_MAC), never the raw cross-domain counter.

Whole-word cells (not per-bit nodes): gray encode is in ^ (in>>1); the two sync
stages are gated dffs; gray decode is an XOR fold. gennet.py generates the device
C; the device tick is never hand-written.
"""
import json

NET = {
    "device": "tai_cdc",
    "window_base": "0x1F00000",
    "kind": "cdc",
    "comment": (
        "tai_cdc — gray-code 2-FF synchronizer (Cummings) bringing the TAI value "
        "from the taisoc/tai domain into the MAC domain, metastability-safe. The "
        "NIC stamps with TAI_MAC (MAC-domain), never raw cross-domain TAI. No "
        "discipline anywhere in the clock set: taiosc is the reference by definition."
    ),

    # --- input lanes (driven from outside the netlist: set by the starter). ---
    # TAI_IN is the SAMPLED tai value: at integration the tai counter's value is
    # presented here (the source-domain sample the synchronizer carries across).
    # It is config to this device (module-barrier law: tai_cdc does not reach into
    # tai's registers; the value is presented on tai_cdc's own input lane).
    "config_nodes": [
        {"name": "TAI_CDC_POWER", "type": "bit",
         "comment": "power/enable bit: sync runs on the MAC edge while bit0 = 1 (set once)"},
        {"name": "TAI_CDC_RUN_UNTIL", "type": "u64",
         "comment": "configured self-run tick budget (set once by starter)"},
        {"name": "TAI_IN", "type": "u64",
         "comment": "sampled tai value presented on tai_cdc's input lane (source-domain "
                    "sample; module-barrier: not a raw read of tai's registers)"}
    ],

    # --- registered + combinational outputs (the device's writes). ------------
    "dff_nodes": [
        {"name": "TAI_CDC_TICKS", "type": "u64",
         "comment": "self-run tick counter (run-loop bookkeeping; bounds the self-run)"},
        {"name": "TAI_SYNC1_GRAY", "type": "u64",
         "comment": "stage-1 sync FF (gray-coded; catches the metastability window)"},
        {"name": "TAI_SYNC2_GRAY", "type": "u64",
         "comment": "stage-2 sync FF (gray-coded; metastability-safe, stable)"}
    ],
    "comb_nodes": [
        {"name": "TAI_MAC", "type": "u64",
         "comment": "gray-decoded stage-2 output: the MAC-domain TAI value (NIC reads this)"}
    ],

    # --- the CDC wiring the gennet consumes. ----------------------------------
    "source": "TAI_IN",
    "power": "TAI_CDC_POWER",
    "encode": {"in": "TAI_IN", "out": "TAI_GRAY"},     # TAI_GRAY is an internal comb temp
    "sync1": {"reg": "TAI_SYNC1_GRAY", "from": "TAI_GRAY"},
    "sync2": {"reg": "TAI_SYNC2_GRAY", "from": "TAI_SYNC1_GRAY"},
    "decode": {"in": "TAI_SYNC2_GRAY", "out": "TAI_MAC"},
    "run": {"power": "TAI_CDC_POWER", "count": "TAI_CDC_TICKS", "limit": "TAI_CDC_RUN_UNTIL"}
}


def main():
    with open("tai_cdc.net.json", "w") as f:
        json.dump(NET, f, indent=2)
        f.write("\n")
    print("emitted tai_cdc.net.json")


if __name__ == "__main__":
    main()
