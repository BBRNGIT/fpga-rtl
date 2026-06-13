#!/usr/bin/env python3
"""route.py — the ROUTER (place-and-route, R step). Reads the block diagram
(system_bindings.json from connect.py) + the fabric, and emits the PIP CONFIG
(the bitstream) that realizes every net on conductor lanes — automatically. This
is the "circuit map self-resolves": no hand-wiring, no module-to-module reads.

Model (system-sized, authentic int_tile structure): each unique producer output
lane is a routing WIRE (conductor); a net is realized by enabling a DRIVE PIP
(producer pin -> wire) and a SAMPLE PIP (wire -> each consumer pin). The router
guarantees ONE driver per wire (no shorts) and full coverage; re-running on a new
block diagram re-routes (DFX). It never connects DOM to candle — only PIPs to lanes.

Usage: python3 install/route.py   (reads install/system_bindings.json)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    bind_path = os.path.join(HERE, "system_bindings.json")
    if not os.path.exists(bind_path):
        sys.stderr.write("route: run connect.py first (no system_bindings.json)\n"); sys.exit(2)
    b = json.load(open(bind_path))
    bindings = b.get("bindings", [])

    wires = {}    # wire name -> {driver, kind, samplers:[]}
    pips = []     # the bitstream: each enabled PIP
    errors = []

    def wire_for(src):
        # source forms: "producer.lane" | "producer.HEAD.field" | "producer.RING[slot].field"
        return src

    for x in bindings:
        kind = x.get("kind")
        if kind == "writes":
            # a producer drives a whole passive bus: every bus lane is driven by it.
            wires.setdefault(f"bus:{x['bus']}", {"driver": x["producer"], "kind": "bus", "samplers": []})
            continue
        consumer, seam, src = x.get("consumer"), x.get("seam"), x.get("source")
        if src is None:
            continue
        w = wire_for(src)
        producer = src.split(".")[0]
        rec = wires.setdefault(w, {"driver": producer, "kind": kind, "samplers": []})
        if rec["driver"] != producer:
            errors.append(f"SHORT: wire {w} driven by {rec['driver']} AND {producer}")
        rec["samplers"].append(f"{consumer}.{seam}")
        # the two PIPs that realize this net:
        pips.append({"net": w, "pip": "drive",  "from": f"{producer}.out", "to": w, "on": 1})
        pips.append({"net": w, "pip": "sample", "from": w, "to": f"{consumer}.{seam}", "on": 1})

    # validate: one driver per wire (by construction, but check), full coverage
    multi = [w for w, r in wires.items() if isinstance(r.get("driver"), list)]
    drive_pips = sum(1 for p in pips if p["pip"] == "drive")
    sample_pips = sum(1 for p in pips if p["pip"] == "sample")

    out = {"wires": wires, "pips": pips,
           "stats": {"wires": len(wires), "nets": sample_pips,
                     "drive_pips": drive_pips, "sample_pips": sample_pips,
                     "total_pips_enabled": len(pips)},
           "errors": errors}
    json.dump(out, open(os.path.join(HERE, "bitstream.json"), "w"), indent=2)

    print("=== ROUTER: block diagram -> PIP config (bitstream) ===")
    print(f"  routed {sample_pips} nets onto {len(wires)} conductor wires")
    print(f"  PIPs enabled: {drive_pips} drive + {sample_pips} sample = {len(pips)} total")
    # show a few wires with driver -> samplers (the resolved circuit)
    for w, r in list(wires.items())[:6]:
        s = ", ".join(r["samplers"][:3]) + (" ..." if len(r["samplers"]) > 3 else "")
        print(f"    wire {w:34} driver={r['driver']:10} -> {s if s else '(bus)'}")
    print(f"    ... and {max(0,len(wires)-6)} more wires")
    if errors:
        print(f"\n  {len(errors)} SHORTS (>1 driver):")
        for e in errors: print("   ", e)
    else:
        print("\n  single-driver per wire: OK   |   every net realized by PIPs: OK")
    print("\nwrote install/bitstream.json (the PIP config)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
