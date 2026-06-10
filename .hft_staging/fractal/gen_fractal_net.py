#!/usr/bin/env python3
"""gen_fractal_net.py — EMITTER: writes fractal.net.json.

This python file is the real deliverable (DESIGN_GUIDE step 3): it emits the
netlist describing the fractal indicator as addressed register nodes wired as
cells — branchless. gennet.py then GENERATES the device C from this netlist; the
device tick is never hand-written.

Hardware spec: 5-bar Bill Williams fractal detector (WAVE 2). The middle bar of
five consecutive completed bars (the cs2 / seq-3 slot) is a fractal pivot when
its HIGH is strictly above (UP) or its LOW strictly below (DN) the four
neighbours, gated by seq >= 5. See FRACTAL_ARCHITECTURE.md §3 for the full
flip-flop spec. Reference logic: hft_pipeline/indicators/fractal/fractal.c.

comb_nodes are the explicit combinational gate primitives from
FRACTAL_ARCHITECTURE.md §3. Each comb_node names ONE gate cell and its inputs;
gennet.py expands each into exactly one structural cell call (no native C
arithmetic, no if/?:, branchless mask algebra only).
"""
import json

SENTINEL = 0xFFFFFFFFFFFFFFFF
CANDLE_HIST_MASK = 0xFF   # candle ring depth 256 -> mask 255
FRAC_HIST_MASK   = 0xFF   # fractal ring depth 256 -> mask 255

