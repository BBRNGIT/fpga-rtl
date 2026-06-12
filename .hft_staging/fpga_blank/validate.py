#!/usr/bin/env python3
"""validate.py — netlist validator for THE FPGA blank (the project gate).

EMITTED BY gen_fpga_blank.py — DO NOT EDIT BY HAND (regenerate via the tool).
Enforces the blank law IN CODE: pure device reference — NO logic, NO allocation,
NO addresses, NO differentiation, and A BLANK ASSIGNS NOTHING (no clock tables,
no module names, no placements). A device that breaks ANY rule does not pass.
(System-wide identity is additionally enforced by checks/check_blank_identity.py
at gate stage 2k.)
"""
import json
import sys

FORBIDDEN = ("dff_nodes", "comb_nodes", "config_nodes", "clock", "window_base",
             "role", "intended_modules_doc", "intended_modules", "placement",
             "residents", "clock_domain_table", "clock_domains", "modules", "slots")

# System module names — none may appear as a key anywhere in a blank.
MODULE_NAMES = {"mac", "internal", "taiosc", "tai", "adapter", "wire", "nic",
                "fifo_rx", "tai_cdc", "pip_resolver", "timeframe", "dom",
                "dom_bus", "candle", "footprint", "tpo", "harness"}


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "fpga_blank.net.json"
    net = json.load(open(path))
    errs = []

    if net.get("kind") != "fpga_blank":
        errs.append(f"kind must be 'fpga_blank' (got {net.get('kind')!r})")
    for forbidden in FORBIDDEN:
        if net.get(forbidden):
            errs.append(f"a blank must have NO {forbidden} (a blank assigns nothing; "
                        f"allocation/placement/clocks-by-install are phases 3/4)")

    def walk(o, path_=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if str(k).lower() in MODULE_NAMES:
                    errs.append(f"'{path_}{k}' — system module named in the blank "
                                f"(part pre-assignment; install is phase 4)")
                walk(v, path_ + str(k) + ".")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, path_ + f"[{i}].")
    walk(net)

    fab = net.get("fabric") or {}
    regs = fab.get("registers", 0)
    if regs <= 0 or (regs & (regs - 1)) != 0:
        errs.append(f"fabric.registers ({regs}) must be a positive power of two")
    if fab.get("word_bits") != 64:
        errs.append("fabric.word_bits must be 64")
    if not net.get("part_ref"):
        errs.append("part_ref missing — a blank must be real-part referenced")
    geo = net.get("address_space_geometry") or {}
    for k in ("size", "slot_alignment", "cdc_region_size"):
        if not isinstance(geo.get(k), int) or geo.get(k) <= 0:
            errs.append(f"address_space_geometry.{k} must be a positive integer")

    if errs:
        for e in errs:
            sys.stderr.write(f"[validate] FAIL: {e}\n")
        sys.exit(3)
    print(f"[validate] OK — THE fpga blank: fabric {regs} regs, full part, "
          f"undifferentiated, assigns nothing")


if __name__ == "__main__":
    main()
