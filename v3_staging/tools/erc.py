#!/usr/bin/env python3
"""
erc.py — Electrical-Rule Check (Tier 1, structural-only).
Sign-off gates C01 single-driver, C02 no-floating-input, C03 no-dangling-output.

DERIVATION: pure topology over device/device.json (the validated netlist emitted
by netc.py). No external reference value — these are structural laws. For every
block, a net is DRIVEN by an instance's output pin and CONSUMED by input pins;
pin direction comes from device.json/primitives[type].out. Nothing is asserted
by hand: drivers/loads are counted from the netlist itself.

C03 exception: a net with a driver and no internal load is only dangling if it is
ALSO not a declared block output (ports dir=out) — a block output legitimately
leaves the block. (Declared device-level outputs are handled at integration.)

Exit 0 = green, 1 = red. Read-only. Run: python3 erc.py [c01|c02|c03|all]
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
DEV = os.path.join(ROOT, "device")

def load(name):
    for base in (DEV, HERE):
        p = os.path.join(base, name)
        if os.path.exists(p):
            return json.load(open(p))
    raise FileNotFoundError(name)

def ok(m):  print(f"[erc] OK  {m}"); sys.exit(0)
def red(m): print(f"[erc] RED {m}"); sys.exit(1)

def _model():
    dev = load("device.json")
    prims = dev.get("primitives", {})
    blocks = dev.get("blocks", {})
    return prims, blocks

# global constant tie-off nets: "0"=logic low, "1"=logic high. These are driven
# by the implicit constant generators every fabric has, not floating inputs.
CONST_NETS = {"0", "1"}

def _outputs_of(prims, blocks, itype):
    """Output pin set for an instance type, resolving HIERARCHY: a primitive's
    outputs come from the primitives table; a sub-block's outputs are its block
    ports with dir=out (the same hierarchical model lower.py uses). Returns the
    set, or None if the type is unknown (neither primitive nor block)."""
    p = prims.get(itype)
    if p is not None:
        return set(p.get("out") or [])
    b = blocks.get(itype)
    if b is not None:
        return {pt["name"] for pt in b.get("ports", []) if pt.get("dir") == "out"}
    return None

def _block_nets(prims, blocks, blk):
    """Return (drivers, loads, unknown_types):
       drivers[net] = list of (ref,pin); loads[net] = list of (ref,pin).
       Constant nets ("0"/"1") are seeded as driven."""
    drivers, loads, unknown = {}, {}, []
    for inst in blk.get("insts", []):
        itype = inst.get("type"); ref = inst.get("ref")
        outs = _outputs_of(prims, blocks, itype)
        if outs is None:
            unknown.append((ref, itype)); continue
        for pin, net in (inst.get("conn") or {}).items():
            if pin in outs:
                drivers.setdefault(net, []).append((ref, pin))
            else:
                loads.setdefault(net, []).append((ref, pin))
    # a constant net ("0"/"1") is driven by the fabric's implicit tie-off ONLY
    # where it is actually consumed — so it satisfies its loads (C02) without
    # appearing as a phantom unloaded driver (C03).
    for c in CONST_NETS:
        if c in loads:
            drivers.setdefault(c, []).append(("const", c))
    return drivers, loads, unknown

def c01_single_driver():
    prims, blocks = _model()
    bad = []
    for bname, blk in blocks.items():
        drivers, _loads, _u = _block_nets(prims, blocks, blk)
        for net, ds in drivers.items():
            if len(ds) > 1:
                bad.append(f"{bname}.{net}<-{[r for r,_ in ds]}")
    red(f"C01 multi-driver nets: {bad[:6]} (+{max(0,len(bad)-6)} more)") if bad \
        else ok(f"C01 single-driver — all nets across {len(blocks)} blocks have ≤1 driver")

def c02_no_floating_input():
    prims, blocks = _model()
    bad = []
    for bname, blk in blocks.items():
        drivers, loads, _u = _block_nets(prims, blocks, blk)
        port_in = {p["name"] for p in blk.get("ports", []) if p.get("dir") == "in"}
        for net, ls in loads.items():
            # a load net must be driven by an instance OR be a block input port
            if net not in drivers and net not in port_in:
                bad.append(f"{bname}.{net}->{[r for r,_ in ls][:2]}")
    red(f"C02 floating inputs (net with load, no driver): {bad[:6]} (+{max(0,len(bad)-6)})") if bad \
        else ok(f"C02 no-floating — every consumed net is driven or is a block input")

def c03_no_dangling_output():
    prims, blocks = _model()
    bad = []
    for bname, blk in blocks.items():
        drivers, loads, _u = _block_nets(prims, blocks, blk)
        port_out = {p["name"] for p in blk.get("ports", []) if p.get("dir") == "out"}
        for net, ds in drivers.items():
            # driven net with no internal load is dangling UNLESS it's a block output
            if net not in loads and net not in port_out:
                bad.append(f"{bname}.{net}<-{[r for r,_ in ds][:2]}")
    red(f"C03 dangling outputs (driven, unloaded, not a port): {bad[:6]} (+{max(0,len(bad)-6)})") if bad \
        else ok(f"C03 no-dangling — every driver is loaded or is a block output")

CHECKS = {"c01": c01_single_driver, "c02": c02_no_floating_input, "c03": c03_no_dangling_output}

def main():
    arg = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
    if arg == "all":
        # run all; first RED exits non-zero (collect by running sequentially)
        for name in ("c01", "c02", "c03"):
            r = os.system(f"{sys.executable} {os.path.abspath(__file__)} {name}")
            if r != 0:
                sys.exit(1)
        print("[erc] OK  all ERC checks passed"); sys.exit(0)
    if arg in CHECKS:
        CHECKS[arg]()
    else:
        print(f"[erc] usage: erc.py [c01|c02|c03|all]"); sys.exit(2)

if __name__ == "__main__":
    main()
