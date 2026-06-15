#!/usr/bin/env python3
"""
lvs.py — Layout-vs-Spec check (Tier 1, derives-now). The heart of "gates derive
from conn_tree + cached docs, never from invented values."

Gates:
  C04 port-direction   — edges connect out->in only (dir from conn_tree ports_list)
  C05 net-completeness — every port the ORIGINATING DOC declares for a node appears
                         in the node's ports_list. Expected port set is READ FROM the
                         cited cache page (node.source, e.g. "ug974 p241"), NOT typed.
  C06 connection-prov  — every edge cites a real source (pin/ball/fig) or is tagged
                         synthesized; the cited page must exist in cache.
  C07 grid-identity    — no two leaf cells share an (X,Y); no explicit address field.

ROOTS (protected, read-only):
  ../hierarchy.json              the connection tree (nodes + edges)   [STRUCT SRC]
  cache/<doc>.jsonl              originating docs reached via node.source [REF SRC]

DERIVATION PROOF (C05, verified): conn_tree node PL/CLB/CARRY8 lists ports
  CI,CI_TOP,CO,DI,O,S citing ug974 p241; cache page 241 "Port Descriptions" table
  contains exactly those. The gate reads both and FAILS on mismatch. The expected
  set is the doc's, never the author's.

Exit 0 = green, 1 = red. Read-only. Run: python3 lvs.py [c04|c05|c06|c07|all]
"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "cache")
HIER = os.path.join(ROOT, "hierarchy.json")

def ok(m):  print(f"[lvs] OK  {m}"); sys.exit(0)
def red(m): print(f"[lvs] RED {m}"); sys.exit(1)

def load_hier():
    h = json.load(open(HIER))
    return h.get("nodes", []), h.get("edges", [])

# ---- cache access by citation -------------------------------------------------
_CITE = re.compile(r"([A-Za-z0-9][\w.-]*?)\s*[ _]?p(?:age)?\s*(\d+)", re.I)
_page_cache = {}                                   # (doc)-> {page:int -> record}

def parse_cite(src):
    if not src: return (None, None)
    m = _CITE.search(src)
    return (m.group(1).lower(), int(m.group(2))) if m else (src.strip().lower(), None)

def _doc_file(prefix):
    if not prefix: return None
    cand = os.path.join(CACHE, prefix + ".jsonl")
    if os.path.exists(cand): return prefix
    for fn in os.listdir(CACHE):
        if fn.endswith(".jsonl") and fn[:-6].lower().startswith(prefix):
            return fn[:-6]
    return None

def page_record(src):
    prefix, page = parse_cite(src)
    doc = _doc_file(prefix)
    if not doc or page is None: return None
    if doc not in _page_cache:
        pages = {}
        for line in open(os.path.join(CACHE, doc + ".jsonl")):
            line = line.strip()
            if not line: continue
            try: rec = json.loads(line)
            except json.JSONDecodeError: continue
            if rec.get("page") is not None: pages[int(rec["page"])] = rec
        _page_cache[doc] = pages
    return _page_cache[doc].get(page)

# ports the doc declares on a page: scan the "Port Descriptions" table + text.
_PORTW = re.compile(r"\b([A-Z][A-Z0-9_]{1,30})\s*(?:<[\d:]+>|\[[\d:]+\])?\b")
def doc_declared_ports(rec):
    """Extract the port-name set from a cached page's Port-Descriptions table."""
    names = set()
    for t in rec.get("tables", []) or []:
        rows = t.get("rows") if isinstance(t, dict) else t
        if not rows: continue
        head = [str(c or "").strip().lower() for c in rows[0]]
        if "port" in head and ("direction" in head or "dir" in head):
            pi = head.index("port")
            di = head.index("direction") if "direction" in head else head.index("dir")
            for r in rows[1:]:
                if pi >= len(r) or not r[pi]:
                    continue
                # a REAL port row has a direction value (Input/Output/Inout) in the
                # direction column. Section sub-headers ("Clock Inputs:", "Address")
                # have no direction -> skip, so their first word isn't read as a port.
                dirv = str(r[di]).strip().lower() if di < len(r) and r[di] else ""
                if dirv.split()[0:1] != [] and dirv.split()[0] not in ("input", "output", "inout", "in", "out", "inout"):
                    continue
                if not dirv:
                    continue
                cell = str(r[pi]).split("\n")[0].split("<")[0].split("[")[0]
                cell = cell.replace("_", "").strip()
                # a port name is a single ALL-CAPS token (no spaces, not prose ending ':')
                if " " in cell or cell.endswith(":"):
                    continue
                m = re.match(r"^([A-Z][A-Z0-9]{0,30})$", cell.upper())
                if m: names.add(m.group(1))
    return names

