#!/usr/bin/env python3
"""
figblocks.py — extract BLOCK-DIAGRAM connectivity from PDF figures.

Where figparse.py traces gate-level schematics (pin labels + inverter bubbles), this tool
reads BLOCK diagrams: labeled rectangles (blocks) joined by orthogonal wires/buses. It is
the right extractor for TRM/architecture figures (APU block diagram, the PS-PL interface
map, DisplayPort media interfaces, clock trees as boxes).

Per figure it:
  1. finds rectangles = block bodies; the block's NAME is the text whose smallest enclosing
     rectangle is that box (so nested container boxes don't swallow child labels);
  2. net-traces the orthogonal wires (union-find + T-junction), exactly like figparse;
  3. attaches each block to every net a wire touches on its perimeter;
  4. binds free-floating text on a wire (not inside any box) as that net's SIGNAL/bus label;
  5. emits, per net, the set of blocks it connects + the signals riding it.

Output figblocks_out.json: {figure: {title, blocks:[...], connections:[{blocks, signals}]}}.
Faithful: every block name and signal is text printed in the figure; edges are the drawn
wires. Nothing is inferred — an unlabeled junction box is dropped, not named.

Usage: figblocks.py <pdf> [--pages a-b] [--out figblocks_out.json]
Exit 0 ok, 2 internal error.
"""
import sys, os, re, json, argparse, math
try:
    import fitz
except Exception as e:
    print(f"figblocks: PyMuPDF required: {e}"); sys.exit(2)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import eda_shapes as eda

EPS = 3.0            # net-merge / T-junction tolerance (points)
TOUCH = 6.0          # a wire endpoint this close to a box edge attaches the box to its net
SIG_REACH = 16.0     # a free label within this of a wire binds as that net's signal

class UF:
    def __init__(self): self.p = {}
    def find(self, x):
        self.p.setdefault(x, x); r = x
        while self.p[r] != r: r = self.p[r]
        while self.p[x] != r: self.p[x], x = r, self.p[x]
        return r
    def union(self, a, b): self.p[self.find(a)] = self.find(b)

def q(p): return (round(p[0] / EPS), round(p[1] / EPS))

