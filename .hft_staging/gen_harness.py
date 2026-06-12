#!/usr/bin/env python3
"""gen_harness.py — emit the POWER HARNESS module from a harness spec (phase 2).

Consumes a harness YAML (harness/system.harness.yaml: boards, power_bit,
start_stop, sequence) and SYNTHESIZES the harness module's logic spec, then runs
the GENERIC emitter (gen_module_net.py) on it to emit the netlist. The harness is
a real module — master power bit, bounded sequence counter, one registered power
lane per board INSTANCE — all canonical cells, nothing by hand.

Per board (branchless):
    reached_<b> = NOT cmp_lt(SEQ, TH_<b>)            (SEQ >= threshold)
    pwr_<b>     = and(reached_<b>, HARNESS_POWER)    (drops when master drops)
Sequence (clock-rule conformant):
    not_done = cmp_lt(SEQ, HARNESS_RUN_UNTIL)
    step     = gate(1, and(HARNESS_POWER, not_done))
    SEQ'     = addsub(SEQ, step)

This tool also emits the COMPLETE component fileset (factory law — zero hand
assembly): Makefile, thin test, canon-synced cells.h, generic gennet/validator.

Usage:
    # netlist to stdout (the Makefile's emit step):
    python3 gen_harness.py harness/system.harness.yaml > harness/harness.net.json
    # emit the COMPLETE component fileset (then `make test` inside it):
    python3 gen_harness.py harness/system.harness.yaml --emit-component harness
"""
import os
import re
import runpy
import shutil
import sys

try:
    import yaml
except ImportError:
    sys.stderr.write("gen_harness: PyYAML required\n")
    sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
GENERIC_EMITTER = os.path.join(HERE, "gen_module_net.py")
GENERIC_GENNET = os.path.join(HERE, "footprint", "gennet.py")   # converged generic generator
GENERIC_VALIDATE = os.path.join(HERE, "candle", "validate.py")  # generic netlist validator
CANON_CELLS = os.path.join(HERE, "cells", "cells.h")


def die(msg):
    sys.stderr.write("gen_harness: " + msg + "\n")
    sys.exit(2)


def load_spec(path):
    h = yaml.safe_load(open(path))
    for f in ("boards", "power_bit", "start_stop", "sequence"):
        if f not in h:
            die(f"harness spec missing required field: {f} (format: harness)")
    if sorted(h["boards"].keys()) != sorted(h["sequence"]):
        die("sequence must name exactly the declared boards")
    return h


