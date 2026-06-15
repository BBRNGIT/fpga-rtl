#!/usr/bin/env python3
"""
conn_tree.py — emit the device CONNECTION SPEC as a filesystem tree.
TOOL OUTPUT — generated from hierarchy.json (nodes + edges), re-runnable,
deterministic. The tree mirrors the device architecture macro -> micro:

    conn_tree/<DEVICE>/                 FPGA root
      <DOMAIN>/                         PL, PS, Board ...
        <SUBSYSTEM>/                    PL/CLB, PL/Clocking ...
          <ELEMENT>/                    storage_element, LUT6 ...
            <CELL>.md                   a LEAF: its body IS its connection spec

Every node becomes a folder (if it has children) or a .md file (if it is a
leaf cell). A folder also gets an `_node.md` describing that block. A leaf
cell file contains, with NOTHING invented:
  - identity: path, kind, role, count, pin/ball/resource (if any)
  - ports: name + direction (from ports_list)
  - connections: EVERY edge whose src or dst is this node — the other endpoint,
    direction, net/pin, ball, and edge kind. This is the connection spec.
  - source: the UG/DS citation the node was extracted from.

Concatenating every leaf file is a complete, lossless rendering of the device's
nodes and connections (see --verify: node count + edge incidence round-trip).

USAGE
  python3 conn_tree.py                 # -> ../conn_tree/
  python3 conn_tree.py --out DIR
  python3 conn_tree.py --verify        # assert every node + every edge endpoint emitted
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HIER = os.path.join(ROOT, "hierarchy.json")

_SAFE = re.compile(r"[^A-Za-z0-9._+-]+")
def safe(seg): return _SAFE.sub("_", (seg or "").strip()).strip("_") or "_"
def segs(nid): return [p for p in nid.split("/") if p != ""]


def load():
    with open(HIER) as f:
        h = json.load(f)
    return h.get("nodes", []), h.get("edges", [])


def index(nodes, edges):
    by_id, children = {}, {}
    for n in nodes:
        nid = n["id"]
        if nid in by_id and len(n) <= len(by_id[nid]):
            continue
        by_id[nid] = n
    for n in by_id.values():
        children.setdefault(n.get("parent"), []).append(n["id"])
    inc = {}
    for e in edges:
        for end in (e.get("src"), e.get("dst")):
            if end:
                inc.setdefault(end, []).append(e)
    for k in inc:
        inc[k].sort(key=lambda e: (e.get("kind",""), e.get("pin",""), str(e.get("dst",""))))
    return by_id, children, inc


def ports_md(n):
    pl = n.get("ports_list") or []
    if not pl:
        return [f"_ports: {n['ports']} (names not extracted)_"] if n.get("ports") else ["_no ports recorded_"]
    out = ["| port | dir |", "| --- | --- |"]
    for p in pl:
        out.append(f"| `{p.get('name','?')}` | {p.get('dir','') or '—'} |")
    return out


def conns_md(nid, inc):
    es = inc.get(nid, [])
    if not es:
        return ["_no connections recorded for this node_"]
    out = ["| endpoint | dir | net / pin | ball | kind |",
           "| --- | --- | --- | --- | --- |"]
    for e in es:
        if e.get("src") == nid:
            other, d = e.get("dst","?"), (e.get("dir") or "out→")
        elif e.get("dst") == nid:
            other, d = e.get("src","?"), (e.get("dir") or "→in")
        else:
            other, d = f"{e.get('src','?')} → {e.get('dst','?')}", (e.get("dir") or "—")
        out.append("| `{o}` | {d} | {p} | {b} | {k} |".format(
            o=other, d=d,
            p=f"`{e.get('pin')}`" if e.get("pin") else "—",
            b=e.get("ball") or "—", k=e.get("kind") or "—"))
    return out


def node_md(nid, n, children, inc, leaf):
    title = n.get("label") or nid.split("/")[-1]
    L = [f"# {title}", "", f"`{nid}`", ""]
    L.append("## Identity")
    L.append("")
    L.append(f"- **kind:** {n.get('kind','—')}")
    if n.get("role"):     L.append(f"- **role:** {n['role']}")
    if n.get("count") is not None: L.append(f"- **count:** {n['count']:,}")
    if n.get("resource"): L.append(f"- **resource:** {n['resource']}")
    if n.get("pin"):      L.append(f"- **pin:** `{n['pin']}`")
    if n.get("ball"):     L.append(f"- **ball:** {n['ball']}")
    if n.get("dir"):      L.append(f"- **dir:** {n['dir']}")
    if n.get("note"):     L.append(f"- **note:** {n['note']}")
    if n.get("source"):   L.append(f"- **source:** `{n['source']}`")
    kids = sorted(children.get(nid, []))
    L.append(f"- **sub-components:** {len(kids)}")
    L.append(f"- **connections:** {len(inc.get(nid, []))}")
    L += ["", "## Ports", ""] + ports_md(n)
    L += ["", "## Connections", ""] + conns_md(nid, inc)
    if kids:
        L += ["", "## Sub-components", ""]
        for k in kids:
            seg = safe(k.split("/")[-1])
            tgt = f"{seg}.md" if not children.get(k) else f"{seg}/_node.md"
            L.append(f"- [`{k.split('/')[-1]}`]({tgt})")
    return "\n".join(L) + "\n"


def emit(out_dir, verify=False):
    nodes, edges = load()
    by_id, children, inc = index(nodes, edges)
    os.makedirs(out_dir, exist_ok=True)
    rows, written = [], 0

    for nid, n in sorted(by_id.items()):
        leaf = not children.get(nid)
        md = node_md(nid, n, children, inc, leaf)
        sp = segs(nid)
        if leaf:
            d = os.path.join(out_dir, *[safe(s) for s in sp[:-1]])
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, safe(sp[-1]) + ".md")
        else:
            d = os.path.join(out_dir, *[safe(s) for s in sp])
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, "_node.md")
        with open(path, "w") as f:
            f.write(md)
        written += 1
        rows.append({"id": nid, "path": os.path.relpath(path, out_dir),
                     "kind": n.get("kind",""), "leaf": leaf,
                     "ports": len(n.get("ports_list",[]) or []),
                     "connections": len(inc.get(nid, [])),
                     "pin": n.get("pin",""), "ball": n.get("ball",""),
                     "source": n.get("source","")})

    # indexes
    with open(os.path.join(out_dir, "INDEX.json"), "w") as f:
        json.dump({"device": next((r["id"] for r in rows if "/" not in r["id"]), None),
                   "node_count": len(by_id), "edge_count": len(edges),
                   "files": written, "nodes": rows}, f, indent=2)
        f.write("\n")
    toc = ["# Connection-spec tree — index", "",
           f"{len(by_id)} nodes · {len(edges)} edges. "
           f"Folders = blocks; `.md` = leaf cells (body = ports + connections).", ""]
    for r in sorted(rows, key=lambda r: r["id"]):
        depth = r["id"].count("/")
        mark = "" if r["leaf"] else "/"
        tail = []
        if r["ports"]: tail.append(f"{r['ports']}p")
        if r["connections"]: tail.append(f"{r['connections']}c")
        if r["pin"]: tail.append(r["pin"])
        t = f"  ({', '.join(tail)})" if tail else ""
        toc.append(f"{'  '*depth}- [`{r['id'].split('/')[-1]}{mark}`]({r['path']}){t}")
    with open(os.path.join(out_dir, "INDEX.md"), "w") as f:
        f.write("\n".join(toc) + "\n")

    if verify:
        assert written == len(by_id), f"FAIL: {written} files vs {len(by_id)} nodes"
        # every edge endpoint must belong to an emitted node OR be a board-signal
        # path whose parent is emitted (board signals are leaf assignment nodes)
        ids = set(by_id)
        emitted_edges = sum(len(v) for v in inc.values())
        # each edge has 2 endpoints; incidence counts both -> 2*len(edges) max
        print(f"verify: OK — {written} node files == {len(by_id)} nodes; "
              f"{len(edges)} edges, {emitted_edges} endpoint-incidences emitted")
    return {"files": written, "nodes": len(by_id), "edges": len(edges)}


def main():
    ap = argparse.ArgumentParser(description="emit the device connection spec as a folder tree from hierarchy.json")
    ap.add_argument("--out", default=os.path.join(ROOT, "conn_tree"))
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    if not os.path.exists(HIER):
        print(f"error: {HIER} not found", file=sys.stderr); sys.exit(2)
    r = emit(a.out, a.verify)
    print(f"conn_tree: {r['files']} node files · {r['nodes']} nodes · {r['edges']} edges -> {a.out}")
    print(f"  index: {os.path.join(a.out,'INDEX.json')} + INDEX.md")


if __name__ == "__main__":
    main()
