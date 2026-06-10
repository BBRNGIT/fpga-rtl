#!/usr/bin/env python3
"""gen_timeframe_net.py — EMITTER: writes timeframe.net.json.

Emits the netlist for the timeframe bar-boundary clock (SPEC_REGISTERS.md §2): a
pure-combinational rollover detector. Each tick it computes elapsed = TAI - BAR_START,
compares elapsed >= PERIOD, and on that boundary increments BAR_SEQ, pulses BAR_CLOSED
for one tick, and re-anchors BAR_START = TAI. All selection is mask algebra; the
subtract/increment are the structural cell_addsub ripple-carry adder; the compare is
the gate-netlist cmp_lt carry chain. No discipline, no master — a guide only.

Module barrier: the spec inputs TIME_TAI_NS_REG and TF_PERIOD_NS_REG are presented on
THIS device's own input lanes (TF_TAI_IN, TF_PERIOD_NS); the device never reaches into
another module's registers (mirrors tai_cdc's TAI_IN). gennet.py generates the device
C; the device tick is never hand-written.
"""
import json

NET = {
    "device": "timeframe",
    "window_base": "0x2000000",
    "kind": "rollover",
    "comment": (
        "timeframe — the reference bar clock (SPEC_REGISTERS.md §2). A pure-combinational "
        "rollover detector: when (TAI - BAR_START) >= PERIOD, BAR_SEQ += 1, BAR_CLOSED pulses "
        "1 for one tick, BAR_START re-anchors to TAI. A GUIDE not a master: each bar module "
        "carries its own period multiple and closes its own bars by watching BAR_SEQ. Module "
        "barrier: TAI and PERIOD are presented on this device's own input lanes."
    ),

    # --- input / config lanes (driven from outside the netlist by the starter). ---
    # TF_TAI_IN carries the sampled TIME_TAI_NS_REG value (module-barrier: presented on
    # this device's lane, not a raw read of the time source's registers).
    "config_nodes": [
        {"name": "TF_POWER", "type": "bit",
         "comment": "power bit: the rollover detect runs while bit0 = 1 (set once)"},
        {"name": "TF_RUN_UNTIL", "type": "u64",
         "comment": "configured self-run tick budget (set once by starter)"},
        {"name": "TF_TAI_IN", "type": "u64",
         "comment": "sampled TIME_TAI_NS_REG value presented on this device's input lane "
                    "(module-barrier: not a raw read of the time source's registers)"},
        {"name": "TF_PERIOD_NS", "type": "u64",
         "comment": "bar period in ns (= REG_TF_CONFIG / TF_PERIOD_NS_REG); operator-written "
                    "once before the first tick"}
    ],

    # --- registered outputs (the device's writes). ----------------------------
    "dff_nodes": [
        {"name": "TF_TICKS", "type": "u64",
         "comment": "self-run tick counter (run-loop bookkeeping; bounds the self-run)"},
        {"name": "TF_BAR_SEQ", "type": "u64",
         "comment": "bar sequence; += 1 when elapsed >= period (= REG_TF_COUNTER rollover)"},
        {"name": "TF_BAR_CLOSED", "type": "u64",
         "comment": "0->1 one-tick pulse at a bar boundary (= TIMEFRAME_DIRTY_BIT)"},
        {"name": "TF_BAR_START", "type": "u64",
         "comment": "TAI at the current bar open (= TIMEFRAME_CURRENT_CANDLE_OPEN)"}
    ],

    # --- the rollover wiring the gennet consumes. -----------------------------
    "power": "TF_POWER",
    "tai": "TF_TAI_IN",            # sampled TAI value (input lane)
    "period": "TF_PERIOD_NS",      # configured bar period (input lane)
    "bar_seq": "TF_BAR_SEQ",       # incremented on rollover
    "bar_closed": "TF_BAR_CLOSED", # one-tick pulse on rollover
    "bar_start": "TF_BAR_START",   # re-anchored to TAI on rollover
    "run": {"power": "TF_POWER", "count": "TF_TICKS", "limit": "TF_RUN_UNTIL"}
}


def main():
    with open("timeframe.net.json", "w") as f:
        json.dump(NET, f, indent=2)
        f.write("\n")
    print("emitted timeframe.net.json")


if __name__ == "__main__":
    main()
