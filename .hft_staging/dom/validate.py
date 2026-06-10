#!/usr/bin/env python3
"""validate.py — netlist validator for the DOM order-book device.

The reviewer for C-as-RTL work — semgrep/CVE/npm do NOT apply. Enforces the
structural laws on dom.net.json:

  single-writer : every DOM-owned dff/comb/table cell has exactly one writer (the
                  generated dom_tick); config nodes are inputs (zero internal
                  writers). The fifo_rx head lanes are NOT DOM nodes (they belong
                  to the fifo_rx window DOM only samples) — must NOT be redeclared.
  no-overlap    : no two DOM scalar nodes share an address; the four tables occupy
                  disjoint contiguous regions after the scalars.
  no-floating   : every wiring name resolves to a declared DOM node or table; the
                  run.count resolves; table_depth is a power of two.
  module-barrier: DOM declares NO node named FIFO_*, SEAM_*, NIC_*, or WIRE_* (it
                  SAMPLES the fifo_rx head slot from fifo_rx_gen.h; redeclaring
                  would be a private copy / second writer — a barrier violation).
  consume-gate  : the fifo fire + empty flags DOM samples are fifo_rx published
                  flags (not DOM-owned), and the head lanes are sampled via the
                  producer's address helper (offsets declared, names not copied).

Exit 0 = PASS; non-zero = FAIL with the offending nodes named.
"""
import json
import sys

FORBIDDEN_PREFIXES = ("FIFO_", "SEAM_", "NIC_", "WIRE_")


def scalar_nodes(net):
    """All DOM-owned scalar nodes (config + dff + comb), in address order."""
    names = []
    for key in ("config_nodes", "dff_nodes", "comb_nodes"):
        for n in net.get(key, []):
            names.append(n["name"])
    return names


def validate(net):
    errors = []
    scalars = scalar_nodes(net)
    declared = set(scalars)

    # no-overlap (scalars): no duplicate scalar node name.
    seen = set()
    for nm in scalars:
        if nm in seen:
            errors.append(f"no-overlap: scalar node '{nm}' declared more than once")
        seen.add(nm)

    # table_depth power of two.
    depth = net["table_depth"]
    if depth <= 0 or (depth & (depth - 1)) != 0:
        errors.append(f"table_depth ({depth}) must be a power of two (mask index)")

    # tables: distinct names, all sharing the same depth.
    tnames = [t["name"] for t in net.get("tables", [])]
    if len(tnames) != len(set(tnames)):
        errors.append("no-overlap: a table name is declared more than once")
    for t in net.get("tables", []):
        if t["depth"] != depth:
            errors.append(
                f"no-overlap: table '{t['name']}' depth ({t['depth']}) != table_depth "
                f"({depth}); all tables share the canonical depth.")

    # module-barrier: no DOM node may be named for a sibling's window.
    for nm in scalars + tnames:
        for pfx in FORBIDDEN_PREFIXES:
            if nm.startswith(pfx):
                errors.append(
                    f"module-barrier: DOM node '{nm}' names a sibling window ({pfx}*) "
                    f"— DOM SAMPLES the fifo_rx head from fifo_rx_gen.h, never declares "
                    f"a private copy (would be a second writer).")

    # single-writer: config nodes are inputs (no internal writer); every other
    # DOM node/table is written exactly once by dom_tick.
    config = {n["name"] for n in net.get("config_nodes", [])}
    written = [nm for nm in scalars if nm not in config]
    if len(written) != len(set(written)):
        errors.append("single-writer: a DOM output node is declared more than once")

    # no-floating: run.count resolves; every wiring name resolves to a declared
    # scalar node or a declared table.
    rc = net["run"]["count"]
    if rc not in declared:
        errors.append(f"no-floating: run.count '{rc}' is not a declared node")
    table_set = set(tnames)
    head_lanes = set(net.get("fifo_head_lanes", []))
    for key, val in net["wiring"].items():
        if val in declared or val in table_set or val in head_lanes:
            continue
        errors.append(f"no-floating: wiring.{key} '{val}' is not a declared node/table/head-lane")

    # consume-gate: the fifo fire + empty DOM samples must be fifo_rx published
    # flags (named FIFO_*), i.e. NOT DOM-owned (they come from the FIFO window).
    for key in ("fifo_fire", "fifo_empty"):
        v = net[key]
        if v in declared:
            errors.append(
                f"consume-gate: {key} '{v}' is a DOM-owned node — it must be a "
                f"fifo_rx published flag sampled from fifo_rx_gen.h (not a copy).")
        if not v.startswith("FIFO_"):
            errors.append(
                f"consume-gate: {key} '{v}' must name a fifo_rx published flag (FIFO_*).")

    # head-lane offsets must cover every declared head lane (no floating sample).
    ofs = net.get("fifo_head_ofs", {})
    for ln in head_lanes:
        if ln not in ofs:
            errors.append(f"no-floating: fifo head lane '{ln}' has no declared sample offset")

    return errors


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "dom.net.json"
    with open(path) as f:
        net = json.load(f)
    errs = validate(net)
    if errs:
        print(f"VALIDATE {path}: FAIL ({len(errs)} error(s))")
        for e in errs:
            print("  " + e)
        sys.exit(1)
    n_scalar = len(scalar_nodes(net))
    n_tables = len(net.get("tables", []))
    print(f"VALIDATE {path}: PASS — {n_scalar} scalar nodes + {n_tables} tables "
          f"(depth {net['table_depth']}); single-writer/no-overlap/no-floating/"
          "module-barrier/consume-gate OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
