#!/usr/bin/env python3
"""gen_cbr_net.py — EMITTER: writes cbr.net.json.

This python file is the real deliverable (DESIGN_GUIDE step 3): it emits the
netlist describing CBR (Cross-Bar Ratio, WAVE 2) as addressed register nodes
wired as cells — branchless. gennet.py then GENERATES the device C from this
netlist; the device tick is never hand-written.

CBR computes bar-over-bar deltas (curr_bar - prev_bar) of committed candle
volume / true-range / intrabar and committed footprint cumulative-delta, plus
running high-water (max) marks. Inputs are sampled committed windows only
(module barrier). See cbr_architecture.md for the full flip-flop spec.

comb_nodes are the explicit combinational gate primitives from
cbr_architecture.md §4. Each comb_node names ONE gate cell and its inputs;
gennet.py expands each into a single structural cell call (no native C
arithmetic, no if/?:, branchless mask algebra only).
"""
import json

NET = {
    "device": "cbr",
    "window_base": "0x00000000",
    "kind": "module",
    "comment": (
        "CBR (Cross-Bar Ratio, WAVE 2): bar-over-bar deltas of committed candle "
        "volume/true-range/intrabar + footprint cumulative-delta, with running "
        "high-water marks. Flip-flop level, netlist-generated (emitter-first)."
    ),

    # --- input lanes (driven from outside: published committed windows). -------
    # CBR samples committed windows only (module barrier); never reads another
    # module's private/live registers.
    "config_nodes": [
        {"name": "CAND_CURR_BID_VOL", "type": "u64",
         "comment": "Committed candle bid volume, current bar (from candle seam)"},
        {"name": "CAND_CURR_ASK_VOL", "type": "u64",
         "comment": "Committed candle ask volume, current bar"},
        {"name": "CAND_CURR_BID_TR", "type": "u64",
         "comment": "Committed candle bid true-range, current bar"},
        {"name": "CAND_CURR_ASK_TR", "type": "u64",
         "comment": "Committed candle ask true-range, current bar"},
        {"name": "CAND_CURR_INTRABAR", "type": "u64",
         "comment": "Committed candle intrabar qty delta, current bar"},
        {"name": "FP_CURR_CUM_DELTA", "type": "u64",
         "comment": "Committed footprint cumulative delta, current bar (footprint seam)"},
        {"name": "TF_BAR_SEQ_REG", "type": "u64",
         "comment": "Timeframe bar sequence (bar-boundary detection)"},
    ],

    # --- registered state (the device's owned writes; architecture §3). --------
    # 14 owned data registers: 6 deltas + 4 high-water + 4 prev-latch.
    # Plus CBR_LAST_TF_SEQ_REG (bar sync) and CBR_BAR_BOUNDARY (control pulse).
    "dff_nodes": [
        # 6 bar-over-bar deltas (curr - prev), latch matching *_UPDATE comb.
        {"name": "CBR_BID_VOL_DELTA_REG", "type": "i64",
         "comment": "curr_bid_vol - prev_bid_vol (committed candle bid volume delta)"},
        {"name": "CBR_ASK_VOL_DELTA_REG", "type": "i64",
         "comment": "curr_ask_vol - prev_ask_vol"},
        {"name": "CBR_BID_TR_DELTA_REG", "type": "i64",
         "comment": "curr_bid_tr - prev_bid_tr (bid true-range delta)"},
        {"name": "CBR_ASK_TR_DELTA_REG", "type": "i64",
         "comment": "curr_ask_tr - prev_ask_tr"},
        {"name": "CBR_FOOTPRINT_DELTA_REG", "type": "i64",
         "comment": "curr_fp_cum - prev_fp_cum (footprint cumulative-delta bar-over-bar)"},
        {"name": "CBR_INTRABAR_DELTA_REG", "type": "i64",
         "comment": "curr_intrabar - prev_intrabar (intrabar qty delta bar-over-bar)"},

        # 4 high-water marks (running unsigned max of primary deltas).
        {"name": "CBR_BID_VOL_HW_REG", "type": "i64",
         "comment": "Running max bid-volume delta observed"},
        {"name": "CBR_ASK_VOL_HW_REG", "type": "i64",
         "comment": "Running max ask-volume delta observed"},
        {"name": "CBR_BID_TR_HW_REG", "type": "i64",
         "comment": "Running max bid-true-range delta observed"},
        {"name": "CBR_ASK_TR_HW_REG", "type": "i64",
         "comment": "Running max ask-true-range delta observed"},

        # 4 previous-bar latches (last committed values; updated on bar boundary).
        {"name": "CBR_PREV_BID_VOL_REG", "type": "u64",
         "comment": "Prev bar committed bid volume (boundary-gated latch)"},
        {"name": "CBR_PREV_ASK_VOL_REG", "type": "u64",
         "comment": "Prev bar committed ask volume"},
        {"name": "CBR_PREV_BID_TR_REG", "type": "u64",
         "comment": "Prev bar committed bid true-range"},
        {"name": "CBR_PREV_ASK_TR_REG", "type": "u64",
         "comment": "Prev bar committed ask true-range"},

        # bar sync + control pulse.
        {"name": "CBR_LAST_TF_SEQ_REG", "type": "u64",
         "comment": "Last TF_BAR_SEQ seen (bar-boundary edge detect)"},
        {"name": "CBR_BAR_BOUNDARY", "type": "u64",
         "comment": "1 iff timeframe seq changed since last cycle (bar just committed)"},
    ],

    # --- combinational logic (cbr_architecture.md §4) --------------------------
    # 20 comb_nodes. Each names ONE gate cell + inputs; gennet expands each into
    # exactly one structural cell call. cell vocabulary: eqmask, addsub, cmp_lt,
    # mux, buf — no native +/-/*, no if/?:.
    "comb_nodes": [
        # 4.1 Bar-boundary detection (eqmask=1 unchanged; XOR 1 -> 1 on change).
        {"name": "CBR_BAR_BOUNDARY", "cell": "eqmask",
         "inputs": ["CBR_LAST_TF_SEQ_REG", "TF_BAR_SEQ_REG"],
         "invert": True,
         "comment": "bar_boundary = eqmask(LAST_TF_SEQ, TF_BAR_SEQ) ^ 1 (seq changed)"},

        # 4.2 Bar-over-bar deltas (curr - prev; sub=1 two's-complement subtract).
        {"name": "CBR_BID_VOL_DELTA_REG_UPDATE", "cell": "addsub",
         "inputs": ["CAND_CURR_BID_VOL", "CBR_PREV_BID_VOL_REG"], "sub": 1,
         "comment": "addsub(curr_bid_vol, prev_bid_vol, 1) = curr - prev"},
        {"name": "CBR_ASK_VOL_DELTA_REG_UPDATE", "cell": "addsub",
         "inputs": ["CAND_CURR_ASK_VOL", "CBR_PREV_ASK_VOL_REG"], "sub": 1,
         "comment": "addsub(curr_ask_vol, prev_ask_vol, 1)"},
        {"name": "CBR_BID_TR_DELTA_REG_UPDATE", "cell": "addsub",
         "inputs": ["CAND_CURR_BID_TR", "CBR_PREV_BID_TR_REG"], "sub": 1,
         "comment": "addsub(curr_bid_tr, prev_bid_tr, 1)"},
        {"name": "CBR_ASK_TR_DELTA_REG_UPDATE", "cell": "addsub",
         "inputs": ["CAND_CURR_ASK_TR", "CBR_PREV_ASK_TR_REG"], "sub": 1,
         "comment": "addsub(curr_ask_tr, prev_ask_tr, 1)"},
        {"name": "CBR_FOOTPRINT_DELTA_REG_UPDATE", "cell": "addsub",
         "inputs": ["FP_CURR_CUM_DELTA", "CBR_PREV_BID_VOL_REG"], "sub": 1,
         "comment": "addsub(curr_fp_cum, prev (boundary-gated chain), 1) — §6 note 2"},
        {"name": "CBR_INTRABAR_DELTA_REG_UPDATE", "cell": "addsub",
         "inputs": ["CAND_CURR_INTRABAR", "CBR_PREV_ASK_VOL_REG"], "sub": 1,
         "comment": "addsub(curr_intrabar, prev (boundary-gated chain), 1) — §6 note 2"},

        # 4.3 High-water (running max): cmp_lt(hw, delta) select, then mux.
        {"name": "CBR_BID_VOL_HW_SEL", "cell": "cmp_lt",
         "inputs": ["CBR_BID_VOL_HW_REG", "CBR_BID_VOL_DELTA_REG_UPDATE"],
         "comment": "is_new_max = cmp_lt(hw, delta) -> 1 iff hw < delta"},
        {"name": "CBR_BID_VOL_HW_REG_UPDATE", "cell": "mux",
         "inputs": ["CBR_BID_VOL_HW_REG", "CBR_BID_VOL_DELTA_REG_UPDATE", "CBR_BID_VOL_HW_SEL"],
         "comment": "mux(hw, delta, is_new_max): adopt delta when hw<delta, else hold"},

        {"name": "CBR_ASK_VOL_HW_SEL", "cell": "cmp_lt",
         "inputs": ["CBR_ASK_VOL_HW_REG", "CBR_ASK_VOL_DELTA_REG_UPDATE"],
         "comment": "is_new_max = cmp_lt(hw, delta)"},
        {"name": "CBR_ASK_VOL_HW_REG_UPDATE", "cell": "mux",
         "inputs": ["CBR_ASK_VOL_HW_REG", "CBR_ASK_VOL_DELTA_REG_UPDATE", "CBR_ASK_VOL_HW_SEL"],
         "comment": "mux(hw, delta, is_new_max)"},

        {"name": "CBR_BID_TR_HW_SEL", "cell": "cmp_lt",
         "inputs": ["CBR_BID_TR_HW_REG", "CBR_BID_TR_DELTA_REG_UPDATE"],
         "comment": "is_new_max = cmp_lt(hw, delta)"},
        {"name": "CBR_BID_TR_HW_REG_UPDATE", "cell": "mux",
         "inputs": ["CBR_BID_TR_HW_REG", "CBR_BID_TR_DELTA_REG_UPDATE", "CBR_BID_TR_HW_SEL"],
         "comment": "mux(hw, delta, is_new_max)"},

        {"name": "CBR_ASK_TR_HW_SEL", "cell": "cmp_lt",
         "inputs": ["CBR_ASK_TR_HW_REG", "CBR_ASK_TR_DELTA_REG_UPDATE"],
         "comment": "is_new_max = cmp_lt(hw, delta)"},
        {"name": "CBR_ASK_TR_HW_REG_UPDATE", "cell": "mux",
         "inputs": ["CBR_ASK_TR_HW_REG", "CBR_ASK_TR_DELTA_REG_UPDATE", "CBR_ASK_TR_HW_SEL"],
         "comment": "mux(hw, delta, is_new_max)"},

        # 4.4 Previous-bar latch: mux(prev, curr, bar_boundary) — adopt on boundary.
        {"name": "CBR_PREV_BID_VOL_REG_UPDATE", "cell": "mux",
         "inputs": ["CBR_PREV_BID_VOL_REG", "CAND_CURR_BID_VOL", "CBR_BAR_BOUNDARY"],
         "comment": "mux(prev, curr, boundary): on bar close adopt curr, else hold prev"},
        {"name": "CBR_PREV_ASK_VOL_REG_UPDATE", "cell": "mux",
         "inputs": ["CBR_PREV_ASK_VOL_REG", "CAND_CURR_ASK_VOL", "CBR_BAR_BOUNDARY"],
         "comment": "mux(prev, curr, boundary)"},
        {"name": "CBR_PREV_BID_TR_REG_UPDATE", "cell": "mux",
         "inputs": ["CBR_PREV_BID_TR_REG", "CAND_CURR_BID_TR", "CBR_BAR_BOUNDARY"],
         "comment": "mux(prev, curr, boundary)"},
        {"name": "CBR_PREV_ASK_TR_REG_UPDATE", "cell": "mux",
         "inputs": ["CBR_PREV_ASK_TR_REG", "CAND_CURR_ASK_TR", "CBR_BAR_BOUNDARY"],
         "comment": "mux(prev, curr, boundary)"},

        # 4.5 Bar-sync latch (track latest seq for next-cycle edge detect).
        {"name": "CBR_LAST_TF_SEQ_REG_UPDATE", "cell": "buf",
         "inputs": ["TF_BAR_SEQ_REG"],
         "comment": "passthrough — latch latest TF_BAR_SEQ for next-cycle boundary edge"},
    ],
}


def main():
    """Emit the netlist as JSON to stdout."""
    import sys
    json.dump(NET, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