def synthesize_logic(h):
    power = h["power_bit"]
    run_until_name = h["start_stop"]
    run_until = int(h.get("run_until", 64))
    consts = [
        {"name": power, "type": "u64", "value": 0,
         "comment": "master power switch — set once by the starter; everything gates on it"},
        {"name": run_until_name, "type": "u64", "value": run_until,
         "comment": "sequence bound (clock rule: start/stop)"},
        {"name": "HARNESS_ONE", "type": "u64", "value": 1, "comment": "constant 1"},
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
    dffs = [{"name": "HARNESS_SEQ", "type": "u64", "fed_by": "seq_next",
             "comment": "power-up sequence counter (harness ticks)"}]
    seam_outputs = []
    for b in h["sequence"]:
        cfg = h["boards"][b]
        lane = cfg["power_lane"]
        th = int(cfg["at_tick"])
        bid = b.replace("-", "_")
        consts.append({"name": f"HARNESS_TH_{bid.upper()}", "type": "u64", "value": th,
                       "comment": f"{b} powers at sequence tick {th}"})
        combs.append({"name": f"reached_{bid}", "cell": "cmp_lt",
                      "inputs": ["HARNESS_SEQ", f"HARNESS_TH_{bid.upper()}"], "invert": True,
                      "comment": f"1 once SEQ >= {th} (NOT SEQ < TH)"})
        combs.append({"name": f"pwr_{bid}", "cell": "and",
                      "inputs": [f"reached_{bid}", power],
                      "comment": f"{b} powered iff reached AND master on (drops with master)"})
        dffs.append({"name": lane, "type": "u64", "fed_by": f"pwr_{bid}",
                     "comment": f"power lane for board instance {b} (registered hop)"})
        seam_outputs.append({"name": f"{lane}_OUT", "source": lane, "type": "u64",
                             "comment": f"published power lane for {b}"})
    return {
        "module": "harness",
        "kind": "harness",
        "clock": {"power": power,
                  "comment": "Self-running from the master power bit, bounded by "
                             + run_until_name + " (clock rule). Nothing external steps it."},
        "seam_inputs": [],
        "const_nodes": consts,
        "dff_nodes": dffs,
        "comb_nodes": combs,
        "wiring": {"sequence": h["sequence"],
                   "note": "power lanes bind to board-instance power inputs at addressing/install"},
        "seam_outputs": seam_outputs,
    }


# ---- component fileset (templates live IN the tool) --------------------------

MAKEFILE = '''# harness — THE POWER HARNESS (programmatic on/off + sequenced power-up for the
# 3 board instances). EMITTED BY gen_harness.py — DO NOT EDIT BY HAND.
# Flow: system.harness.yaml --gen_harness--> netlist --validate--> --gennet-->
# device C --cc--> thin test. NOTHING by hand.
CC=cc
CFLAGS=-std=c11 -Wall -Wextra -Werror -O2
PY=python3
SPEC=system.harness.yaml
NET=harness.net.json
GEN=harness_gen.h
.PHONY: all emit validate gen test clean
all: test
emit: $(SPEC) ../gen_harness.py ../gen_module_net.py
\t$(PY) ../gen_harness.py $(SPEC) > $(NET)
$(NET): $(SPEC) ../gen_harness.py ../gen_module_net.py
\t$(PY) ../gen_harness.py $(SPEC) > $(NET)
validate: $(NET)
\t$(PY) validate.py $(NET)
gen: validate
\t$(PY) gennet.py $(NET) > $(GEN)
test: gen
\t$(CC) $(CFLAGS) -o test_harness test_harness.c
\t./test_harness
clean:
\trm -f test_harness
'''

TEST = '''/* test_harness.c — thin test: master power on + run + display power lanes.
 * EMITTED BY gen_harness.py — DO NOT EDIT BY HAND (regenerate via the tool).
 * Proves the sequenced power-up: control@0, in@4, main@8, bounded by RUN_UNTIL. */
#include <stdio.h>
#include "harness_gen.h"

int main(void) {
    word_t r[HARNESS_REG_COUNT] = {0};
    harness_init(r);
    r[HARNESS_HARNESS_POWER] = 1u;          /* master ON — the only external act */
    for (int t = 0; t < 6; t++) harness_tick(r);
    printf("t=6 : control=%llu in=%llu main=%llu (seq=%llu)\\n",
           (unsigned long long)r[HARNESS_HARNESS_PWR_FPGA_CONTROL],
           (unsigned long long)r[HARNESS_HARNESS_PWR_FPGA_IN],
           (unsigned long long)r[HARNESS_HARNESS_PWR_FPGA_MAIN],
           (unsigned long long)r[HARNESS_HARNESS_SEQ]);
    for (int t = 0; t < 6; t++) harness_tick(r);
    printf("t=12: control=%llu in=%llu main=%llu\\n",
           (unsigned long long)r[HARNESS_HARNESS_PWR_FPGA_CONTROL],
           (unsigned long long)r[HARNESS_HARNESS_PWR_FPGA_IN],
           (unsigned long long)r[HARNESS_HARNESS_PWR_FPGA_MAIN]);
    r[HARNESS_HARNESS_POWER] = 0u;          /* master OFF — everything drops */
    harness_tick(r);
    printf("off : control=%llu in=%llu main=%llu\\n",
           (unsigned long long)r[HARNESS_HARNESS_PWR_FPGA_CONTROL],
           (unsigned long long)r[HARNESS_HARNESS_PWR_FPGA_IN],
           (unsigned long long)r[HARNESS_HARNESS_PWR_FPGA_MAIN]);
    return 0;
}
'''

GITIGNORE = "test_harness\n*.dSYM/\n"


def emit_component(comp_dir):
    os.makedirs(comp_dir, exist_ok=True)
    with open(os.path.join(comp_dir, "Makefile"), "w") as f:
        f.write(MAKEFILE)
    with open(os.path.join(comp_dir, "test_harness.c"), "w") as f:
        f.write(TEST)
    with open(os.path.join(comp_dir, ".gitignore"), "w") as f:
        f.write(GITIGNORE)
    # tool-performed syncs from the canonical sources (single source of truth):
    cells = open(CANON_CELLS).read()
    cells = re.sub(r"[A-Za-z_]+CELLS_H", "HARNESS_CELLS_H", cells)
    with open(os.path.join(comp_dir, "cells.h"), "w") as f:
        f.write(cells)
    shutil.copyfile(GENERIC_GENNET, os.path.join(comp_dir, "gennet.py"))
    shutil.copyfile(GENERIC_VALIDATE, os.path.join(comp_dir, "validate.py"))
    sys.stderr.write(f"gen_harness: emitted complete fileset -> {comp_dir}/ "
                     f"(Makefile, test, cells.h<-canon, gennet<-generic, validate<-generic)\n"
                     f"gen_harness: now run `make test` inside {comp_dir}/\n")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        die("usage: gen_harness.py <system.harness.yaml> [--emit-component <dir>] "
            "[> harness.net.json]")
    spec_path = args[0]
    h = load_spec(spec_path)

    if "--emit-component" in sys.argv:
        i = sys.argv.index("--emit-component")
        if i + 1 >= len(sys.argv):
            die("--emit-component needs a directory")
        emit_component(sys.argv[i + 1])
        return

    # Write the synthesized logic spec next to the harness spec (TOOL OUTPUT —
    # committed for provenance; never hand-edited), then run the generic emitter.
    logic = synthesize_logic(h)
    out_dir = os.path.dirname(os.path.abspath(spec_path))
    logic_path = os.path.join(out_dir, "harness_logic.yaml")
    with open(logic_path, "w") as f:
        f.write("# GENERATED by gen_harness.py from system.harness.yaml — DO NOT EDIT BY HAND.\n"
                "# The harness module's logic spec, synthesized from the harness format and\n"
                "# consumed by the generic emitter (gen_module_net.py).\n")
        yaml.safe_dump(logic, f, sort_keys=False)
    sys.argv = [GENERIC_EMITTER, logic_path]
    runpy.run_path(GENERIC_EMITTER, run_name="__main__")


if __name__ == "__main__":
    main()