def dist_pt_seg(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay; l2 = dx * dx + dy * dy
    if l2 == 0: return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

def trace(segs):
    uf = UF()
    for a, b in segs: uf.union(q(a), q(b))
    ends = [a for a, b in segs] + [b for a, b in segs]
    for pt in ends:
        kp = q(pt)
        for a, b in segs:
            if dist_pt_seg(pt, a, b) < EPS: uf.union(kp, q(a)); uf.union(kp, q(b))
    return uf

def dist_pt_rect(p, r):
    """distance from point to the nearest edge of rect r=(x0,y0,x1,y1) (0 if on border)."""
    x0, y0, x1, y1 = r; px, py = p
    dx = max(x0 - px, 0, px - x1); dy = max(y0 - py, 0, py - y1)
    if dx == 0 and dy == 0:                                  # inside: dist to closest edge
        return min(px - x0, x1 - px, py - y0, y1 - py)
    return math.hypot(dx, dy)

def area(r): return abs((r[2] - r[0]) * (r[3] - r[1]))

def figures_on_page(page):
    figs = []
    for b in page.get_text("blocks"):
        txt = b[4].strip().replace("\n", " ")
        if re.match(r'(X-Ref Target.*)?Figure\s+\d+-\d+', txt) and "Target" not in txt:
            figs.append((re.sub(r'^X-Ref.*?(Figure)', r'\1', txt), b[1]))
    return figs

SIG_RE = re.compile(r'^[A-Za-z][\w/]{1,}(\[\d+:\d+\])?$')

def clean_name(nm):
    """Strip block-diagram annotation noise from a box label: bus-width digit runs and
    standalone AXI M/S port markers that sit inside the box, plus pure-glyph garble. Keeps
    multiplicity tokens (x2/x4) and real words. Returns '' if nothing real remains."""
    toks = nm.split()
    keep = [t for t in toks if not re.fullmatch(r'\d+', t)        # bare bus width
            and not re.fullmatch(r'[MSFD]', t)                    # AXI master/slave/domain marker
            and re.search(r'[A-Za-z]{2,}|x\d', t)]                # must carry a real word / xN
    out = re.sub(r'\s+', " ", " ".join(keep)).strip()
    return out if len(out) >= 2 else ""

def run(pdf, pages, out):
    doc = fitz.open(pdf)
    rng = range(doc.page_count)
    if pages:
        a, b = pages.split("-"); rng = range(int(a) - 1, int(b))
    pageA = doc[rng.start].rect.width * doc[rng.start].rect.height if rng else 0
    result = {}
    for i in rng:
        if i < 0 or i >= doc.page_count: continue
        page = doc[i]
        caps = sorted(figures_on_page(page), key=lambda c: c[1])
        if not caps: continue
        wires, diags, rects_all, _ = eda.collect(page.get_drawings())
        # triangle/symbol-body exclusion is O(diags^2) and only matters for gate schematics;
        # block diagrams have ~no gate triangles, so skip it on diagonal-dense pages (keeps
        # the dense interconnect figures from dominating wall-clock; accuracy-neutral here).
        if len(diags) <= 250:
            flat = eda.triangle_flat_sides(diags, wires)
            wires = [w for w in wires if w not in flat]
        words = [(w[0], w[1], w[2], w[3], w[4]) for w in page.get_text("words")]
        PA = page.rect.width * page.rect.height
        prev = 70.0
        for cap, cy in caps:
            band = (prev, cy - 2)
            fw = [(a, b) for a, b in wires if band[0] < a[1] < band[1] and band[0] < b[1] < band[1]]
            # boxes: rects in band, not the page border, reasonably sized
            boxes = [r for r in rects_all
                     if band[0] < (r[1] + r[3]) / 2 < band[1]
                     and 0.00008 * PA < area(r) < 0.55 * PA
                     and (r[2] - r[0]) > 8 and (r[3] - r[1]) > 6]
            prev = cy
            if len(fw) < 3 or len(boxes) < 2: continue
            boxes.sort(key=area)                              # smallest first -> innermost label owner
            # label each box from words whose SMALLEST containing box is it
            blab = {bi: [] for bi in range(len(boxes))}
            used = set()
            for wi, (x0, y0, x1, y1, t) in enumerate(words):
                if not (band[0] <= (y0 + y1) / 2 <= band[1]): continue
                cx, cyw = (x0 + x1) / 2, (y0 + y1) / 2
                for bi, r in enumerate(boxes):
                    if r[0] <= cx <= r[2] and r[1] <= cyw <= r[3]:
                        blab[bi].append((y0, x0, t)); used.add(wi); break
            names = {}
            for bi, toks in blab.items():
                toks.sort()
                nm = " ".join(t for _, _, t in toks).strip()
                nm = clean_name(re.sub(r'\s+', " ", nm))
                if 2 <= len(nm) <= 60: names[bi] = nm
            if len(names) < 2: continue
            uf = trace(fw)
            # attach each named box to the nets its perimeter touches
            box_nets = {bi: set() for bi in names}
            for a, b in fw:
                for pt in (a, b):
                    for bi in names:
                        if dist_pt_rect(pt, boxes[bi]) <= TOUCH:
                            box_nets[bi].add(uf.find(q(pt)))
            net_boxes = {}
            for bi, nets in box_nets.items():
                for nid in nets: net_boxes.setdefault(nid, set()).add(bi)
            # free signal labels (not inside a box) bound to nearest net
            net_sig = {}
            for wi, (x0, y0, x1, y1, t) in enumerate(words):
                if wi in used or not (band[0] <= (y0 + y1) / 2 <= band[1]): continue
                if not SIG_RE.match(t): continue
                cpt = ((x0 + x1) / 2, (y0 + y1) / 2)
                best, bnid = SIG_REACH, None
                for a, b in fw:
                    d = dist_pt_seg(cpt, a, b)
                    if d < best: best, bnid = d, uf.find(q(a if math.hypot(cpt[0]-a[0], cpt[1]-a[1]) <= math.hypot(cpt[0]-b[0], cpt[1]-b[1]) else b))
                if bnid is not None: net_sig.setdefault(bnid, set()).add(t)
            conns = []
            for nid, bis in net_boxes.items():
                if len(bis) < 2 and not net_sig.get(nid): continue
                if len(bis) < 2: continue
                conns.append({"blocks": sorted(names[bi] for bi in bis),
                              "signals": sorted(net_sig.get(nid, []))[:8]})
            m = re.search(r'Figure\s+(\d+-\d+)\s*:?\s*(.*)', cap)
            fid = m.group(1) if m else cap[:10]; title = (m.group(2).strip() if m else "")[:50]
            if conns or len(names) >= 2:
                result[f"p{i+1}:Fig{fid}"] = {"page": i + 1, "title": title,
                    "blocks": sorted(set(names.values())), "connections": conns}
    json.dump(result, open(out, "w"), indent=2)
    nb = sum(len(v["blocks"]) for v in result.values()); nc = sum(len(v["connections"]) for v in result.values())
    print(f"figblocks: {len(result)} figure(s), {nb} blocks, {nc} connections -> {out}")
    for k, v in list(result.items())[:40]:
        print(f"  {k:16s} {v['title'][:38]:38s} blocks={len(v['blocks']):2d} conns={len(v['connections']):2d}")
    return 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf"); ap.add_argument("--pages", default=None)
    ap.add_argument("--out", default=os.path.join(HERE, "figblocks_out.json"))
    a = ap.parse_args()
    try: sys.exit(run(a.pdf, a.pages, a.out))
    except Exception:
        import traceback; traceback.print_exc(); sys.exit(2)