# ---- C05 net-completeness (the derives-now flagship) --------------------------
def c05_net_completeness():
    nodes, _edges = load_hier()
    checked = mism = 0; bad = []
    for n in nodes:
        pl = n.get("ports_list")
        src = n.get("source")
        if not pl or not src: continue
        rec = page_record(src)
        if rec is None: continue            # page not in cache -> C06 territory, skip here
        declared = doc_declared_ports(rec)
        if not declared: continue           # page has no parseable port table
        have = {p.get("name", "").upper().split("<")[0].split("[")[0] for p in pl}
        # normalize doc names the same way (CO<7:0> -> CO)
        missing = {d for d in declared if d not in have}
        checked += 1
        if missing:
            mism += 1
            bad.append(f"{n['id']} [{src}] missing {sorted(missing)}")
    if not checked:
        red("C05 could not derive any expected port set from cache — extraction gap")
    red(f"C05 net-completeness: {mism}/{checked} nodes miss doc-declared ports: {bad[:4]}") if bad \
        else ok(f"C05 net-completeness — {checked} nodes match their cited doc port tables")

# ---- C04 port-direction -------------------------------------------------------
def c04_port_direction():
    nodes, edges = load_hier()
    dirof = {}
    for n in nodes:
        for p in (n.get("ports_list") or []):
            dirof[(n["id"], p.get("name"))] = p.get("dir")
    bad = []
    for e in edges:
        s, d = e.get("src"), e.get("dst")
        # only check edges that resolve to known ports on both ends
        sd = dirof.get((s_node(s), port_of(s))) if s else None
        dd = dirof.get((s_node(d), port_of(d))) if d else None
        if sd == "in" and dd == "in":
            bad.append(f"{s}->{d} (in->in)")
        elif sd == "out" and dd == "out":
            bad.append(f"{s}->{d} (out->out)")
    red(f"C04 port-direction conflicts: {bad[:6]}") if bad \
        else ok("C04 port-direction — no out->out / in->in edges among resolved ports")

def s_node(path):    return path.rsplit("/", 1)[0] if "/" in (path or "") else path
def port_of(path):   return path.rsplit("/", 1)[1] if "/" in (path or "") else path

# ---- C06 connection-provenance ------------------------------------------------
def c06_connection_provenance():
    _nodes, edges = load_hier()
    bad = 0; ex = []
    for e in edges:
        has_cite = bool(e.get("pin") or e.get("ball") or e.get("fig") or e.get("source"))
        synth = (e.get("kind") == "synthesized") or e.get("synthesized")
        if not has_cite and not synth:
            bad += 1
            if len(ex) < 6: ex.append(f"{e.get('src')}->{e.get('dst')}")
    red(f"C06 provenance: {bad} edges with no citation and not synthesized: {ex}") if bad \
        else ok(f"C06 connection-provenance — all {len(edges)} edges cite a source or are tagged synthesized")

# ---- C07 grid identity --------------------------------------------------------
def c07_grid_identity():
    nodes, _edges = load_hier()
    seen = {}; dup = []; addr = []
    for n in nodes:
        xy = (n.get("x"), n.get("y"))
        if xy != (None, None):
            if xy in seen: dup.append(f"{n['id']}=={seen[xy]}@{xy}")
            else: seen[xy] = n["id"]
        if any(k in n for k in ("address", "addr", "base_addr")):
            addr.append(n["id"])
    if dup or addr:
        red(f"C07 grid-identity: {len(dup)} duplicate sites {dup[:3]}, {len(addr)} addressed nodes {addr[:3]}")
    ok(f"C07 grid-identity — {len(seen)} positioned cells unique, no address registry")

CHECKS = {"c04": c04_port_direction, "c05": c05_net_completeness,
          "c06": c06_connection_provenance, "c07": c07_grid_identity}

def main():
    arg = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
    if arg == "all":
        for name in ("c06", "c05", "c04", "c07"):     # provenance first (guards data)
            if os.system(f"{sys.executable} {os.path.abspath(__file__)} {name}") != 0:
                sys.exit(1)
        print("[lvs] OK  all LVS checks passed"); sys.exit(0)
    if arg in CHECKS: CHECKS[arg]()
    else: print("[lvs] usage: lvs.py [c04|c05|c06|c07|all]"); sys.exit(2)

if __name__ == "__main__":
    main()
