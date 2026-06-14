#!/usr/bin/env python3
"""
figparse.py — Tool: extract CONNECTIONS from PDF figures (vector shapes + text).

A datasheet figure is a schematic: line segments are wires, text tokens are
labels/ties (port names, VDD, GND). This tool net-traces the wires (union-find on
line endpoints, with T-junction detection) and assigns each label to the net its
pin touches. Output figparse_out.json: per figure, the connection groups (which
labels are wired together). This is how config decompositions (e.g. BUFGMUX =
BUFGCTRL + ties, the MMCM D/PFD/VCO/M/O divider diagram) come from the SPEC,
not from hand-encoding.

Usage: figparse.py <pdf> [--pages a-b] [--out figparse_out.json]
Exit 0 ok, 2 internal error.
"""
import sys, os, re, json, argparse, math
try:
    import fitz
except Exception as e:
    print(f"figparse: PyMuPDF required: {e}"); sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eda_shapes as eda
EPS = 3.0           # point tolerance: merge endpoints / detect T-junctions
LABEL_REACH = 20.0  # max distance label-center -> wire node to bind a label to a net

class UF:
    def __init__(self): self.p = {}
    def find(self, x):
        self.p.setdefault(x, x)
        r = x
        while self.p[r] != r: r = self.p[r]
        while self.p[x] != r: self.p[x], x = r, self.p[x]
        return r
    def union(self, a, b): self.p[self.find(a)] = self.find(b)

def q(p): return (round(p[0] / EPS), round(p[1] / EPS))

