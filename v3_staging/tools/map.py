#!/usr/bin/env python3
"""
map.py — P5 mapping framework: LOAD a design onto the cast blank container. Places each
block at a grid (X,Y) — the coordinate IS its identity (no registry, no allocation) — and
routes the inter-block connectivity through the INT-tile fabric via route.py. Emits the
loadmap (placements + PIP configuration = the bitstream surface). The "design payload" is a
parameter; with none locked yet, it loads the device's OWN extracted block diagram
(hierarchy.json blocks+edges) as the representative system — faithful, not invented.

Output device/loadmap.json. Usage: map.py [--grid R C]
"""
import sys, os, json, argparse
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import route  # reuse coord() + route_net()

def run(R, C):
    h = json.load(open(os.path.join(ROOT, "hierarchy.json")))
    # design = placeable blocks (configs/elements/PS blocks); place each at a grid coord
    blocks = [n["id"].split("/")[-1] for n in h["nodes"] if n["kind"] in ("config", "element", "subsystem")]
    blocks = sorted(set(blocks))
    placements = {b: list(route.coord(b, R, C)) for b in blocks}
    # route the inter-block edges between placed blocks
    edges = [e for e in h["edges"] if e.get("kind") in ("figure", "routing")]
    taken, routes, unrouted = set(), [], 0
    for i, e in enumerate(edges):
        s, d = str(e.get("src", "")).split("/")[-1], str(e.get("dst", "")).split("/")[-1]
        src = placements.get(s) or route.coord(s, R, C)
        dst = placements.get(d) or route.coord(d, R, C)
        if tuple(src) == tuple(dst): continue
        pips, ok = route.route_net(tuple(src), tuple(dst), taken)
        if ok: routes.append({"net": i, "from": list(src), "to": list(dst), "hops": len(pips)})
        else: unrouted += 1
    wires = sum(r["hops"] for r in routes)
    single_driver = len(taken) == sum(r["hops"] for r in routes)  # each wire used once
    out = {"grid": [R, C], "design": "device block diagram (hierarchy.json)",
           "placed": len(placements), "nets_routed": len(routes), "unroutable": unrouted,
           "pip_bits": wires, "single_driver": single_driver,
           "bitstream_summary": {"placements": len(placements), "pips_set": wires},
           "placements": placements, "routes": routes[:50]}
    os.makedirs(os.path.join(ROOT, "device"), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, "device", "loadmap.json"), "w"), indent=2)
    print(f"map: loaded {len(placements)} blocks at grid positions, routed {len(routes)} nets "
          f"({wires} PIP bits), {unrouted} unroutable -> device/loadmap.json")
    print(f"  GATE single-driver: {'PASS' if single_driver else 'FAIL'}")
    return 0 if single_driver else 1

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--grid", nargs=2, type=int, default=[128, 128])
    a = ap.parse_args()
    sys.exit(run(*a.grid))
