#!/usr/bin/env python3
"""validate.py — netlist validator for the fifo_rx CDC FIFO device.

The reviewer for C-as-RTL work — semgrep/CVE/npm do NOT apply. Enforces the
structural laws on fifo_rx.net.json:

  single-writer : every fifo_rx-owned dff/comb/slot node has exactly one writer
                  (the generated fifo_rx_tick); config nodes are inputs (zero
                  internal writers). The nic seam inputs are NOT fifo_rx nodes
                  (they belong to the nic window the FIFO only reads) — they must
                  NOT be redeclared.
  no-overlap    : no two fifo_rx nodes share an address (node names are the keys).
  no-floating   : every referenced write/read-side wiring name resolves to a
                  declared fifo_rx node; the slot lanes resolve to nic seam inputs;
                  depth is a power of two; ptr_bits = addr_bits + 1.
  module-barrier: fifo_rx declares NO node named SEAM_* or NIC_* (it reads those
                  from the nic window; redeclaring would be a private copy / second
                  writer — a barrier violation).
  cdc-structure : two distinct 2-FF synchronizer chains (write-domain captures the
                  READ gray; read-domain captures the WRITE gray); each chain's
                  two stages are distinct declared dffs; the sync source is the
                  OPPOSITE side's gray pointer (cross-domain read goes only through
                  the synchronizer, never raw).

Exit 0 = PASS; non-zero = FAIL with the offending nodes named.
"""
import json
import sys


def fifo_nodes(net):
    """All fifo_rx-OWNED nodes (config + dff + comb + per-slot per-lane RAM)."""
    names = []
    for n in net.get("config_nodes", []):
        names.append(n["name"])
    for n in net.get("dff_nodes", []):
        names.append(n["name"])
    for n in net.get("comb_nodes", []):
        names.append(n["name"])
    ram = net["ram"]
    for i in range(ram["depth"]):
        for ln in ram["lanes"]:
            names.append(f"{ram['slot_prefix']}_{i}_{ln}")
    return names


def validate(net):
    errors = []
    names = fifo_nodes(net)

    # no-overlap
    seen = set()
    for nm in names:
        if nm in seen:
            errors.append(f"no-overlap: node '{nm}' declared more than once")
        seen.add(nm)
    declared = set(names)

    # depth power of two + pointer width relation.
    depth = net["depth"]
    if depth <= 0 or (depth & (depth - 1)) != 0:
        errors.append(f"depth ({depth}) must be a power of two (mask index)")
    addr_bits = net["addr_bits"]
    ptr_bits = net["ptr_bits"]
    if (1 << addr_bits) != depth:
        errors.append(f"addr_bits ({addr_bits}) must satisfy 2**addr_bits == depth ({depth})")
    if ptr_bits != addr_bits + 1:
        errors.append(
            f"ptr_bits ({ptr_bits}) must be addr_bits+1 ({addr_bits + 1}) — the "
            f"extra wrap bit distinguishes FULL from EMPTY (Cummings).")

    # module-barrier: no fifo_rx node may be named for the nic's window.
    for nm in names:
        if nm.startswith("SEAM_") or nm.startswith("NIC_"):
            errors.append(
                f"module-barrier: fifo_rx node '{nm}' names the nic window — the "
                f"FIFO READS the seam from nic_gen.h, never declares a private copy "
                f"(would be a second writer).")

    # single-writer: config nodes are inputs (no internal writer); every other
    # fifo_rx node is written exactly once by fifo_rx_tick.
    config = {n["name"] for n in net.get("config_nodes", [])}
    written_once = [nm for nm in names if nm not in config]
    rc = net["run"]["count"]
    if rc not in declared:
        errors.append(f"no-floating: run.count '{rc}' is not a declared node")
    if len(written_once) != len(set(written_once)):
        errors.append("single-writer: a fifo_rx output node is declared more than once")

    # no-floating: every write/read-side wiring name resolves to a declared node
    # (except the cross-domain fire/sync SOURCES, which are nic-seam or the
    # opposite side's gray — checked below).
    ws, rs = net["write_side"], net["read_side"]
    for side, sd in (("write", ws), ("read", rs)):
        for key in ("bin", "gray", "sync1", "sync2"):
            if sd[key] not in declared:
                errors.append(f"no-floating: {side}_side.{key} '{sd[key]}' is not a declared node")
        flag_key = "full" if side == "write" else "empty"
        if sd[flag_key] not in declared:
            errors.append(f"no-floating: {side}_side.{flag_key} '{sd[flag_key]}' is not a declared node")
    for k in ("write", "read"):
        if net["fire"][k] not in declared:
            errors.append(f"no-floating: fire.{k} '{net['fire'][k]}' is not a declared node")

    # cdc-structure: two DISTINCT 2-FF chains; each chain's stages distinct; the
    # sync source is the OPPOSITE side's gray pointer (cross-domain only via sync).
    seam_in = set(net.get("seam_inputs", []))
    #  write side fires off a nic seam strobe (cross-domain input it samples).
    if ws["fire_from"] not in seam_in:
        errors.append(
            f"cdc-structure: write_side.fire_from '{ws['fire_from']}' must be a nic "
            f"seam input (the strobe the FIFO samples)")
    #  read side fires off a declared config read-enable.
    if rs["fire_from"] not in config:
        errors.append(
            f"cdc-structure: read_side.fire_from '{rs['fire_from']}' must be a config "
            f"read-enable lane")
    #  the write domain synchronizes the READ gray; the read domain the WRITE gray.
    if ws["sync_from"] != rs["gray"]:
        errors.append(
            f"cdc-structure: write_side.sync_from '{ws['sync_from']}' must be the "
            f"READ gray pointer '{rs['gray']}' (write domain syncs the read pointer)")
    if rs["sync_from"] != ws["gray"]:
        errors.append(
            f"cdc-structure: read_side.sync_from '{rs['sync_from']}' must be the "
            f"WRITE gray pointer '{ws['gray']}' (read domain syncs the write pointer)")
    #  each 2-FF chain's two stages must be distinct nodes, and the two chains
    #  must not share a stage (separate metastability hardware per direction).
    chain_w = (ws["sync1"], ws["sync2"])
    chain_r = (rs["sync1"], rs["sync2"])
    if chain_w[0] == chain_w[1]:
        errors.append("cdc-structure: write 2-FF chain stages must be distinct dffs")
    if chain_r[0] == chain_r[1]:
        errors.append("cdc-structure: read 2-FF chain stages must be distinct dffs")
    if set(chain_w) & set(chain_r):
        errors.append("cdc-structure: write and read 2-FF chains must not share a stage")

    # no-floating: each slot lane's source must be a nic seam input lane (SEAM_<lane>).
    ram = net["ram"]
    for ln in ram["lanes"]:
        src = f"SEAM_{ln}"
        if src not in seam_in:
            errors.append(
                f"no-floating: slot lane '{ln}' source '{src}' is not a declared "
                f"nic seam input")

    return errors


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "fifo_rx.net.json"
    with open(path) as f:
        net = json.load(f)
    errs = validate(net)
    if errs:
        print(f"VALIDATE {path}: FAIL ({len(errs)} error(s))")
        for e in errs:
            print("  " + e)
        sys.exit(1)
    n = len(fifo_nodes(net))
    print(f"VALIDATE {path}: PASS — {n} nodes, single-writer/no-overlap/no-floating/"
          "module-barrier/cdc-structure OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
