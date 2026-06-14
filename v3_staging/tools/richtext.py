#!/usr/bin/env python3
"""
richtext.py — programmatic deep-extractor for a TRM's rich tabular content.

A TRM's semantics live in highly regular tables (surveyed from the real cache):
  register defs   : [Register Name | Address | Width | Type | Reset Value | Description]
  register lists  : [Register Type | Register Name | Description] / [Register Name | Description]
  field/bit tables: [Register | Bits | Name | Description | Address] / [Bits | Name | Description]
  address maps    : [Base Address | Description]
  routing/conns   : [Name | Count | Source | Destination | Description]   <- real connectivity
This tool classifies each cached table by its header and column-indexes the rows (robust to
column order). NO agent reading — a tool does the extraction; the harness runs/observes it.
Supports --pages A-B so parallel copies can shard the doc (the orchestrator observes the
shards, then merge them with --merge).

Usage:
  richtext.py <cache.jsonl> [--pages A-B] [--out richtext[.shard].json]
  richtext.py --merge <out.json> shard1.json shard2.json ...
"""
import sys, os, re, json, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
CHAP = re.compile(r'Chapter\s+\d+:\s*([A-Z][^\n]{3,48})')

def norm(c): return (c or "").strip().lower().replace("\n", " ")
def repair(s):  # UG1085 renders underscores in identifiers as spaces
    s = (s or "").split("\n")[0].strip()
    return re.sub(r'\s+', "_", s) if re.match(r'^[A-Za-z][A-Za-z0-9 ]*$', s) and " " in s and s.isupper() else s.strip()

def col(hdr, *names):
    for n in names:
        for i, h in enumerate(hdr):
            if h == n: return i
    for n in names:                                          # fall back to substring
        for i, h in enumerate(hdr):
            if n in h: return i
    return None

def classify(hdr):
    has = lambda *n: col(hdr, *n) is not None
    if has("drp address") and has("attribute name"):
        return "drp"                                         # transceiver DRP attribute map
    if has("attribute") and has("type") and has("description"):
        return "attributes"                                  # transceiver config attributes
    if has("task") and (has("register") or has("register name")) and has("bits"):
        return "sequences"                                   # register programming flows
    if has("register name") and has("address", "register offset") and has("description"):
        return "registers"
    if has("base address") and has("description"):
        return "address_map"
    if has("source") and has("destination"):
        return "routing"
    if has("bits") and has("name") and has("description"):
        return "fields"
    if has("register name") and has("description"):
        return "register_list"
    return None

def cell(row, i):
    return re.sub(r'\s+', " ", (row[i] or "").replace("\n", " ").strip()) if (i is not None and i < len(row)) else ""

