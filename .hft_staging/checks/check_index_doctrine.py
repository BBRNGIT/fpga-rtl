#!/usr/bin/env python3
"""check_index_doctrine.py — Index Doctrine enforcer (the project gate).

Enforces CLAUDE.md Law #10 / FOUNDER_VISION.md §8a on a component:

  PRICE IS A DIRECT INDEX, NOT STORED DATA, AND MAY BE REFERENCED ONLY AGAINST
  TIME — never against price, never absolute.

A price-indexed module (indicator or DOM) is a price-indexed activity counter:
the price *is* the address. The following are therefore FORBIDDEN and fail the
gate (a violation blocks development):

  1. ALLOCATION / STORED PRICE-KEY — a ring/table slot that stores a price as a
     key to match against (the retired FP_LVL / level_ring-with-price-slot model),
     or any free-slot/cursor allocation node (ALLOC, *_CURSOR, FREE_SLOT).
  2. ABSOLUTE-PRICE ANCHOR — a constant/config price origin (PRICE_ANCHOR,
     PRICE_BASE, PRICE_REF, ABS_PRICE): there is no absolute price.
  3. PRICE-vs-PRICE OFFSET — a subtraction whose BOTH operands are price seams
     (price referenced against price). The only legal price-values are the
     time-referenced extremes open/high/low/close and DOM per-tick counters.

Legitimate (NOT flagged): OHLC extremes (price at/over a time event), history
rings indexed by BAR_SEQ, per-tick activity counters indexed by price.

Scope: applies to modules whose kind is indicator/dom OR that consume DOM price
seams. Infra/clock modules (no price axis) pass quietly.

Usage: check_index_doctrine.py <component_dir>
Exit 0 = PASS (conforms / not price-indexed); 1 = FAIL with violations named.
"""
import sys, os, glob, re, json

try:
    import yaml
except Exception:
    yaml = None

ALLOC_RE  = re.compile(r"(alloc|_cursor|cursor_|free_slot|alloc_cur)", re.I)
ANCHOR_RE = re.compile(r"(price_anchor|price_base|price_ref|abs_price|absolute_price)", re.I)
PRICE_RE  = re.compile(r"price", re.I)
# OHLC / time-referenced extremes are legitimate price-values — never flagged.
OHLC_RE   = re.compile(r"(open|high|low|close|_ohlc)", re.I)


def load_spec(comp):
    """Return (kind, spec_dict, source_path) — prefer *_logic.yaml, else *.net.json."""
    ly = glob.glob(os.path.join(comp, "*_logic.yaml"))
    if ly and yaml:
        d = yaml.safe_load(open(ly[0]))
        return d.get("kind", ""), d, ly[0]
    nets = [n for n in glob.glob(os.path.join(comp, "*.net.json"))]
    if nets:
        d = json.load(open(nets[0]))
        return d.get("kind", ""), d, nets[0]
    return "", None, None


def is_price_indexed(kind, spec):
    if kind in ("indicator", "dom"):
        return True
    blob = json.dumps(spec) if spec else ""
    return "DOM_BEST_" in blob or kind == "footprint" or kind == "tpo"


def main():
    if len(sys.argv) != 2:
        sys.stderr.write("usage: check_index_doctrine.py <component_dir>\n"); sys.exit(2)
    comp = sys.argv[1].rstrip("/")
    name = os.path.basename(comp)
    kind, spec, src = load_spec(comp)
    if spec is None:
        print(f"check_index_doctrine: {name}: no spec/netlist — skipped"); sys.exit(0)
    if not is_price_indexed(kind, spec):
        print(f"check_index_doctrine: PASS {name}: not price-indexed (no price axis) — N/A")
        sys.exit(0)

    violations = []

    # (1) allocation / stored price-key -------------------------------------
    lr = spec.get("level_ring")
    if isinstance(lr, dict):
        for slot in lr.get("slots", []):
            sn = slot.get("name", "")
            if PRICE_RE.search(sn):
                violations.append(
                    f"ALLOCATION/STORED-PRICE-KEY: level_ring slot '{sn}' stores price "
                    f"as a key — price is the index, not stored data (Law #10).")
        if not any(PRICE_RE.search(s.get("name", "")) for s in lr.get("slots", [])):
            violations.append(
                f"ALLOCATION: 'level_ring' present — store-and-allocate is retired; "
                f"index by price directly (Law #10).")

    # name-based scan across all declared nodes -----------------------------
    def node_names(spec):
        out = []
        for grp in ("const_nodes", "config_nodes", "dff_nodes", "comb_nodes", "out_nodes"):
            for n in spec.get(grp, []) or []:
                if isinstance(n, dict) and n.get("name"):
                    out.append(n["name"])
        return out

    for nm in node_names(spec):
        if ALLOC_RE.search(nm):
            violations.append(f"ALLOCATION: node '{nm}' is a free-slot/cursor allocator (Law #10).")
        if ANCHOR_RE.search(nm):
            violations.append(f"ABSOLUTE-PRICE ANCHOR: node '{nm}' — there is no absolute price; "
                              f"reference price only against time (Law #10).")

    # (3) price-vs-price offset (subtraction of two price operands) ----------
    for c in spec.get("comb_nodes", []) or []:
        if not isinstance(c, dict):
            continue
        if c.get("cell") == "addsub" and int(c.get("sub", 0)) == 1:
            ins = [str(x) for x in c.get("inputs", [])]
            price_ins = [x for x in ins if PRICE_RE.search(x)]
            ohlc_ins = [x for x in ins if OHLC_RE.search(x)]
            # both operands are prices AND neither is an OHLC time-extreme => price-vs-price
            if len(price_ins) >= 2 and not ohlc_ins:
                violations.append(
                    f"PRICE-vs-PRICE OFFSET: comb_node '{c.get('name')}' subtracts price "
                    f"from price ({', '.join(price_ins)}) — price may be referenced only "
                    f"against time (Law #10).")

    if violations:
        print(f"INDEX-DOCTRINE {os.path.basename(src)}: FAIL — module '{name}' violates the Index Doctrine:")
        for v in violations:
            print(f"  ERROR: {v}")
        print("  Fix: spec the module as a price-indexed projection (price = direct index; "
              "values only as time-referenced OHLC / per-tick counters). See CLAUDE.md Law #10.")
        sys.exit(1)

    print(f"check_index_doctrine: PASS {name}: price-indexed, no allocation/anchor/price-vs-price (Law #10)")
    sys.exit(0)


if __name__ == "__main__":
    main()
