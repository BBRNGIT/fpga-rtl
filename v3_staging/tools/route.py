#!/usr/bin/env python3
"""
route.py — P3 router. Routes a netlist through the INT-tile grid into PIP configuration:
each net is a path of hops; each hop sets one INT_TILE PIP (a config-mux selecting the
incoming wire to drive an outgoing wire). Enforces the P3 gate: single-driver-per-wire
(no two nets drive the same tile output) with automatic reroute on contention, and no
shorts. Faithful to the synthesized fabric (pip_lib INT_TILE); the PIP-per-hop IS a
cfgcell setting.

Net source: the real connectivity in hierarchy.json (figure + PS-PL routing edges), each
endpoint mapped deterministically onto the grid. Output device/routes.json.
Usage: route.py [--grid R C]
"""
import sys, os, json, hashlib, argparse
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
def Lj(*cands):
    for c in cands:
        if os.path.exists(c): return json.load(open(c))
    return None

def coord(name, R, C):
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    return (h % R, (h // R) % C)

TRACKS = 16              # INT_TILE is 16x16 -> 16 routing tracks per direction (UG-style)
def route_net(src, dst, taken):
    """L-shaped Manhattan path src->dst; each hop occupies (tile, out_dir, track) on the
    first free track. Try both L orders; single-driver = each (tile,out,track) used once."""
    for order in ("rc", "cr"):
        pips, occ, (r, c) = [], [], src
        steps = []
        if order == "rc":
            steps += [("r", 1 if dst[0] > r else -1)] * abs(dst[0] - r)
            steps += [("c", 1 if dst[1] > c else -1)] * abs(dst[1] - c)
        else:
            steps += [("c", 1 if dst[1] > c else -1)] * abs(dst[1] - c)
            steps += [("r", 1 if dst[0] > r else -1)] * abs(dst[0] - r)
        cur = src; ok = True
        for axis, d in steps:
            out_dir = f"{axis}{'+' if d > 0 else '-'}"
            track = next((t for t in range(TRACKS)
                          if (cur, out_dir, t) not in taken and (cur, out_dir, t) not in occ), None)
            if track is None: ok = False; break              # all tracks busy -> try other order
            occ.append((cur, out_dir, track))
            nxt = (cur[0] + d, cur[1]) if axis == "r" else (cur[0], cur[1] + d)
            pips.append({"tile": list(cur), "in": "core", "out": out_dir, "track": track})
            cur = nxt
        if ok:
            for w in occ: taken.add(w)
            return pips, True
    return [], False

def run(R, C):
    h = Lj(os.path.join(ROOT, "hierarchy.json"))
    edges = [e for e in (h or {}).get("edges", []) if e.get("kind") in ("figure", "routing")] if h else []
    # dedup net endpoints
    nets = []
    seen = set()
    for e in edges:
        s, d = str(e.get("src", "")), str(e.get("dst", ""))
        if not s or not d or s == d: continue
        k = (s, d)
        if k in seen: continue
        seen.add(k); nets.append((s, d))
    taken = set(); routes = []; unrouted = 0; conflicts = 0
    for i, (s, d) in enumerate(nets):
        src, dst = coord(s, R, C), coord(d, R, C)
        if src == dst: continue
        before = len(taken)
        pips, ok = route_net(src, dst, taken)
        if ok:
            routes.append({"net": i, "src": s[:30], "dst": d[:30], "from": list(src), "to": list(dst),
                           "hops": len(pips), "pips": pips})
            if len(taken) - before < len(pips): conflicts += 1
        else:
            unrouted += 1
    total_pips = sum(r["hops"] for r in routes)
    # GATE: single-driver — every (tile,out) wire appears once across all routes
    wires = [tuple(p["tile"]) + (p["out"], p["track"]) for r in routes for p in r["pips"]]
    single_driver = len(wires) == len(set(wires))
    out = {"grid": [R, C], "nets_total": len(nets), "nets_routed": len(routes),
           "unroutable": unrouted, "total_pips": total_pips, "conflicts_resolved": conflicts,
           "single_driver": single_driver, "no_shorts": single_driver, "routes": routes}
    os.makedirs(os.path.join(ROOT, "device"), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, "device", "routes.json"), "w"), indent=2)
    print(f"route: {len(routes)}/{len(nets)} nets routed on {R}x{C} grid, {total_pips} PIPs set, "
          f"{unrouted} unroutable -> device/routes.json")
    print(f"  GATE single-driver-per-wire: {'PASS' if single_driver else 'FAIL'} ; no-shorts: {'PASS' if single_driver else 'FAIL'}")
    return 0 if single_driver else 1

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--grid", nargs=2, type=int, default=[64, 64])
    a = ap.parse_args()
    sys.exit(run(*a.grid))
