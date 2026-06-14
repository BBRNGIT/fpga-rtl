#!/usr/bin/env python3
"""
phys.py — extract the PHYSICAL fabric element set from the architecture-guide caches
(UG574 CLB / UG573 memory / UG579 DSP / UG570 config). This is P1 layer-1: WHICH physical
elements exist, their per-slice/per-tile composition, and the doc's own primitive->resource
mapping (the seed of the config-map). Faithful — structure + counts + maps come from the
doc's tables and prose; nothing invented. The element INTERFACE is derived later by
configmap.py from the catalogue config-variants.

Output phys.json: {elements:[{name,role,per_slice,doc,page}],
                   prim_resource_map:[{primitive,resource,detail,doc,page}],
                   composition:[the slice/tile composition rows]}.
Usage: phys.py   (reads the architecture-guide caches in cache/)
"""
import json, os, re, glob
HERE = os.path.dirname(os.path.abspath(__file__)); CACHE = os.path.join(HERE, "cache")
DOCS = {"ug574": "CLB", "ug573": "Memory", "ug579": "DSP", "ug570": "Config"}

def norm(c): return re.sub(r"\s+", " ", (c or "").strip())
def low(c): return norm(c).lower()

# physical elements asserted by each guide's prose (the per-slice/tile composition is the fact)
COUNT_FACTS = [  # (regex, element, role) — count captured from group(1)
 (r"(eight|8)\s+6-input LUTs", "LUT6", "6-input LUT / distributed-RAM / SRL (SLICEM)"),
 (r"(sixteen|16)\s+flip-flops", "storage_element", "configurable FF/latch (CE, sync/async set/reset)"),
 (r"(one|two)?\s*CARRY8", "CARRY8", "carry chain"),
 (r"(MUXF7)", "MUXF7", "wide function mux"),
 (r"(MUXF8)", "MUXF8", "wide function mux"),
 (r"(MUXF9)", "MUXF9", "wide function mux"),
]
WORD = {"one":1,"two":2,"three":3,"eight":8,"sixteen":16}

def run():
    elements, pmap, comp = {}, [], []
    for cf in sorted(glob.glob(os.path.join(CACHE, "*.jsonl"))):
        stem = os.path.basename(cf).split("-")[0].split(".")[0]
        if stem not in DOCS: continue
        sub = DOCS[stem]; recs = [json.loads(l) for l in open(cf)]
        full = "\n".join(r["text"] for r in recs)
        for rx, el, role in COUNT_FACTS:
            m = re.search(rx, full, re.I)
            if m and el not in elements:
                g = (m.group(1) or "").lower()
                elements[el] = {"name": el, "subsystem": sub, "role": role,
                                "per_slice": WORD.get(g), "doc": stem}
        # tables: composition (slice|luts|flip-flops...) + primitive->resource maps
        for r in recs:
            for tb in r.get("tables", []):
                rows = tb["rows"]; hdr = [low(c) for c in rows[0]]
                if not any(hdr): continue
                hset = " ".join(hdr)
                if "primitive" in hdr and ("resource" in hset or "type" in hset or "ram size" in hset):
                    pc = hdr.index("primitive")
                    rc = next((i for i,h in enumerate(hdr) if h in ("resource","type")), None)
                    for row in rows[1:]:
                        if pc >= len(row): continue
                        prim = norm(row[pc])
                        if not re.match(r"^[A-Z][A-Z0-9_]", prim): continue
                        pmap.append({"primitive": prim.split()[0],
                                     "resource": norm(row[rc]) if rc is not None and rc < len(row) else "",
                                     "detail": " | ".join(norm(c) for c in row if c)[:120],
                                     "doc": stem, "page": r["page"]})
                if ("luts" in hset and "flip-flops" in hset) or ("slice" in hset and "luts" in hset):
                    for row in rows[1:]:
                        cells = [norm(c) for c in row if c]
                        if cells: comp.append({"row": cells, "doc": stem, "page": r["page"]})
    out = {"elements": sorted(elements.values(), key=lambda e: e["name"]),
           "prim_resource_map": pmap, "composition": comp}
    json.dump(out, open(os.path.join(HERE, "phys.json"), "w"), indent=2)
    print(f"phys: {len(out['elements'])} physical elements, {len(pmap)} primitive->resource maps, "
          f"{len(comp)} composition rows -> phys.json")
    for e in out["elements"]:
        ps = f"×{e['per_slice']}/slice" if e.get("per_slice") else ""
        print(f"   {e['name']:18s} [{e['subsystem']}] {ps:12s} {e['role']}")
    if pmap:
        print("  sample primitive->resource maps:")
        seen=set()
        for m in pmap:
            k=(m['primitive'],m['resource'])
            if k in seen: continue
            seen.add(k); print(f"     {m['primitive']:12s} -> {m['resource'][:40]}")
            if len(seen)>=8: break
    return 0

if __name__ == "__main__":
    import sys; sys.exit(run())
