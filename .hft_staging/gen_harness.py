#!/usr/bin/env python3
"""gen_harness.py — emit the POWER HARNESS module from a harness spec.

Factory phase 2 tool (factory_toolchain.yaml). Consumes a harness YAML
(harness/system.harness.yaml: boards, power_bit, start_stop, sequence) and
SYNTHESIZES the harness module's logic spec, then runs the GENERIC emitter
(gen_module_net.py) on it to emit the netlist. The harness is a real module —
master power bit, bounded sequence counter, one power lane per board — all
canonical cells, nothing by hand.

Per board (branchless):
    reached_<b> = NOT cmp_lt(SEQ, TH_<b>)            (SEQ >= threshold)
    PWR_<b>     = and(reached_<b>, HARNESS_POWER)    (drops when master drops)
Sequence (clock-rule conformant):
    not_done = cmp_lt(SEQ, HARNESS_RUN_UNTIL)
    step     = gate(1, and(HARNESS_POWER, not_done))
    SEQ'     = addsub(SEQ, step)

Usage:
    python3 gen_harness.py harness/system.harness.yaml > harness/harness.net.json
(Also writes harness/harness_logic.yaml — a TOOL OUTPUT, never hand-edited —
so the standard per-component flow and byte-match checks apply.)
"""
import os
import runpy
import sys

try:
    import yaml
except ImportError:
    sys.stderr.write("gen_harness: PyYAML required\n")
    sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
GENERIC = os.path.join(HERE, "gen_module_net.py")


def die(msg):
    sys.stderr.write("gen_harness: " + msg + "\n")
    sys.exit(2)


def main():
    if len(sys.argv) < 2:
        die("usage: gen_harness.py <system.harness.yaml> > harness.net.json")
    spec_path = sys.argv[1]
    h = yaml.safe_load(open(spec_path))

    for f in ("boards", "power_bit", "start_stop", "sequence"):
        if f not in h:
            die(f"harness spec missing required field: {f} (format: harness)")
    boards = h["boards"]
    seq_order = h["sequence"]
    if sorted(boards.keys()) != sorted(seq_order):
        die("sequence must name exactly the declared boards")
    power = h["power_bit"]
    run_until_name = h["start_stop"]
    run_until = int(h.get("run_until", 64))

    # ---- synthesize the harness module's logic spec --------------------------
    consts = [
        {"name": power, "type": "u64", "value": 0,
         "comment": "master power switch — set once by the starter; everything gates on it"},
        {"name": run_until_name, "type": "u64", "value": run_until,
         "comment": "sequence bound (clock rule: start/stop)"},
    ]
    combs = [
        {"name": "not_done", "cell": "cmp_lt", "inputs": ["HARNESS_SEQ", run_until_name],
         "comment": "1 while SEQ < RUN_UNTIL"},
        {"name": "running", "cell": "and", "inputs": [power, "not_done"],
         "comment": "master on AND not done"},
        {"name": "seq_step", "cell": "gate", "inputs": ["HARNESS_ONE", "running"],
         "comment": "advance 1 while running, else 0"},
        {"name": "seq_next", "cell": "addsub", "inputs": ["HARNESS_SEQ", "seq_step"], "sub": 0,
         "comment": "bounded sequence counter"},
    ]
    consts.append({"name": "HARNESS_ONE", "type": "u64", "value": 1, "comment": "constant 1"})
    dffs = [{"name": "HARNESS_SEQ", "type": "u64", "fed_by": "seq_next",
             "comment": "power-up sequence counter (harness ticks)"}]
    seam_outputs = []
    for b in seq_order:
        cfg = boards[b]
        lane = cfg["power_lane"]
        th = int(cfg["at_tick"])
        cname = f"HARNESS_TH_{b.replace('-', '_').upper()}"
        consts.append({"name": cname, "type": "u64", "value": th,
                       "comment": f"{b} powers at sequence tick {th}"})
        combs.append({"name": f"reached_{b.replace('-', '_')}", "cell": "cmp_lt",
                      "inputs": ["HARNESS_SEQ", cname], "invert": True,
                      "comment": f"1 once SEQ >= {th} (NOT SEQ < TH)"})
        combs.append({"name": f"pwr_{b.replace('-', '_')}", "cell": "and",
                      "inputs": [f"reached_{b.replace('-', '_')}", power],
                      "comment": f"{b} powered iff reached AND master on (drops with master)"})
        dffs.append({"name": lane, "type": "u64", "fed_by": f"pwr_{b.replace('-', '_')}",
                     "comment": f"power lane for {b} (registered hop to the board)"})
        seam_outputs.append({"name": f"{lane}_OUT", "source": lane, "type": "u64",
                             "comment": f"published power lane for {b}"})

    logic = {
        "module": "harness",
        "kind": "harness",
        "clock": {"power": power,
                  "comment": "Self-running from the master power bit, bounded by "
                             + run_until_name + " (clock rule). Nothing external steps it."},
        "seam_inputs": [],
        "const_nodes": consts,
        "dff_nodes": dffs,
        "comb_nodes": combs,
        "wiring": {"sequence": seq_order,
                   "note": "power lanes bind to board power inputs at assignment/install"},
        "seam_outputs": seam_outputs,
    }

    # Write the synthesized logic spec next to the harness spec (TOOL OUTPUT —
    # committed for provenance/byte-match; never hand-edited).
    out_dir = os.path.dirname(os.path.abspath(spec_path))
    logic_path = os.path.join(out_dir, "harness_logic.yaml")
    with open(logic_path, "w") as f:
        f.write("# GENERATED by gen_harness.py from system.harness.yaml — DO NOT EDIT BY HAND.\n"
                "# The harness module's logic spec, synthesized from the harness format and\n"
                "# consumed by the generic emitter (gen_module_net.py).\n")
        yaml.safe_dump(logic, f, sort_keys=False)

    # Run the generic emitter on it — netlist to stdout.
    sys.argv = [GENERIC, logic_path]
    runpy.run_path(GENERIC, run_name="__main__")


if __name__ == "__main__":
    main()
