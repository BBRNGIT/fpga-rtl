"""
eda_shapes.py — a small EDA symbol library + classifier that aids figure extraction.

Datasheet schematics use a fixed visual vocabulary. Describing it here lets figparse
RECOGNIZE shapes instead of treating every vector line as a wire (which over-merges):

  - WIRE        : an orthogonal segment (horizontal or vertical) that connects pins.
  - SYMBOL body : diagonal line-triples form triangles (buffers / the BUFGCTRL symbol).
  - INVERTER    : a small CURVE (bubble) at a triangle tip negates the signal.
  - BOX         : a rectangle is a block body (its edges are NOT wires).
  - TIE         : the text tokens VDD / GND are power ties (constant 1 / 0).

Extend this library with more described shapes (gate outlines, mux trapezoids,
junction dots) to sharpen extraction further — that is the "custom EDA library".
"""
import math

ORTHO_EPS = 1.6     # slope tolerance: a wire is H or V within this many points
BUBBLE_MAX = 9.0    # an inverter bubble curve is small (bbox diagonal under this)

def seg_kind(a, b):
    dx, dy = abs(b[0] - a[0]), abs(b[1] - a[1])
    if dx <= ORTHO_EPS and dy <= ORTHO_EPS: return "dot"
    if dy <= ORTHO_EPS:                       return "wire_h"
    if dx <= ORTHO_EPS:                       return "wire_v"
    return "diag"                              # symbol edge (triangle / inverter)

def is_wire(a, b):
    return seg_kind(a, b) in ("wire_h", "wire_v")

# --- power ties ---
TIE = {"VDD": "1", "VCC": "1", "GND": "0", "VSS": "0"}
def tie_const(label):
    return TIE.get(label.strip().upper())

# --- inverter bubbles (small curves) ---
def bubble_center(item):
    """item is a 'c' (curve) drawing item -> (cx,cy, size) if it's bubble-sized, else None."""
    pts = [p for p in item[1:] if hasattr(p, "x")]
    if not pts: return None
    xs = [p.x for p in pts]; ys = [p.y for p in pts]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    if math.hypot(w, h) <= BUBBLE_MAX:
        return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, math.hypot(w, h))
    return None

def collect(drawings):
    """split a page's drawings into wires, diagonals (symbol edges), rects, bubbles."""
    wires, diags, rects, bubbles = [], [], [], []
    for dr in drawings:
        for it in dr["items"]:
            if it[0] == "l":
                a, b = (it[1].x, it[1].y), (it[2].x, it[2].y)
                (wires if is_wire(a, b) else diags).append((a, b))
            elif it[0] == "re":
                r = it[1]; rects.append((r.x0, r.y0, r.x1, r.y1))
            elif it[0] == "c":
                bc = bubble_center(it)
                if bc: bubbles.append(bc)
    return wires, diags, rects, bubbles

def _close(a, b, t=4.0): return math.hypot(a[0] - b[0], a[1] - b[1]) <= t
def _other(seg, end):    return seg[1] if _close(seg[0], end) else seg[0]

def triangle_flat_sides(diags, wires):
    """A symbol triangle = two diagonals meeting at a tip, closed by a vertical 'flat side'
    wire. That flat side is orthogonal so it looks like a wire, but it is the SYMBOL body —
    keeping it shorts every input pin together. Return the flat-side wires to EXCLUDE."""
    excl = set()
    for i in range(len(diags)):
        for j in range(i + 1, len(diags)):
            di, dj = diags[i], diags[j]
            for ea in di:
                for eb in dj:
                    if _close(ea, eb):                      # shared tip
                        oa, ob = _other(di, ea), _other(dj, eb)
                        for w in wires:
                            if (_close(w[0], oa) and _close(w[1], ob)) or \
                               (_close(w[0], ob) and _close(w[1], oa)):
                                excl.add(w)
    return excl
