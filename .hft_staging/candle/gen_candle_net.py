#!/usr/bin/env python3
"""gen_candle_net.py — EMITTER: writes candle.net.json.

This python file is the real deliverable (DESIGN_GUIDE step 3): it emits the
netlist describing candle as addressed register nodes wired as cells
— branchless. gennet.py then GENERATES the device C from this netlist; the
device tick is never hand-written.

Hardware specification for building the Candle (Indicator) component flip-flop-level from the netlist-generator (emitter-first workflow).

comb_nodes are the explicit combinational gate primitives from
tools/generators/candle_architecture.md §3. Each comb_node names its gate cell
and its inputs; gennet.py expands each into a single structural cell call (no
native C arithmetic, no if/?:, branchless mask algebra only).
"""
import json

NET = {
    "device": "candle",
    "window_base": "0x00000000",
    "kind": "module",
    "comment": (
        "Hardware specification for building the Candle (Indicator) component flip-flop-level from the netlist-generator (emitter-first workflow). "
        "(auto-generated from PARTS_LIST)"
    ),

    # --- input lanes (driven from outside the netlist: published windows). -----
    # Candle samples published windows only (module barrier); never reads another
    # module's private registers.
    "config_nodes": [
        {"name": "DOM_BID_PRICE", "type": "u64",
         "comment": "Best bid price (highest bid level)"},
        {"name": "DOM_ASK_PRICE", "type": "u64",
         "comment": "Best ask price (lowest ask level)"},
        {"name": "DOM_BID_QTY", "type": "u64",
         "comment": "Bid quantity per price level (indexed by PRICE_IDX)"},
        {"name": "DOM_ASK_QTY", "type": "u64",
         "comment": "Ask quantity per price level (indexed by PRICE_IDX)"},
        {"name": "TF_BAR_SEQ_REG", "type": "u64",
         "comment": "Timeframe bar sequence (for bar-boundary detection)"},
    ],

    # --- registered state (the device's owned writes; architecture §2 Live). ---
    # Each live register is the destination latch for the matching comb_node
    # *_UPDATE rule below. Tick-detection / boundary signals are also dff-backed
    # so their values are addressable inputs to the accumulator rules.
    "dff_nodes": [
        {"name": "CANDLE_BID_OPEN", "type": "u64",
         "comment": "First bid price of bar"},
        {"name": "CANDLE_BID_HIGH", "type": "u64",
         "comment": "Running max bid price"},
        {"name": "CANDLE_BID_LOW", "type": "u64",
         "comment": "Running min bid price"},
        {"name": "CANDLE_BID_CLOSE", "type": "u64",
         "comment": "Most recent bid price (also = previous-bid for tick detect)"},
        {"name": "CANDLE_ASK_OPEN", "type": "u64",
         "comment": "First ask price of bar"},
        {"name": "CANDLE_ASK_HIGH", "type": "u64",
         "comment": "Running max ask price"},
        {"name": "CANDLE_ASK_LOW", "type": "u64",
         "comment": "Running min ask price"},
        {"name": "CANDLE_ASK_CLOSE", "type": "u64",
         "comment": "Most recent ask price (also = previous-ask for tick detect)"},
        {"name": "CANDLE_VOLUME_BID", "type": "u64",
         "comment": "Cumulative bid ticks this bar"},
        {"name": "CANDLE_VOLUME_ASK", "type": "u64",
         "comment": "Cumulative ask ticks this bar"},
        {"name": "CANDLE_TRUE_RANGE_BID", "type": "u64",
         "comment": "bid_high - bid_low"},
        {"name": "CANDLE_TRUE_RANGE_ASK", "type": "u64",
         "comment": "ask_high - ask_low"},
        {"name": "CANDLE_INTRABAR_QTY_DELTA", "type": "u64",
         "comment": "Cumulative (ask_qty - bid_qty) over the bar"},
        {"name": "CANDLE_MID", "type": "u64",
         "comment": "Convenience (bid_high + ask_low) >> 1 (read-only)"},
        {"name": "CANDLE_OPEN_SET", "type": "u64",
         "comment": "Flag: first tick of bar processed (1) / fresh bar (0)"},
        {"name": "CANDLE_LAST_TF_SEQ", "type": "u64",
         "comment": "Last TF_BAR_SEQ seen (bar-boundary edge detect)"},
        {"name": "CANDLE_BID_TICK", "type": "u64",
         "comment": "1 iff bid price differs from last latched bid (tick detect)"},
        {"name": "CANDLE_ASK_TICK", "type": "u64",
         "comment": "1 iff ask price differs from last latched ask (tick detect)"},
        {"name": "CANDLE_BAR_BOUNDARY", "type": "u64",
         "comment": "1 iff timeframe seq changed since last cycle (bar closed)"},
    ],

    # --- combinational logic (candle_architecture.md §3) -----------------------
    # 18 comb_nodes. Each names ONE gate cell and its inputs; gennet expands each
    # into exactly one structural cell call. cell vocabulary (cells.h + emitted
    # cmp_lt): eqmask, mux, buf, addsub, cmp_lt — no native +/-/*, no if/?:.
    "comb_nodes": [
        # 3.1 Tick-detection signals (computed first; XOR 1 inverts eqmask).
        {"name": "CANDLE_BID_TICK", "cell": "eqmask",
         "inputs": ["DOM_BID_PRICE", "CANDLE_BID_CLOSE"],
         "invert": True,
         "comment": "bid_changed = eqmask(DOM_BID_PRICE, CANDLE_BID_CLOSE) ^ 1 (no native !=)"},
        {"name": "CANDLE_ASK_TICK", "cell": "eqmask",
         "inputs": ["DOM_ASK_PRICE", "CANDLE_ASK_CLOSE"],
         "invert": True,
         "comment": "ask_changed = eqmask(DOM_ASK_PRICE, CANDLE_ASK_CLOSE) ^ 1"},

        # 3.2 Bid-side OHLC. mux(a,b,sel)=sel?b:a.
        {"name": "CANDLE_BID_OPEN_UPDATE", "cell": "mux",
         "inputs": ["DOM_BID_PRICE", "CANDLE_BID_OPEN", "CANDLE_OPEN_SET"],
         "comment": "OPEN_SET=0 fresh bar -> latch DOM_BID_PRICE; 1 -> hold CANDLE_BID_OPEN"},
        {"name": "CANDLE_BID_HIGH_UPDATE", "cell": "cmp_lt",
         "inputs": ["CANDLE_BID_HIGH", "DOM_BID_PRICE"],
         "comment": "is_new_high = cmp_lt(CANDLE_BID_HIGH, DOM_BID_PRICE); running max seed override"},
        {"name": "CANDLE_BID_LOW_UPDATE", "cell": "cmp_lt",
         "inputs": ["DOM_BID_PRICE", "CANDLE_BID_LOW"],
         "comment": "is_new_low = cmp_lt(DOM_BID_PRICE, CANDLE_BID_LOW); running min seed override"},
        {"name": "CANDLE_BID_CLOSE_UPDATE", "cell": "buf",
         "inputs": ["DOM_BID_PRICE"],
         "comment": "passthrough — always latch most recent bid"},

        # 3.3 Ask-side OHLC (symmetric to bid).
        {"name": "CANDLE_ASK_OPEN_UPDATE", "cell": "mux",
         "inputs": ["DOM_ASK_PRICE", "CANDLE_ASK_OPEN", "CANDLE_OPEN_SET"],
         "comment": "OPEN_SET=0 fresh bar -> latch DOM_ASK_PRICE; 1 -> hold CANDLE_ASK_OPEN"},
        {"name": "CANDLE_ASK_HIGH_UPDATE", "cell": "cmp_lt",
         "inputs": ["CANDLE_ASK_HIGH", "DOM_ASK_PRICE"],
         "comment": "is_new_high = cmp_lt(CANDLE_ASK_HIGH, DOM_ASK_PRICE)"},
        {"name": "CANDLE_ASK_LOW_UPDATE", "cell": "cmp_lt",
         "inputs": ["DOM_ASK_PRICE", "CANDLE_ASK_LOW"],
         "comment": "is_new_low = cmp_lt(DOM_ASK_PRICE, CANDLE_ASK_LOW)"},
        {"name": "CANDLE_ASK_CLOSE_UPDATE", "cell": "buf",
         "inputs": ["DOM_ASK_PRICE"],
         "comment": "passthrough — always latch most recent ask"},

        # 3.4 Volume accumulation (gated increment). sub=0 -> add.
        {"name": "CANDLE_VOLUME_BID_UPDATE", "cell": "addsub",
         "inputs": ["CANDLE_VOLUME_BID", "CANDLE_BID_TICK"], "sub": 0,
         "comment": "addsub(CANDLE_VOLUME_BID, bid_tick, 0): +1 on bid tick, else +0"},
        {"name": "CANDLE_VOLUME_ASK_UPDATE", "cell": "addsub",
         "inputs": ["CANDLE_VOLUME_ASK", "CANDLE_ASK_TICK"], "sub": 0,
         "comment": "addsub(CANDLE_VOLUME_ASK, ask_tick, 0): +1 on ask tick, else +0"},

        # 3.5 True Range (high - low). sub=1 -> two's-complement subtract.
        {"name": "CANDLE_TRUE_RANGE_BID_UPDATE", "cell": "addsub",
         "inputs": ["CANDLE_BID_HIGH", "CANDLE_BID_LOW"], "sub": 1,
         "comment": "addsub(bid_high, bid_low, 1) = bid_high - bid_low (no native -)"},
        {"name": "CANDLE_TRUE_RANGE_ASK_UPDATE", "cell": "addsub",
         "inputs": ["CANDLE_ASK_HIGH", "CANDLE_ASK_LOW"], "sub": 1,
         "comment": "addsub(ask_high, ask_low, 1) = ask_high - ask_low"},

        # 3.6 Intrabar quantity delta (cumulative ask_qty - bid_qty).
        {"name": "CANDLE_INTRABAR_QTY_DELTA_UPDATE", "cell": "addsub",
         "inputs": ["DOM_ASK_QTY", "DOM_BID_QTY"], "sub": 1,
         "comment": "quote_delta = addsub(DOM_ASK_QTY, DOM_BID_QTY, 1) = ask - bid (DECISIONS §A)"},

        # 3.7 Convenience mid (non-blocking). >>1 is the structural /2 on the sum.
        {"name": "CANDLE_MID_UPDATE", "cell": "addsub",
         "inputs": ["CANDLE_BID_HIGH", "CANDLE_ASK_LOW"], "sub": 0,
         "shift_right": 1,
         "comment": "addsub(bid_high, ask_low, 0) >> 1 = (bid_high + ask_low)/2 (power-of-two /2)"},

        # 3.8 Bar-boundary detection (eqmask=1 unchanged; XOR 1 -> 1 on change).
        {"name": "CANDLE_BAR_BOUNDARY", "cell": "eqmask",
         "inputs": ["CANDLE_LAST_TF_SEQ", "TF_BAR_SEQ_REG"],
         "invert": True,
         "comment": "bar_boundary = eqmask(CANDLE_LAST_TF_SEQ, TF_BAR_SEQ_REG) ^ 1 (seq changed)"},

        # 3.9 Bar-control: OPEN_SET. mux(1,0,bar_boundary): 0 on boundary else 1.
        {"name": "CANDLE_OPEN_SET_UPDATE", "cell": "mux",
         "inputs": ["CANDLE_OPEN_SET_HOLD", "CANDLE_OPEN_SET_FRESH", "CANDLE_BAR_BOUNDARY"],
         "comment": "mux(1, 0, bar_boundary): boundary -> 0 (force seed), else hold 1 (open)"},
    ],

    # constant lanes referenced by comb_node inputs (e.g. OPEN_SET mux arms).
    # Driven once at reset by the starter; never written by the device tick.
    "const_nodes": [
        {"name": "CANDLE_OPEN_SET_HOLD", "type": "u64", "value": 1,
         "comment": "mux arm a for OPEN_SET (steady-state value held off-boundary)"},
        {"name": "CANDLE_OPEN_SET_FRESH", "type": "u64", "value": 0,
         "comment": "mux arm b for OPEN_SET (fresh-bar value latched on boundary)"},
    ],
}


def main():
    """Emit the netlist as JSON to stdout."""
    import sys
    json.dump(NET, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
