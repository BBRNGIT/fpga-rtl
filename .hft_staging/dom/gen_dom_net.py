#!/usr/bin/env python3
"""gen_dom_net.py — EMITTER: writes dom.net.json.

Emits the netlist for DOM (Depth-of-Market) — the first internal-domain consumer
past the CDC FIFO. Each device edge DOM samples the fifo_rx head slot (the packet
the pipeline would pop), gated by fifo_rx's read-fire, and maintains the order
book: price-indexed qty/count/time tables, best-bid/ask tracking, running totals,
derived spread/mid, diagnostic event counters, and the 10-level relay ladders the
indicators read. Source spec: ../DOM_PARTS_LIST.md (the named authoritative list).

The device tick is GENERATED from this netlist by gennet.py — never hand-written.
All datapath ops are gate-level: presence/increment via cell_addsub, selection via
cell_mux, equality via cell_eqmask, derived spread via cell_addsub — NO native
+/-/* on data in the generated tick (gate-level arithmetic law). The price index
and table addressing are ADDRESS math (a power-of-two mask), the same dispensation
cells.h takes for its loop counter — outside the data-path operator ban.

Module-barrier: DOM SAMPLES the fifo_rx published window (the head slot at the read
pointer + RD_FIRE/EMPTY flags), read from fifo_rx_gen.h via the producer's own
generated address helper (fifo_rx_head_addr). DOM writes ONLY its own DOM_* window.
No private copy of the FIFO map.

Address window: 0x2100000 (next free above graduated fifo_rx @ 0x2000000; every
window below is an owned sibling). DOM_PARTS_LIST §12 names 0x0C00000 but marks it
"exact value TBD"; DOM_ARCHITECTURE independently names 0x2100000. Flagged in
DOM.md; the window base is a one-line change here if the founder wants the literal.
"""
import json

# --- price-index table depth (power of two: index is a branchless mask). The four
# tables are ADDRESSED regions (not per-cell unrolled); the tick reads/writes the
# addressed cell at the computed index. PARTS_LIST §2 names 16384. ----------------
TABLE_DEPTH = 16384
RELAY_LEVELS = 10            # PARTS_LIST §8: top-10 ladder per side, 0 = best

# the fifo_rx head-slot lanes DOM samples (lane order = fifo_rx PACKET_LANES; the
# offset is the lane index into fifo_rx_head_addr). DOM reads these from the FIFO
# published window — it does NOT redeclare them as DOM nodes (module barrier).
FIFO_HEAD_LANES = [
    "BID_PX", "ASK_PX", "TIME", "SRC_TIME",
    "SYMBOL", "PIP", "COMMISSION", "SEQ",
]
FIFO_HEAD_OFS = {ln: i for i, ln in enumerate(FIFO_HEAD_LANES)}

# scalar dff registers DOM owns (PARTS_LIST §3-§7, §9). Order is the address order.
SCALAR_DFFS = [
    "DOM_BEST_BID_PRICE_REG", "DOM_BEST_BID_QTY_REG",
    "DOM_BEST_ASK_PRICE_REG", "DOM_BEST_ASK_QTY_REG",
    "DOM_TOTAL_BID_QTY_REG", "DOM_TOTAL_ASK_QTY_REG",
    "DOM_PKT_COUNT_REG", "DOM_ADD_COUNT_REG",
    "DOM_CANCEL_COUNT_REG", "DOM_TRADE_COUNT_REG",
    "DOM_LAST_FEED_TIME_REG",
    "DOM_PREV_BID_PRICE", "DOM_PREV_ASK_PRICE",
]
# combinational (derived, recomputed each edge but registered for the consumer).
COMB_DERIVED = ["DOM_SPREAD_REG", "DOM_MID_PRICE_REG"]


def relay_nodes():
    """The 40 relay ladder registers (10 levels x {bid,ask} x {price,qty})."""
    names = []
    for side in ("BID", "ASK"):
        for what in ("PRICE", "QTY"):
            for i in range(RELAY_LEVELS):
                names.append(f"DOM_REL_{side}_{what}_{i}")
    return names


# the four price-indexed tables (addressed regions; depth = TABLE_DEPTH each).
TABLES = [
    {"name": "DOM_BID_QTY",  "fed_by": "addsub",
     "comment": "per-level bid presence/qty: 1 when the new bid index, else 0 (PARTS_LIST §2)"},
    {"name": "DOM_ASK_QTY",  "fed_by": "addsub",
     "comment": "per-level ask presence/qty: 1 when the new ask index, else 0 (PARTS_LIST §2)"},
    {"name": "DOM_COUNT",    "fed_by": "addsub",
     "comment": "per-level event counter: += 1 when level i touched (PARTS_LIST §2)"},
    {"name": "DOM_TIME",     "fed_by": "mux",
     "comment": "per-level timestamp latch: latch head TAI when level i touched (PARTS_LIST §2)"},
]