def dist_pt_seg(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 == 0: return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

def page_shapes(page):
    """ALL orthogonal WIRES (symbol triangles/boxes recognized & excluded) + bubbles.
    Band selection happens in run() from the wire cluster, so figure prose is excluded."""
    wires_all, diags, rects, bubbles = eda.collect(page.get_drawings())
    flat = eda.triangle_flat_sides(diags, wires_all)      # symbol-body edges to drop
    wires = [(a, b) for a, b in wires_all if (a, b) not in flat]
    return wires, bubbles

def trace(segs):
    uf = UF()
    for a, b in segs:
        uf.union(q(a), q(b))
    ends = [a for a, b in segs] + [b for a, b in segs]
    for pt in ends:                       # T-junctions: endpoint on another wire's body
        kp = q(pt)
        for a, b in segs:
            if dist_pt_seg(pt, a, b) < EPS:
                uf.union(kp, q(a)); uf.union(kp, q(b))
    return uf

def _foot(p, a, b):
    """perpendicular foot of point p on segment a-b, clamped to the segment."""
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 == 0: return (ax, ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return (ax + t * dx, ay + t * dy)

def nearest_node(label, segs):
    """Bind a label to the WIRE it touches, returning a real endpoint of that wire
    (so q(pt) yields the correct net) and the perpendicular contact distance.

    A pin label often sits on the BODY of its stub wire (e.g. an inverter-output
    pin lands mid-segment, far from either endpoint). So we score against the
    perpendicular FOOT-point on each segment, not just its endpoints — a degenerate
    foot at an endpoint reproduces the old endpoint behaviour. The OWN-row bias is
    preserved: vertical offset of the foot is penalized 10x so vertically-stacked
    labels don't cross-bind. Returns (endpoint_pt, perp_dist)."""
    cx, cy = label["cx"], label["cy"]
    best, bscore, bdist = None, 1e9, 1e9
    for a, b in segs:
        fx, fy = _foot((cx, cy), a, b)
        dx, dy = abs(cx - fx), abs(cy - fy)
        score = dx + dy * 10
        if score < bscore:
            # bind to the segment endpoint nearest the foot: a real, quantized net node
            pt = a if math.hypot(fx - a[0], fy - a[1]) <= math.hypot(fx - b[0], fy - b[1]) else b
            bscore, best, bdist = score, pt, math.hypot(dx, dy)
    return (best, bdist)

LABEL_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*(\[\d+:\d+\])?$|^V?DD$|^GND$|^VDD$')

def figures_on_page(page):
    """find 'Figure N-N:' captions -> (caption, y_top_of_caption). band = between header and caption."""
    figs = []
    for b in page.get_text("blocks"):
        txt = b[4].strip().replace("\n", " ")
        if re.match(r'(X-Ref Target.*)?Figure\s+\d+-\d+', txt) and "Target" not in txt:
            figs.append((txt, b[1]))
    return figs

def run(pdf, pages, out, debug=False, cap_filter=None):
    doc = fitz.open(pdf)
    rng = range(doc.page_count)
    if pages:
        a, b = pages.split("-"); rng = range(int(a) - 1, int(b))
    result = {}
    for i in rng:
        if i < 0 or i >= doc.page_count: continue
        page = doc[i]
        caps = sorted(figures_on_page(page), key=lambda c: c[1])
        if not caps: continue
        all_wires, all_bubbles = page_shapes(page)
        prev = 80.0
        for cap, cy in caps:
            # figure = the wire cluster between the previous caption and this one
            fw = [(a, b) for (a, b) in all_wires if prev < a[1] < cy and prev < b[1] < cy]
            if len(fw) < 4: prev = cy; continue
            band = (min(min(a[1], b[1]) for a, b in fw) - 20, cy - 4)  # hug the shapes (+pad for top pins)
            wires = fw
            bubbles = [bb for bb in all_bubbles if band[0] <= bb[1] <= band[1]]
            prev = cy
            uf = trace(wires)
            labs = []
            for w in page.get_text("words"):
                x0, y0, x1, y1, t = w[0], w[1], w[2], w[3], w[4]
                if not (band[0] <= y0 <= band[1]): continue
                if not LABEL_RE.match(t): continue
                if t in ("Figure",): continue
                labs.append({"text": t, "cx": (x0 + x1) / 2, "cy": (y0 + y1) / 2})
            net_pts = {}                       # net id -> wire endpoint positions
            for a, b in wires:
                for pt in (a, b):
                    net_pts.setdefault(uf.find(q(pt)), []).append(pt)
            nets = {}
            for lb in labs:
                node, d = nearest_node(lb, wires)
                bound = node is not None and d <= LABEL_REACH
                if debug and (cap_filter is None or cap_filter in cap):
                    nid = uf.find(q(node)) if node is not None else None
                    print(f"      {lb['text']:10s} d={d:5.1f} -> {('net'+str(nid)) if bound else 'UNBOUND'}")
                if not bound: continue
                nets.setdefault(uf.find(q(node)), []).append(lb["text"])
            # inverter: a bubble links the two nearest distinct nets (out = nearest, in = next)
            def net_dist(nid, p):
                return min((math.hypot(p[0] - x[0], p[1] - x[1]) for x in net_pts.get(nid, [])), default=1e9)
            def lbls(nid): return sorted(set(nets.get(nid, []))) or [f"net{nid[0]}_{nid[1]}"]
            inverters, seen_inv = [], set()
            for bx, by, _ in bubbles:
                ranked = sorted(net_pts, key=lambda nid: net_dist(nid, (bx, by)))
                near = [nid for nid in ranked if net_dist(nid, (bx, by)) < 18][:2]
                if len(near) == 2:
                    o, ii = lbls(near[0]), lbls(near[1])
                    key = (tuple(o), tuple(ii))     # a bubble drawn as many curve points -> one inverter
                    if key in seen_inv: continue
                    seen_inv.add(key)
                    inverters.append({"out": o, "in": ii})
            groups = []
            for nid, v in nets.items():
                names = sorted(set(v))
                if len(names) < 2: continue
                g = {"net": names}
                ties = sorted({eda.tie_const(n) for n in names if eda.tie_const(n)})
                if ties: g["tie"] = ties
                groups.append(g)
            m = re.search(r'Figure\s+(\d+-\d+)\s*:?\s*(.*)', cap)
            fid = m.group(1) if m else cap[:12]
            name = (m.group(2).strip() if m else "")[:48]
            result[f"p{i+1}:Fig{fid}"] = {"page": i + 1, "title": name,
                                          "labels": len(labs), "wires": len(wires),
                                          "bubbles": len(bubbles), "nets": groups,
                                          "inverters": inverters}
    json.dump(result, open(out, "w"), indent=2)
    print(f"figparse: {len(result)} figure(s) -> {out}")
    for k, v in result.items():
        print(f"  {k:14s} {v['title'][:32]:32s} wires={v.get('wires',0):3d} nets={len(v['nets'])}")
        for g in v["nets"][:12]:
            tag = f" [tie {','.join(g['tie'])}]" if g.get("tie") else ""
            print(f"        {' = '.join(g['net'])}{tag}")
        for inv in v.get("inverters", []):
            print(f"        {'/'.join(inv['out'])} = ~( {'/'.join(inv['in'])} )")
    return 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf"); ap.add_argument("--pages", default=None)
    ap.add_argument("--out", default=os.path.join(HERE, "figparse_out.json"))
    ap.add_argument("--debug", action="store_true"); ap.add_argument("--fig", default=None)
    a = ap.parse_args()
    try: sys.exit(run(a.pdf, a.pages, a.out, a.debug, a.fig))
    except Exception:
        import traceback; traceback.print_exc(); sys.exit(2)
