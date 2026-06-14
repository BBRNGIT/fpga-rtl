#!/usr/bin/env python3
"""
configmap.py — P1 layer-3: derive the catalogue -> (physical element, configuration) map.

Joins catalog.json (UNISIM entries: ports + params) with phys.json (the physical element set
+ UG574 primitive->resource maps). For each catalogue entry it assigns a physical element and
derives the CONFIG from documented behavior (the variant's own control ports + params), NOT a
guess: e.g. the storage element is one element; FDRE carries port R (sync reset), FDSE carries
S (sync set), FDCE carries CLR (async clear), FDPE carries PRE (async preset) — the config IS
which documented control the variant exposes. The element INTERFACE = union of its variants'
ports. Deriving from documented behavior is legitimate (Law #7); fabricating a fact is not.

Output configmap.json: {<element>: {ports:[union], members:[...], configs:{<prim>:{control,params,...}}}}.
Usage: configmap.py
"""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
cat = json.load(open(os.path.join(HERE, "catalog.json")))
phys = json.load(open(os.path.join(HERE, "phys.json")))
res_of = {m["primitive"]: m["resource"] for m in phys["prim_resource_map"]}

# element membership (UG574-grounded): which physical element each catalogue family configures
def element_of(name, v):
    n = name.upper(); g = v.get("group", "")
    if g == "PS" or v.get("note"): return None                # PS / hard-IP handled elsewhere
    if re.match(r"FD|LD", n): return "storage_element"
    if re.match(r"LUT\d|CFGLUT|SRL", n): return "LUT6"
    if re.match(r"RAM\d", n): return "LUT6"                    # distributed RAM = LUT6 in SLICEM
    if re.match(r"CARRY", n): return "CARRY8"
    if re.match(r"MUXF", n): return n if n in ("MUXF7","MUXF8","MUXF9") else "MUXF7"
    return None                                                # non-CLB: deferred to other arch docs

# documented control that distinguishes a storage-element / LUT config (read from its ports)
CTRL = {"R":"sync_reset","S":"sync_set","CLR":"async_clear","PRE":"async_preset","G":"latch_gate"}
def config_of(name, v, el):
    portnames = {p["name"] for p in v.get("ports", [])}
    cfg = {"init": next((p["default"] for p in v.get("params", []) if p["name"]=="INIT"), None),
           "inverts": [p["name"] for p in v.get("params", []) if p["name"].startswith("IS_")]}
    if el == "storage_element":
        cfg["mode"] = "latch" if name.upper().startswith("LD") else "flip_flop"
        cfg["control"] = sorted({CTRL[c] for c in CTRL if c in portnames})
    elif el == "LUT6":
        cfg["mode"] = ("dist_ram" if name.upper().startswith("RAM") else
                       "srl" if name.upper().startswith("SRL") else
                       "reconfig" if name.upper().startswith("CFGLUT") else "logic")
        if res_of.get(name): cfg["resource"] = res_of[name]   # UG574 doc map (Single/Dual-port…)
        m = re.match(r"LUT(\d)", name.upper())
        if m: cfg["inputs"] = int(m.group(1))
    return cfg

elements = {}
for name in sorted(cat):
    v = cat[name]
    if not v.get("ports"): continue
    el = element_of(name, v)
    if not el: continue
    e = elements.setdefault(el, {"element": el, "ports": {}, "members": [], "configs": {}})
    e["members"].append(name)
    e["configs"][name] = config_of(name, v, el)
    for p in v["ports"]:                                       # element interface = union of variants
        e["ports"].setdefault(p["name"], p)
out = {el: {"element": el, "ports": sorted(d["ports"].values(), key=lambda p: p["name"]),
            "members": sorted(d["members"]), "configs": d["configs"]} for el, d in elements.items()}
json.dump(out, open(os.path.join(HERE, "configmap.json"), "w"), indent=2)

mapped = sum(len(d["members"]) for d in out.values())
print(f"configmap: {mapped} catalogue entries mapped onto {len(out)} physical elements -> configmap.json")
for el, d in sorted(out.items()):
    print(f"   {el:18s} {len(d['ports']):3d} ports (union)  <- {len(d['members'])} configs: {', '.join(d['members'][:6])}{'…' if len(d['members'])>6 else ''}")
# show the storage_element config derivation (the FDRE/FDSE/FDCE/FDPE proof)
if "storage_element" in out:
    print("\n  storage_element configs (one element, documented controls differ):")
    for nm, c in list(out["storage_element"]["configs"].items())[:6]:
        print(f"     {nm:6s} mode={c.get('mode'):9s} control={c.get('control')}")
