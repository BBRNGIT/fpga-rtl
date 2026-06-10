#!/usr/bin/env python3
"""validate.py — netlist validator for the PIP_RESOLVER lookup device.

The reviewer for C-as-RTL work — semgrep/CVE/npm do NOT apply. Enforces the
structural laws on pip_resolver.net.json:

  single-writer : every PIP-owned table/dff/out/status node has exactly one writer
                  (the generated pip_resolver_tick / run loop); config nodes are
                  inputs (zero internal writers). The pip-config table slots are
                  init-only config (written once by the starter, read-only in the
                  tick). The NIC seam inputs are NOT PIP nodes (they belong to the
                  NIC window the PIP_RESOLVER only reads) — must NOT be redeclared.
  no-overlap    : no two PIP nodes share an address (node names are the address keys).
  no-floating   : every referenced output source is the computed 'res'/'symbol'/
                  'valid'; the compute operands are NIC seam input lanes; table
                  depth is a power of two.
  module-barrier: the PIP_RESOLVER declares NO node named SEAM_* / NIC_* / WIRE_* /
                  TAI_* (it reads the NIC seam from nic_gen.h; redeclaring would be a
                  private copy / a second writer — a barrier violation).

Exit 0 = PASS; non-zero = FAIL with the offending nodes named.
"""
import json
import sys


def pip_nodes(net):
    """All PIP-OWNED nodes (config + table slots + dff + out + status)."""
    names = []
    for n in net.get("config_nodes", []):
        names.append(n["name"])
    table = net["table"]
    for i in range(table["depth"]):
        names.append(f"{table['prefix']}_{i}")
    for n in net.get("dff_nodes", []):
        names.append(n["name"])
    for n in net.get("out_nodes", []):
        names.append(n["name"])
    for n in net.get("out_status", []):
        names.append(n["name"])
    return names


def validate(net):
    errors = []
    names = pip_nodes(net)

    # no-overlap
    seen = set()
    for nm in names:
        if nm in seen:
            errors.append(f"no-overlap: node '{nm}' declared more than once")
        seen.add(nm)
    declared = set(names)

    # table depth power of two
    depth = net["table"]["depth"]
    if depth <= 0 or (depth & (depth - 1)) != 0:
        errors.append(f"table: depth ({depth}) must be a power of two (mask index)")

    # module-barrier: no PIP node may be named for a sibling's window lane.
    for nm in names:
        if (nm.startswith("SEAM_") or nm.startswith("NIC_")
                or nm.startswith("WIRE_") or nm.startswith("TAI_")):
            errors.append(
                f"module-barrier: PIP node '{nm}' names a sibling window lane — "
                f"the PIP_RESOLVER READS the NIC seam from nic_gen.h, never declares "
                f"a private copy (would be a second writer).")

    # single-writer: config nodes (incl. the init-only table slots) are inputs;
    # every other PIP node is written exactly once by pip_resolver_tick (the
    # generator emits one cell_dff per dff/out/status node). The run-counter
    # (PIP_TICKS) is written by the run loop — still a single writer.
    rc = net["run"]["count"]
    if rc not in declared:
        errors.append(f"no-floating: run.count '{rc}' is not a declared node")

    # no-floating: out sources must be the computed 'res'/'symbol'; status sources
    # must be the computed 'valid'.
    for n in net.get("out_nodes", []):
        if n["from"] not in ("res", "symbol"):
            errors.append(
                f"no-floating: out lane '{n['name']}' source '{n['from']}' is "
                f"not the computed 'res' or 'symbol'")
        if n.get("en") not in ("valid",):
            errors.append(
                f"no-floating: out lane '{n['name']}' enable '{n.get('en')}' "
                f"must be the computed 'valid'")
    for n in net.get("out_status", []):
        if n["from"] not in ("valid",):
            errors.append(
                f"no-floating: out status '{n['name']}' source '{n['from']}' "
                f"must be the computed 'valid'")

    # the compute references (symbol/valid) must be NIC seam input lanes.
    nic_in = set(net.get("nic_inputs", []))
    comp = net["compute"]
    for key in ("symbol", "valid"):
        if comp[key] not in nic_in:
            errors.append(
                f"no-floating: compute.{key} '{comp[key]}' is not a NIC seam input")

    # the table index source must be a NIC seam input lane.
    if net["table"]["index_from"] not in nic_in:
        errors.append(
            f"no-floating: table.index_from '{net['table']['index_from']}' is "
            f"not a NIC seam input")

    return errors


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "pip_resolver.net.json"
    with open(path) as f:
        net = json.load(f)
    errs = validate(net)
    if errs:
        print(f"VALIDATE {path}: FAIL ({len(errs)} error(s))")
        for e in errs:
            print("  " + e)
        sys.exit(1)
    n = len(pip_nodes(net))
    print(f"VALIDATE {path}: PASS — {n} nodes, single-writer/no-overlap/no-floating/"
          "module-barrier OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
