#!/usr/bin/env python3
"""check_blank_identity.py — ALL BLANKS ARE IDENTICAL (founder law, 2026-06-12).

There is ONE blank: the full real part, complete and UNDIFFERENTIATED. The boards
(fpga-in / fpga-main / fpga-control) are identical INSTANCES of it; identity is a
name assigned at addressing (phase 3), and what differs between boards is only
what gets INSTALLED (phase 4) — never the blank.

Enforced on every netlist of kind fpga_blank found under the staging tree:
  no-differentiation : a blank netlist must carry NO role, NO intended/installed
                       modules, NO placement, NO per-instance fields, NO clock
                       SUBSET marker — only full real-part facts.
  one-part-profile   : exactly ONE part profile may exist (device_profiles/);
                       per-board profiles are differentiation at the source.
  identical          : if multiple blank netlists exist, they must be IDENTICAL
                       byte-for-byte after normalizing the device/instance name.
  full-part          : resource/io tables must match the part profile exactly
                       (no slicing).

Usage: check_blank_identity.py [staging_dir]     (default: script's parent)
Exit 0 = PASS (or no blanks yet); 1 = FAIL with violations named.
"""
import glob
import json
import os
import re
import sys

try:
    import yaml
except Exception:
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))
STAGING = os.path.normpath(os.path.join(HERE, ".."))

FORBIDDEN_KEYS = re.compile(
    r"(^role$|intended_modules|installed_modules|placement|residents|assigned)", re.I)
# A BLANK ASSIGNS NOTHING: clock domains belong to the oscillator MODULES and
# arrive only at install (phase 4). A blank/profile carrying a clock table is
# part-assignment at casting — the violation that slipped through 2026-06-12.
ASSIGNMENT_KEYS = re.compile(r"(clock_domain|clock_domains|clock_table|slots?$)", re.I)
# Known system module names — none may appear as a KEY anywhere in a blank.
MODULE_NAMES = {"mac", "internal", "taiosc", "tai", "adapter", "wire", "nic",
                "fifo_rx", "tai_cdc", "pip_resolver", "timeframe", "dom",
                "dom_bus", "candle", "footprint", "tpo", "harness"}


def main():
    staging = sys.argv[1] if len(sys.argv) > 1 else STAGING
    blanks = []
    for nj in glob.glob(os.path.join(staging, "*", "*.net.json")):
        try:
            d = json.load(open(nj))
        except Exception:
            continue
        if d.get("kind") == "fpga_blank":
            blanks.append((nj, d))

    if not blanks:
        print("check_blank_identity: no fpga_blank netlists present — N/A")
        sys.exit(0)

    errs = []

    # (1) no differentiation AND no assignment anywhere in a blank netlist:
    #     no roles/placement, no clock tables, no system-module names as keys.
    for nj, d in blanks:
        def walk(o, path=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    if FORBIDDEN_KEYS.search(str(k)) and v:
                        errs.append(f"{os.path.basename(nj)}: '{path}{k}' — differentiation "
                                    f"in a blank (role/placement/slicing is phase-3/4)")
                    if ASSIGNMENT_KEYS.search(str(k)) and v:
                        errs.append(f"{os.path.basename(nj)}: '{path}{k}' — ASSIGNMENT in a "
                                    f"blank (clock domains belong to oscillator modules and "
                                    f"arrive at install; a blank assigns nothing)")
                    if str(k).lower() in MODULE_NAMES:
                        errs.append(f"{os.path.basename(nj)}: '{path}{k}' — system module "
                                    f"named in a blank (part pre-assignment; install is phase 4)")
                    walk(v, path + str(k) + ".")
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, path + f"[{i}].")
        walk(d)

    # (1b) the part profile itself must carry no clock table / module assignment
    if yaml:
        for p in glob.glob(os.path.join(staging, "device_profiles", "*.yaml")):
            prof = yaml.safe_load(open(p)) or {}
            if not prof.get("part_ref"):
                continue
            for k in prof:
                if ASSIGNMENT_KEYS.search(str(k)):
                    errs.append(f"{os.path.basename(p)}: '{k}' — the part profile carries a "
                                f"clock table / assignment (part facts only; clocks arrive "
                                f"with installed oscillator modules)")

    # (2) exactly one part profile (no per-board profiles)
    profs = [p for p in glob.glob(os.path.join(staging, "device_profiles", "*.yaml"))
             if yaml and (yaml.safe_load(open(p)) or {}).get("part_ref")]
    if len(profs) > 1:
        errs.append(f"multiple part profiles ({[os.path.basename(p) for p in profs]}) — "
                    f"ONE blank, ONE part profile; per-board profiles are differentiation")

    # (3) all blank netlists identical modulo the device/instance name
    def normalized(d):
        c = json.loads(json.dumps(d))
        for k in ("device", "board", "comment"):
            c.pop(k, None)
        return json.dumps(c, sort_keys=True)
    forms = {normalized(d) for _, d in blanks}
    if len(forms) > 1:
        errs.append(f"{len(blanks)} blank netlists are NOT identical (modulo instance "
                    f"name) — all blanks must be the same full part")

    # (4) full part: blank resource/io tables must equal the part profile's
    if profs and yaml:
        prof = yaml.safe_load(open(profs[0]))
        want_res = {rn: int(r["capacity"]) for rn, r in (prof.get("resources") or {}).items()}
        want_io = {k: int(v) for k, v in (prof.get("io") or {}).items()}
        for nj, d in blanks:
            got_res = {rn: int(r.get("capacity", -1)) for rn, r in (d.get("resource_budget") or {}).items()}
            got_io = {k: int(v) for k, v in (d.get("io_geometry") or {}).items()}
            if want_res and got_res and got_res != want_res:
                errs.append(f"{os.path.basename(nj)}: resource table != part profile (sliced?)")
            if want_io and got_io and got_io != want_io:
                errs.append(f"{os.path.basename(nj)}: io table != part profile (sliced?)")

    if errs:
        print("BLANK-IDENTITY: FAIL — the identical-blank law is violated:")
        for e in errs:
            print(f"  ERROR: {e}")
        sys.exit(1)
    print(f"check_blank_identity: PASS — {len(blanks)} blank(s), identical, undifferentiated, full-part")
    sys.exit(0)


if __name__ == "__main__":
    main()
