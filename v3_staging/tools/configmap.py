#!/usr/bin/env python3
"""
configmap.py — P1: map EVERY ported catalogue entry onto a physical fabric element and
realize the elements. Two element kinds:
  - DECOMPOSED (CLB): storage_element / LUT6 / CARRY8 / MUXF7-9 — realized by phys_lib.py
    builders; the catalogue families (FDRE/FDSE/…, LUT1-6/RAM*/SRL*, MUXF*) are CONFIGS.
  - LEAF (hard blocks): RAMB/URAM/DSP/transceiver/IO/clock/config — distinct physical
    elements (NOT config-variants of each other). Realized as configurable BASE PRIMITIVES
    (behavior is spec, like dff_d), interface = the documented ports. Memory FIFO modes fold
    into their RAM element (a documented config). "Deeper where documented" refinement of a
    leaf into gates is a later pass; a faithful leaf + config is the P1 floor.

Outputs configmap.json (the full map) and INJECTS leaf elements into primitives.json so
assemble.py emits them and netc.py validates the whole library. Faithful: grouping is the
doc's (UG574 CLB folding, UG573 FIFO=BRAM mode); ports are extracted; nothing invented.
Usage: configmap.py
"""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
cat = json.load(open(os.path.join(HERE, "catalog.json")))
phys = json.load(open(os.path.join(HERE, "phys.json")))
res_of = {m["primitive"]: m["resource"] for m in phys["prim_resource_map"]}

DECOMP = {"storage_element", "LUT6", "CARRY8", "MUXF7", "MUXF8", "MUXF9"}  # realized by phys_lib/atom

def element_of(name, v):
    n = name.upper(); g = v.get("group", "")
    if g == "PS" or v.get("note"): return None                # PS (P4) / doc-pointer hard-IP
    if re.match(r"GT[HY]E3", n): return None                  # UltraScale E3 — not in this part
    # --- CLB: config-folded onto the 6 physical elements ---
    if re.match(r"FD|LD", n): return "storage_element"
    if re.match(r"(LUT\d|CFGLUT|SRL|RAM\d)", n): return "LUT6"
    if re.match(r"CARRY", n): return "CARRY8"
    if n in ("MUXF7", "MUXF8", "MUXF9"): return n
    # --- Memory: FIFO modes fold into the BRAM element (UG573) ---
    if re.match(r"(RAMB36|FIFO36)", n): return "RAMB36E2"
    if re.match(r"(RAMB18|FIFO18)", n): return "RAMB18E2"
    if re.match(r"URAM", n): return "URAM288"
    # --- everything else: the hard block IS its own physical element (leaf) ---
    return name

def config_of(name, v, el):
    ports = {p["name"] for p in v.get("ports", [])}
    cfg = {"init": next((p["default"] for p in v.get("params", []) if p["name"] == "INIT"), None),
           "inverts": [p["name"] for p in v.get("params", []) if p["name"].startswith("IS_")]}
    if el == "storage_element":
        cfg["mode"] = "latch" if name.upper().startswith("LD") else "flip_flop"
        cfg["control"] = sorted({{"R":"sync_reset","S":"sync_set","CLR":"async_clear",
                                   "PRE":"async_preset","G":"latch_gate"}[c] for c in
                                  ("R","S","CLR","PRE","G") if c in ports})
    elif el == "LUT6":
        cfg["mode"] = ("dist_ram" if name.upper().startswith("RAM") else
                       "srl" if name.upper().startswith("SRL") else
                       "reconfig" if name.upper().startswith("CFGLUT") else "logic")
        if res_of.get(name): cfg["resource"] = res_of[name]
        m = re.match(r"LUT(\d)", name.upper()); cfg["inputs"] = int(m.group(1)) if m else None
    elif el in ("RAMB36E2", "RAMB18E2"):
        cfg["mode"] = "fifo" if name.upper().startswith("FIFO") else "ram"
    return cfg

elements = {}
excluded = []
for name in sorted(cat):
    v = cat[name]
    if not v.get("ports"): continue
    el = element_of(name, v)
    if el is None:
        excluded.append(name); continue
    e = elements.setdefault(el, {"element": el, "ports": {}, "members": [], "configs": {},
                                 "kind": "decomposed" if el in DECOMP else "leaf",
                                 "subsystem": v.get("group", "")})
    e["members"].append(name); e["configs"][name] = config_of(name, v, el)
    for p in v["ports"]: e["ports"].setdefault(p["name"], p)

out = {el: {"element": el, "kind": d["kind"], "subsystem": d["subsystem"],
            "ports": sorted(d["ports"].values(), key=lambda p: p["name"]),
            "members": sorted(d["members"]), "configs": d["configs"]} for el, d in elements.items()}
json.dump(out, open(os.path.join(HERE, "configmap.json"), "w"), indent=2)

# inject LEAF elements into primitives.json as configurable base primitives (behavior is spec)
prims = json.load(open(os.path.join(HERE, "primitives.json")))
added = 0
for el, d in out.items():
    if d["kind"] == "decomposed": continue                    # CLB handled by phys_lib / storage_element
    pins = [p["name"] for p in d["ports"]]
    outs = [p["name"] for p in d["ports"] if p["dir"] == "out"]
    prims[el] = {"pins": pins, "out": outs, "state": True,
                 "config": f"configs: {', '.join(d['members'][:8])}",
                 "_note": f"physical {d['subsystem']} element (leaf, behavior=spec); see configmap.json"}
    added += 1
json.dump(prims, open(os.path.join(HERE, "primitives.json"), "w"), indent=2)

mapped = sum(len(d["members"]) for d in out.values())
dec = sum(1 for d in out.values() if d["kind"] == "decomposed")
print(f"configmap: {mapped} catalogue entries -> {len(out)} physical elements "
      f"({dec} decomposed CLB + {len(out)-dec} leaf), {added} leaf primitives injected -> primitives.json")
print(f"  excluded (E3/PS/hard-IP-doc-pointer): {len(excluded)} -> {excluded[:8]}{'…' if len(excluded)>8 else ''}")
import collections
bysub = collections.Counter(d["subsystem"] for d in out.values())
print("  physical elements by subsystem:", dict(bysub))