NET = {
    "device": "fractal",
    "window_base": "0x00000000",
    "kind": "module",
    "comment": (
        "5-bar Bill Williams fractal detector (WAVE 2). Pivot = middle bar "
        "(cs2/seq-3) of five consecutive completed bars; UP iff its HIGH is "
        "strictly above all four neighbours, DN iff its LOW strictly below, "
        "both gated by seq>=5. (auto-generated from FRACTAL_ARCHITECTURE.md)"
    ),

    # --- input lanes (driven from outside the netlist: published windows). -----
    # Fractal samples published windows only (module barrier); never reads
    # another module's private registers. TF_BAR_SEQ_REG is the timeframe seq;
    # H0..H4 / L0..L4 are the candle-published HIGH/LOW lanes already resolved at
    # ring slots cs0..cs4 (the candle producer indexes; fractal reads the lane).
    "config_nodes": [
        {"name": "TF_BAR_SEQ_REG", "type": "u64",
         "comment": "Timeframe bar sequence (seq>=5 guard + ring index source)"},
        {"name": "H0", "type": "u64", "comment": "candle HIGH at cs0 (seq-1)"},
        {"name": "H1", "type": "u64", "comment": "candle HIGH at cs1 (seq-2)"},
        {"name": "H2", "type": "u64", "comment": "candle HIGH at cs2 (seq-3, pivot)"},
        {"name": "H3", "type": "u64", "comment": "candle HIGH at cs3 (seq-4)"},
        {"name": "H4", "type": "u64", "comment": "candle HIGH at cs4 (seq-5)"},
        {"name": "L0", "type": "u64", "comment": "candle LOW at cs0 (seq-1)"},
        {"name": "L1", "type": "u64", "comment": "candle LOW at cs1 (seq-2)"},
        {"name": "L2", "type": "u64", "comment": "candle LOW at cs2 (seq-3, pivot)"},
        {"name": "L3", "type": "u64", "comment": "candle LOW at cs3 (seq-4)"},
        {"name": "L4", "type": "u64", "comment": "candle LOW at cs4 (seq-5)"},
    ],

    # constant lanes referenced by comb_node inputs (subtrahends for the ring
    # index derivation, the seq guard threshold, and the no-fractal sentinel).
    # Driven once at reset by init; never written by the device tick.
    "const_nodes": [
        {"name": "FRAC_THREE", "type": "u64", "value": 3,
         "comment": "subtrahend for the pivot write slot cs2 = seq-3"},
        {"name": "FRAC_FIVE",  "type": "u64", "value": 5,
         "comment": "the seq>=5 guard threshold (need five completed bars)"},
        {"name": "FRAC_SENTINEL", "type": "u64", "value": SENTINEL,
         "comment": "no-fractal sentinel (0xFFFF...FFFF, renders ---.----)"},
    ],

    # --- registered state (the device's owned writes). -------------------------
    # Two scalar high-water marks. Each is the destination latch for the matching
    # *_UPDATE comb_node below (mux: latch pivot on match, else hold).
    "dff_nodes": [
        {"name": "IND_FRAC_UP_PRICE_REG", "type": "u64",
         "comment": "High-water mark of detected UP fractal pivot highs"},
        {"name": "IND_FRAC_DN_PRICE_REG", "type": "u64",
         "comment": "High-water mark of detected DN fractal pivot lows"},
    ],

    # --- history ring (FRACTAL_ARCHITECTURE.md §2): 256 slots x 2 fields. -------
    # The middle-bar (cs2) slot receives NEXT_HU/NEXT_HD each tick: pivot price on
    # a match, else sentinel. Index is computed structurally (CS2 comb node).
    "history_ring": {
        "name": "IND_FRAC_HIST",
        "depth": 256,
        "fields": ["FRAC_HIST_UP", "FRAC_HIST_DN"],
        "index": "CS2",
        "field_src": {"FRAC_HIST_UP": "NEXT_HU", "FRAC_HIST_DN": "NEXT_HD"},
        "init": SENTINEL,
        "comment": "Per-bar fractal record; sentinel where no fractal detected",
    },

    # --- combinational logic (FRACTAL_ARCHITECTURE.md §3) ----------------------
    # Each comb_node names ONE gate cell and its inputs; gennet expands each into
    # exactly one structural cell call. cell vocabulary: addsub (+ optional mask),
    # cmp_lt, and, mux, plus the ^1 invert modifier. No native +/-/*, no if/?:.
    "comb_nodes": [
        # 3.1 Pivot history-write slot: cs2 = (seq-3) & FRAC_HIST_MASK. This is
        # the ONLY ring index fractal owns — it addresses fractal's OWN history
        # write. The read-side slots (cs0/cs1/cs3/cs4) that resolve H0..H4/L0..L4
        # belong to the candle seam (the producer indexes its ring and publishes
        # the H*/L* lanes); fractal samples those lanes, so it does not recompute
        # their indices. Modelling them here would be dead logic (no consumer)
        # and trip -Werror -Wunused-variable.
        {"name": "CS2", "cell": "addsub", "inputs": ["TF_BAR_SEQ_REG", "FRAC_THREE"],
         "sub": 1, "mask": FRAC_HIST_MASK,
         "comment": "cs2 = (seq-3) & FRAC_HIST_MASK (pivot bar + history write slot)"},

        # 3.2 seq>=5 guard. cmp_lt(seq,5)=1 iff seq<5; invert -> seq>=5.
        {"name": "SEQ_GE5", "cell": "cmp_lt",
         "inputs": ["TF_BAR_SEQ_REG", "FRAC_FIVE"], "invert": True,
         "comment": "SEQ_GE5 = cmp_lt(seq,5) ^ 1 = (seq >= 5)"},

        # 3.3 UP predicate: h2 strictly greater than each neighbour.
        # a>b expressed as cmp_lt(b,a) (operands swapped).
        {"name": "UP_GT0", "cell": "cmp_lt", "inputs": ["H0", "H2"],
         "comment": "h2 > h0"},
        {"name": "UP_GT1", "cell": "cmp_lt", "inputs": ["H1", "H2"],
         "comment": "h2 > h1"},
        {"name": "UP_GT3", "cell": "cmp_lt", "inputs": ["H3", "H2"],
         "comment": "h2 > h3"},
        {"name": "UP_GT4", "cell": "cmp_lt", "inputs": ["H4", "H2"],
         "comment": "h2 > h4"},
        {"name": "UP_AND_A", "cell": "and", "inputs": ["UP_GT0", "UP_GT1"],
         "comment": "(h2>h0) & (h2>h1)"},
        {"name": "UP_AND_B", "cell": "and", "inputs": ["UP_GT3", "UP_GT4"],
         "comment": "(h2>h3) & (h2>h4)"},
        {"name": "UP_AND_C", "cell": "and", "inputs": ["UP_AND_A", "UP_AND_B"],
         "comment": "all four high comparisons"},
        {"name": "IS_UP", "cell": "and", "inputs": ["UP_AND_C", "SEQ_GE5"],
         "comment": "IS_UP = neighbours & (seq>=5)"},

        # 3.4 DN predicate: l2 strictly less than each neighbour. a<b = cmp_lt(a,b).
        {"name": "DN_LT0", "cell": "cmp_lt", "inputs": ["L2", "L0"],
         "comment": "l2 < l0"},
        {"name": "DN_LT1", "cell": "cmp_lt", "inputs": ["L2", "L1"],
         "comment": "l2 < l1"},
        {"name": "DN_LT3", "cell": "cmp_lt", "inputs": ["L2", "L3"],
         "comment": "l2 < l3"},
        {"name": "DN_LT4", "cell": "cmp_lt", "inputs": ["L2", "L4"],
         "comment": "l2 < l4"},
        {"name": "DN_AND_A", "cell": "and", "inputs": ["DN_LT0", "DN_LT1"],
         "comment": "(l2<l0) & (l2<l1)"},
        {"name": "DN_AND_B", "cell": "and", "inputs": ["DN_LT3", "DN_LT4"],
         "comment": "(l2<l3) & (l2<l4)"},
        {"name": "DN_AND_C", "cell": "and", "inputs": ["DN_AND_A", "DN_AND_B"],
         "comment": "all four low comparisons"},
        {"name": "IS_DN", "cell": "and", "inputs": ["DN_AND_C", "SEQ_GE5"],
         "comment": "IS_DN = neighbours & (seq>=5)"},

        # 3.5 Scalar high-water updates. mux(a,b,sel)=sel?b:a -> latch pivot, hold.
        {"name": "IND_FRAC_UP_PRICE_REG_UPDATE", "cell": "mux",
         "inputs": ["IND_FRAC_UP_PRICE_REG", "H2", "IS_UP"],
         "comment": "IS_UP -> latch h2, else hold prior UP high-water"},
        {"name": "IND_FRAC_DN_PRICE_REG_UPDATE", "cell": "mux",
         "inputs": ["IND_FRAC_DN_PRICE_REG", "L2", "IS_DN"],
         "comment": "IS_DN -> latch l2, else hold prior DN high-water"},

        # 3.6 History-slot records: pivot price on match, else sentinel.
        {"name": "NEXT_HU", "cell": "mux",
         "inputs": ["FRAC_SENTINEL", "H2", "IS_UP"],
         "comment": "IS_UP -> h2, else sentinel -> IND_FRAC_HIST[cs2].UP"},
        {"name": "NEXT_HD", "cell": "mux",
         "inputs": ["FRAC_SENTINEL", "L2", "IS_DN"],
         "comment": "IS_DN -> l2, else sentinel -> IND_FRAC_HIST[cs2].DN"},
    ],

    # --- published seam (downstream samples these; fractal is single writer). ---
    "seam_nodes": [
        {"name": "IND_FRAC_UP_PRICE_REG",
         "comment": "Relayed to strategy/display: latest UP fractal high"},
        {"name": "IND_FRAC_DN_PRICE_REG",
         "comment": "Relayed to strategy/display: latest DN fractal low"},
    ],
}


def main():
    """Emit the netlist as JSON to stdout."""
    import sys
    json.dump(NET, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
