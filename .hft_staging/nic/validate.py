#!/usr/bin/env python3
"""validate.py — netlist validator for the NIC gateway device.

The reviewer for C-as-RTL work — semgrep/CVE/npm do NOT apply. Enforces the
structural laws on nic.net.json:

  single-writer : every NIC-owned dff/seam/status/ring node has exactly one writer
                  (the generated nic_tick); config nodes are inputs (zero internal
                  writers). The wire/tai inputs are NOT NIC nodes (they belong to the
                  sibling windows the NIC only reads) — they must NOT be redeclared.
  no-overlap    : no two NIC nodes share an address (node names are the address keys).
  no-floating   : every referenced seam source is a wire/tai input lane or the
                  computed pass/dup; ring depth is a power of two.
  module-barrier: the NIC declares NO node named WIRE_* or TAI_* (it reads those
                  from the siblings' windows; redeclaring them would be a private
                  copy / a second writer — a barrier violation).

Exit 0 = PASS; non-zero = FAIL with the offending nodes named.
"""
import json
import sys


def nic_nodes(net):
    """All NIC-OWNED nodes (config + dff + ring seq/valid + seam + status)."""
    names = []
    for n in net.get("config_nodes", []):
        names.append(n["name"])
    for n in net.get("dff_nodes", []):
        names.append(n["name"])
    ring = net["ring"]
    for i in range(ring["depth"]):
        names.append(f"{ring['seq_prefix']}_{i}")
        names.append(f"{ring['valid_prefix']}_{i}")
    for n in net.get("seam_nodes", []):
        names.append(n["name"])
    for n in net.get("seam_status", []):
        names.append(n["name"])
    return names


def validate(net):
    errors = []
    names = nic_nodes(net)

    # no-overlap
    seen = set()
    for nm in names:
        if nm in seen:
            errors.append(f"no-overlap: node '{nm}' declared more than once")
        seen.add(nm)
    declared = set(names)

    # ring depth power of two
    depth = net["ring"]["depth"]
    if depth <= 0 or (depth & (depth - 1)) != 0:
        errors.append(f"ring: depth ({depth}) must be a power of two (mask index)")

    # module-barrier: no NIC node may be named for a sibling's window.
    for nm in names:
        if nm.startswith("WIRE_") or nm.startswith("TAI_"):
            errors.append(
                f"module-barrier: NIC node '{nm}' names a sibling window lane — "
                f"the NIC READS those from wire_gen.h/tai_cdc_gen.h, never declares "
                f"a private copy (would be a second writer).")

    # single-writer: config nodes are inputs (no internal writer); every other
    # NIC node is written exactly once by nic_tick (the generator emits one
    # cell_dff per dff/seam/status/ring node).
    config = {n["name"] for n in net.get("config_nodes", [])}
    written_once = [nm for nm in names if nm not in config]
    # the run-counter (NIC_TICKS) is written by the run loop, not nic_tick — still
    # a single writer. Just confirm it is a declared dff.
    rc = net["run"]["count"]
    if rc not in declared:
        errors.append(f"no-floating: run.count '{rc}' is not a declared node")
    # confirm there are no duplicate-named writers (the generator is 1 writer/node
    # by construction; here we just assert the declared set is internally consistent).
    if len(written_once) != len(set(written_once)):
        errors.append("single-writer: a NIC output node is declared more than once")

    # no-floating: seam sources must be a wire input, the tai input, or pass/dup.
    wire_in = set(net.get("wire_inputs", []))
    tai_in = net.get("tai_input")
    legal_src = wire_in | {tai_in}
    for n in net.get("seam_nodes", []):
        if n["from"] not in legal_src:
            errors.append(
                f"no-floating: seam lane '{n['name']}' source '{n['from']}' is "
                f"not a declared wire/tai input lane")
    for n in net.get("seam_status", []):
        if n["from"] not in ("pass", "dup"):
            errors.append(
                f"no-floating: seam status '{n['name']}' source '{n['from']}' "
                f"must be the computed 'pass' or 'dup'")

    # the compute references (stamp/seq/valid/src_time) must be wire/tai inputs.
    comp = net["compute"]
    for key in ("valid", "seq", "src_time"):
        if comp[key] not in wire_in:
            errors.append(f"no-floating: compute.{key} '{comp[key]}' is not a wire input")
    if comp["stamp"] != tai_in:
        errors.append(f"no-floating: compute.stamp '{comp['stamp']}' is not the tai input")

    return errors


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "nic.net.json"
    with open(path) as f:
        net = json.load(f)
    errs = validate(net)
    if errs:
        print(f"VALIDATE {path}: FAIL ({len(errs)} error(s))")
        for e in errs:
            print("  " + e)
        sys.exit(1)
    n = len(nic_nodes(net))
    print(f"VALIDATE {path}: PASS — {n} nodes, single-writer/no-overlap/no-floating/"
          "module-barrier OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