NET = {
    "device": "dom",
    "window_base": "0x2100000",
    "kind": "order_book",
    "clock": "internal",
    "table_depth": TABLE_DEPTH,
    "relay_levels": RELAY_LEVELS,
    "comment": (
        "DOM — the order book. On the internal edge: sample the fifo_rx head slot "
        "(gated by FIFO_RD_FIRE & ~FIFO_EMPTY), detect bid/ask price change vs the "
        "PREV registers (branchless eqmask), index the price tables by mask, update "
        "the addressed bid/ask/count/time cells (presence model: set 1 / clear 0; "
        "count += 1; time latch), eagerly track best bid/ask, accumulate running "
        "totals, derive spread/mid (guarded by ask-valid), publish the 10-level "
        "relay ladders, bump the diagnostic counters, and latch the feed time + "
        "prev prices. Single internal domain (the MAC->internal CDC is upstream in "
        "fifo_rx). Presence model per PARTS_LIST: no trade/CVD/qty-accumulation "
        "(price-only data law; TRADE_COUNT kept = 0 for API compat)."
    ),

    # --- the fifo_rx head lanes DOM SAMPLES (read from fifo_rx_gen.h via the
    # producer's generated head-address helper; NOT redeclared as DOM nodes). ------
    "fifo_head_lanes": FIFO_HEAD_LANES,
    "fifo_head_ofs": FIFO_HEAD_OFS,
    "fifo_fire": "FIFO_FIFO_RD_FIRE",     # consume gate (fifo_rx published flag)
    "fifo_empty": "FIFO_FIFO_EMPTY",      # validity (fifo_rx published flag)

    # --- config / input lanes (set once by the starter). ----------------------
    "config_nodes": [
        {"name": "DOM_POWER", "type": "bit",
         "comment": "power/enable: DOM self-runs on its clock edge while bit0 = 1 (set once)"},
        {"name": "DOM_RUN_UNTIL", "type": "u64",
         "comment": "configured self-run tick budget (set once by starter)"},
        {"name": "DOM_SESSION_BASE", "type": "u64",
         "comment": "session base price: idx = (price - SESSION_BASE) & (depth-1). Config (set once)."},
        {"name": "DOM_PIP_RES", "type": "u64",
         "comment": "pip resolution for the relay ladder step (best +/- (i+1)*PIP_RES). Config."}
    ],

    # --- registered state (dffs), all DOM-owned. ------------------------------
    "dff_nodes": (
        [{"name": "DOM_TICKS", "type": "u64",
          "comment": "self-run tick counter (run-loop bookkeeping; bounds the self-run)"}]
        + [{"name": n, "type": "u64", "comment": "scalar order-book register (PARTS_LIST §3-§9)"}
           for n in SCALAR_DFFS]
        + [{"name": n, "type": "u64", "comment": "relay ladder lane (PARTS_LIST §8)"}
           for n in relay_nodes()]
    ),

    # --- combinational derived outputs (registered for the consumer each edge). -
    "comb_nodes": [
        {"name": n, "type": "u64", "comment": "derived register (PARTS_LIST §5)"}
        for n in COMB_DERIVED
    ],

    # --- the four price-indexed tables (addressed regions, depth each). ---------
    "tables": [
        {"name": t["name"], "depth": TABLE_DEPTH, "fed_by": t["fed_by"],
         "comment": t["comment"]}
        for t in TABLES
    ],

    # --- the wiring the gennet consumes (named so the generator + validator agree).
    "wiring": {
        "head_bid": "BID_PX", "head_ask": "ASK_PX", "head_tai": "TIME",
        "prev_bid": "DOM_PREV_BID_PRICE", "prev_ask": "DOM_PREV_ASK_PRICE",
        "best_bid_price": "DOM_BEST_BID_PRICE_REG", "best_bid_qty": "DOM_BEST_BID_QTY_REG",
        "best_ask_price": "DOM_BEST_ASK_PRICE_REG", "best_ask_qty": "DOM_BEST_ASK_QTY_REG",
        "total_bid": "DOM_TOTAL_BID_QTY_REG", "total_ask": "DOM_TOTAL_ASK_QTY_REG",
        "spread": "DOM_SPREAD_REG", "mid": "DOM_MID_PRICE_REG",
        "pkt_count": "DOM_PKT_COUNT_REG", "add_count": "DOM_ADD_COUNT_REG",
        "cancel_count": "DOM_CANCEL_COUNT_REG", "trade_count": "DOM_TRADE_COUNT_REG",
        "last_feed_time": "DOM_LAST_FEED_TIME_REG",
        "bid_qty_table": "DOM_BID_QTY", "ask_qty_table": "DOM_ASK_QTY",
        "count_table": "DOM_COUNT", "time_table": "DOM_TIME",
        "session_base": "DOM_SESSION_BASE", "pip_res": "DOM_PIP_RES",
    },

    "power": "DOM_POWER",
    "run": {"power": "DOM_POWER", "count": "DOM_TICKS", "limit": "DOM_RUN_UNTIL"}
}


def main():
    if TABLE_DEPTH <= 0 or (TABLE_DEPTH & (TABLE_DEPTH - 1)) != 0:
        raise SystemExit(
            f"gen_dom_net: table_depth ({TABLE_DEPTH}) must be a power of two "
            f"(price index is a branchless mask: (price - base) & (depth-1)).")
    with open("dom.net.json", "w") as f:
        json.dump(NET, f, indent=2)
        f.write("\n")
    nscalar = 1 + len(SCALAR_DFFS) + len(COMB_DERIVED)
    print(f"emitted dom.net.json (table_depth {TABLE_DEPTH}, {len(relay_nodes())} relay "
          f"lanes, {nscalar} scalar regs, {len(TABLES)} price tables)")


if __name__ == "__main__":
    main()