def extract(cache, pages):
    recs = [json.loads(l) for l in open(cache)]
    if pages:
        a, b = (int(x) for x in pages.split("-")); recs = [r for r in recs if a <= r["page"] <= b]
    out = {k: [] for k in ("registers", "register_list", "fields", "address_map", "routing", "sequences", "drp", "attributes")}
    chapter = "?"
    for r in recs:
        m = CHAP.search(r["text"])
        if m: chapter = m.group(1).strip()
        for tb in r.get("tables", []):
            rows = tb["rows"]
            if not rows: continue
            hdr = [norm(c) for c in rows[0]]
            fam = classify(hdr)
            if not fam: continue
            ci = {nm: col(hdr, nm) for nm in
                  ("register name", "register type", "register", "register field", "register offset",
                   "address", "width", "type", "reset value", "bits", "name", "description",
                   "base address", "count", "source", "destination", "value", "task",
                   "drp address", "drp bits", "r/w", "attribute name", "attribute bits", "attribute", "drp encoding")}
            for row in rows[1:]:
                if fam == "registers":
                    nm = repair(cell(row, ci["register name"]))
                    if not nm or len(nm) < 2: continue
                    out["registers"].append({"name": nm, "address": cell(row, ci["address"] or ci["register offset"]),
                        "width": cell(row, ci["width"]), "type": cell(row, ci["type"]),
                        "reset_value": cell(row, ci["reset value"]), "description": cell(row, ci["description"]),
                        "block": chapter, "page": r["page"]})
                elif fam == "register_list":
                    nm = repair(cell(row, ci["register name"]))
                    if not nm or len(nm) < 2: continue
                    out["register_list"].append({"name": nm, "type": cell(row, ci["register type"]),
                        "description": cell(row, ci["description"]), "block": chapter, "page": r["page"]})
                elif fam == "fields":
                    nm = cell(row, ci["name"]); bits = cell(row, ci["bits"])
                    if not nm and not bits: continue
                    out["fields"].append({"register": repair(cell(row, ci["register"])), "bits": bits,
                        "name": nm, "description": cell(row, ci["description"]),
                        "block": chapter, "page": r["page"]})
                elif fam == "address_map":
                    ba = cell(row, ci["base address"])
                    if not re.search(r'0x|[0-9A-Fa-f]{4,}', ba): continue
                    out["address_map"].append({"base_address": ba, "description": cell(row, ci["description"]),
                        "block": chapter, "page": r["page"]})
                elif fam == "routing":
                    src = cell(row, ci["source"]); dst = cell(row, ci["destination"])
                    if not src and not dst: continue
                    out["routing"].append({"name": cell(row, ci["name"]), "count": cell(row, ci["count"]),
                        "source": src, "destination": dst, "description": cell(row, ci["description"]),
                        "block": chapter, "page": r["page"]})
                elif fam == "drp":
                    at = repair(cell(row, ci["attribute name"]))
                    if not at: continue
                    out["drp"].append({"attribute": at, "drp_address": cell(row, ci["drp address"]),
                        "drp_bits": cell(row, ci["drp bits"]), "rw": cell(row, ci["r/w"]),
                        "attribute_bits": cell(row, ci["attribute bits"]), "encoding": cell(row, ci["drp encoding"]),
                        "block": chapter, "page": r["page"]})
                elif fam == "attributes":
                    at = repair(cell(row, ci["attribute"]))
                    if not at or at.lower() == "attribute": continue
                    out["attributes"].append({"name": at, "type": cell(row, ci["type"]),
                        "description": cell(row, ci["description"]), "block": chapter, "page": r["page"]})
                elif fam == "sequences":
                    reg = repair(cell(row, ci["register"] if ci["register"] is not None else ci["register name"]))
                    fld = cell(row, ci["register field"]); val = cell(row, ci["value"])
                    if not reg and not fld: continue
                    out["sequences"].append({"task": cell(row, ci["task"]), "register": reg,
                        "field": fld, "offset": cell(row, ci["register offset"]), "bits": cell(row, ci["bits"]),
                        "value": val, "block": chapter, "page": r["page"]})
    return out

def report(out, dst):
    json.dump(out, open(dst, "w"), indent=2)
    print(f"richtext: -> {dst}")
    for k, v in out.items(): print(f"   {len(v):5d}  {k}")

def run(cache, pages, outp):
    out = extract(cache, pages)
    report(out, outp)
    return 0

def merge(dst, shards):
    out = {}
    for s in shards:
        d = json.load(open(s))
        for k, v in d.items(): out.setdefault(k, []).extend(v)
    # dedup registers/lists by name (keep first); keep fields/routing as-is (row-level)
    for k in ("registers", "register_list"):
        seen = {}; [seen.setdefault(x["name"], x) for x in out.get(k, [])]
        out[k] = sorted(seen.values(), key=lambda x: x["name"])
    report(out, dst)
    return 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cache", nargs="?"); ap.add_argument("--pages", default=None)
    ap.add_argument("--out", default=os.path.join(HERE, "ug1085_richtext.json"))
    ap.add_argument("--merge", default=None); ap.add_argument("shards", nargs="*")
    a = ap.parse_args()
    if a.merge:                                              # all positionals are shards in merge mode
        sys.exit(merge(a.merge, ([a.cache] if a.cache else []) + a.shards))
    sys.exit(run(a.cache, a.pages, a.out))
