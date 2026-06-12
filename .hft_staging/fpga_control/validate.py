#!/usr/bin/env python3
"""validate.py — netlist validator for an FPGA BLANK (the project gate).

Enforces the blank-enforcement law on <board>.net.json:
  blank      : kind == fpga_blank; NO module allocation — no dff_nodes, no
               comb_nodes, no config_nodes, no clock (a blank owns no logic);
               NO addresses (no window_base or assigned slots — geometry only).
  fabric     : fabric.registers is a positive power of two; word_bits == 64.
  real-part  : part_ref present; clock_domain_table frequencies are integers.
  geometry   : address_space_geometry has size / slot_alignment / cdc_region_size.

Exit 0 = PASS; non-zero = FAIL with the offending detail.
"""
import json
import sys


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        sys.stderr.write("usage: validate.py <board>.net.json\n")
        sys.exit(2)
    net = json.load(open(path))
    errs = []

    if net.get("kind") != "fpga_blank":
        errs.append(f"kind must be 'fpga_blank' (got {net.get('kind')!r})")
    for forbidden in ("dff_nodes", "comb_nodes", "config_nodes", "clock", "window_base"):
        if net.get(forbidden):
            errs.append(f"a blank must have NO {forbidden} (pure device reference; "
                        f"allocation/install are later tool phases)")
    fab = net.get("fabric") or {}
    regs = fab.get("registers", 0)
    if regs <= 0 or (regs & (regs - 1)) != 0:
        errs.append(f"fabric.registers ({regs}) must be a positive power of two")
    if fab.get("word_bits") != 64:
        errs.append("fabric.word_bits must be 64")
    if not net.get("part_ref"):
        errs.append("part_ref missing — a blank must be real-part referenced (determinism)")
    geo = net.get("address_space_geometry") or {}
    for k in ("size", "slot_alignment", "cdc_region_size"):
        if not isinstance(geo.get(k), int) or geo.get(k) <= 0:
            errs.append(f"address_space_geometry.{k} must be a positive integer")
    for cn, c in (net.get("clock_domain_table") or {}).items():
        if not isinstance(c.get("frequency_hz"), int):
            errs.append(f"clock domain {cn}: frequency_hz must be an integer (no floats)")

    if errs:
        for e in errs:
            sys.stderr.write(f"[validate] FAIL: {e}\n")
        sys.exit(3)
    print(f"[validate] OK — fpga blank '{net.get('board')}', fabric {regs} regs, "
          f"{len(net.get('clock_domain_table', {}))} clock domains, real-part referenced")


if __name__ == "__main__":
    main()
