#!/usr/bin/env python3
"""validate.py — netlist validator for THE FPGA blank (the project gate).

EMITTED BY gen_fpga_blank.py — DO NOT EDIT BY HAND (regenerate via the tool).
Enforces the blank law: pure device reference — NO logic, NO allocation, NO
addresses, NO differentiation. (System-wide identity across blanks is enforced
separately by checks/check_blank_identity.py at gate stage 2k.)
"""
import json
import sys


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "fpga_blank.net.json"
    net = json.load(open(path))
    errs = []

    if net.get("kind") != "fpga_blank":
        errs.append(f"kind must be 'fpga_blank' (got {net.get('kind')!r})")
    for forbidden in ("dff_nodes", "comb_nodes", "config_nodes", "clock", "window_base",
                      "role", "intended_modules_doc", "intended_modules", "placement",
                      "residents"):
        if net.get(forbidden):
            errs.append(f"a blank must have NO {forbidden} (pure undifferentiated "
                        f"device reference; allocation/placement are phases 3/4)")
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
    for cn, c in (net.get("clock_domain_table") or {}).items():
        if not isinstance(c.get("frequency_hz"), int):
            errs.append(f"clock domain {cn}: frequency_hz must be an integer")

    if errs:
        for e in errs:
            sys.stderr.write(f"[validate] FAIL: {e}\n")
        sys.exit(3)
    print(f"[validate] OK — THE fpga blank: fabric {regs} regs, "
          f"{len(net.get('clock_domain_table', {}))} clock domains, full part, undifferentiated")


if __name__ == "__main__":
    main()
