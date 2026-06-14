#!/usr/bin/env python3
"""
ps_realize.py — P4 PS realization. The PS (UG1085) blocks were extracted (ps_ports.json) but
excluded from the PL config-map. Realize each as a configurable BASE PRIMITIVE (behavior is
spec, like dff_d / the hard-block leaves) and record the PS-PL AXI seam — the connection
surface to the PL fabric. Injects the PS elements into primitives.json so assemble.py emits
them and netc.py validates. Faithful: pins are the doc-extracted signals; the AXI interfaces
are named as-is (each a full AMBA AXI4 bus, expanded at wiring time, not invented).

Output device/ps_realize.json (PS manifest) + PS leaves in primitives.json.
Usage: ps_realize.py
"""
import os, json
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
ps = json.load(open(os.path.join(HERE, "ps_ports.json")))
prims = json.load(open(os.path.join(HERE, "primitives.json")))

blocks, seam = [], []
for blk, sigs in ps.items():
    pins = [s["name"] for s in sigs]
    outs = [s["name"] for s in sigs if s.get("dir") == "out"]
    prims[blk] = {"pins": pins, "out": outs, "state": True,
                  "config": f"PS hard block — {len(sigs)} documented signals (UG1085)",
                  "_note": "physical PS-domain element (leaf, behavior=spec); see ps_ports.json"}
    blocks.append({"name": blk, "signals": len(sigs)})
    if blk == "PS_PL_AXI_INTERFACES":
        seam = [{"interface": s["name"], "dir": s.get("dir", "")} for s in sigs]

json.dump(prims, open(os.path.join(HERE, "primitives.json"), "w"), indent=2)
os.makedirs(os.path.join(ROOT, "device"), exist_ok=True)
manifest = {"domain": "PS", "source": "UG1085",
            "blocks": sorted(blocks, key=lambda b: -b["signals"]),
            "ps_pl_axi_seam": seam, "total_signals": sum(b["signals"] for b in blocks)}
json.dump(manifest, open(os.path.join(ROOT, "device", "ps_realize.json"), "w"), indent=2)

print(f"ps_realize: {len(blocks)} PS blocks realized as base primitives ({manifest['total_signals']} signals), "
      f"{len(seam)} PS-PL AXI interfaces -> device/ps_realize.json + primitives.json")
for b in manifest["blocks"]: print(f"   {b['name']:34s} {b['signals']} signals")
