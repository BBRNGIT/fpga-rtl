# CANDLE_SPEC_V2 — Complete Flip-Flop-Level Specification (Phase 2 prep)

**Status:** SPECIFICATION ONLY. No addresses, no placement, no cross-module
wiring assignment — those are separate founder-assigned tasks. All cross-module
inputs are referenced by SYMBOLIC seam-register name only.

**Fixes:** WAVE_1_AUDIT.md root cause — the prior spec/netlist documented
registers (dff_nodes) but no complete comb_nodes / wiring / fed_by
attribution. This document specifies EVERY combinational node with its cell
type, inputs, and the register it feeds, plus the completed-bar latch and the
history ring that were entirely absent from the stub.

**Machine-readable companion:** `candle_logic.yaml` (same directory) — emitter
input for the forthcoming `gen_device_specialization` build mode.

---

## 0. Module Role and Clocking

Candle accumulates dual OHLC (bid-side and ask-side), tick volume, true range
and intrabar quantity delta per timeframe bar, snapshots the completed bar at
the bar boundary, and appends it to a branchless history ring.

**Clock conformance (founder clock law, `checks/check_clock_rule.py`):**
Candle is a **passive consumer**. It owns NO clock: the netlist declares no
`clock`, `counter`, `edge`, `run`, `run_power`, or `run_bound` section. Its
tick is invoked by the device composition on the host clock domain; bar timing
comes entirely from the timeframe module's published seam registers. The
clock-rule checker passes quietly on such a netlist (no clock owned = nothing
to enforce). No POWER/RUN_UNTIL registers are therefore required or declared.

---

## 1. Input Interface (Seam Registers Consumed — symbolic names only)

From **DOM** (`dom.net.json`, published `wiring` map — these are the real
registered seam names; the stub's invented `DOM_BID_PRICE` / `DOM_ASK_PRICE`
do not exist in the DOM netlist and are corrected here):

| Symbolic seam register     | DOM netlist name          | Use |
|----------------------------|---------------------------|-----|
| `DOM_BEST_BID_PRICE_REG`   | wiring.best_bid_price     | bid OHLC source |
| `DOM_BEST_ASK_PRICE_REG`   | wiring.best_ask_price     | ask OHLC source |
| `DOM_BEST_BID_QTY_REG`     | wiring.best_bid_qty       | intrabar delta |
| `DOM_BEST_ASK_QTY_REG`     | wiring.best_ask_qty       | intrabar delta |

From **Timeframe** (`timeframe.net.json`, published top-level seam keys):

| Symbolic seam register | Timeframe netlist name | Use |
|------------------------|------------------------|-----|
| `TF_BAR_SEQ`           | bar_seq                | bar-boundary edge detect |
| `TF_BAR_START`         | bar_start              | bar-open TAI stamp (COMP_TAI) |

These appear in the candle netlist as `config_nodes` (input lanes, module
barrier per the timeframe pattern: sampled onto candle's own input lanes by
the device-level wiring task — NOT addressed here).

Single-writer law: candle only READS these lanes; it writes only `CANDLE_*`
registers.

Data law: every output derives from bid, ask, qty, time primitives. No
invented fields. No floats (mid uses power-of-two shift, not division).

---

## 2. Register Definitions (dff_nodes)

### 2.1 Live registers (reused from the stub netlist, kept as-is)

| Register | Type | Function |
|---|---|---|
| CANDLE_BID_OPEN | u64 | first bid price of bar |
| CANDLE_BID_HIGH | u64 | running max bid price |
| CANDLE_BID_LOW  | u64 | running min bid price |
| CANDLE_BID_CLOSE| u64 | most recent bid (doubles as prev-bid for tick detect) |
| CANDLE_ASK_OPEN | u64 | first ask price of bar |
| CANDLE_ASK_HIGH | u64 | running max ask price |
| CANDLE_ASK_LOW  | u64 | running min ask price |
| CANDLE_ASK_CLOSE| u64 | most recent ask (doubles as prev-ask for tick detect) |
| CANDLE_VOLUME_BID | u64 | cumulative bid ticks this bar |
| CANDLE_VOLUME_ASK | u64 | cumulative ask ticks this bar |
| CANDLE_TRUE_RANGE_BID | u64 | bid_high − bid_low |
| CANDLE_TRUE_RANGE_ASK | u64 | ask_high − ask_low |
| CANDLE_INTRABAR_QTY_DELTA | u64 | Σ(ask_qty − bid_qty) over bar |
| CANDLE_MID | u64 | (bid_high + ask_low) >> 1 convenience |
| CANDLE_OPEN_SET | u64 | bit0: 1 after first tick of bar latched |
| CANDLE_LAST_TF_SEQ | u64 | last TF_BAR_SEQ seen (edge detect) |
| CANDLE_BID_TICK | u64 | registered: bid changed last tick |
| CANDLE_ASK_TICK | u64 | registered: ask changed last tick |
| CANDLE_BAR_BOUNDARY | u64 | registered: boundary pulse last tick |

### 2.2 NEW working registers (extension required by complete logic)

| Register | Type | Function |
|---|---|---|
| CANDLE_BAR_SEQ | u64 | candle's own completed-bar counter (ring write cursor) |

### 2.3 NEW completed-bar snapshot registers (latched en=boundary)

CANDLE_COMP_BID_OPEN, CANDLE_COMP_BID_HIGH, CANDLE_COMP_BID_LOW,
CANDLE_COMP_BID_CLOSE, CANDLE_COMP_ASK_OPEN, CANDLE_COMP_ASK_HIGH,
CANDLE_COMP_ASK_LOW, CANDLE_COMP_ASK_CLOSE, CANDLE_COMP_VOLUME_BID,
CANDLE_COMP_VOLUME_ASK, CANDLE_COMP_TRUE_RANGE_BID,
CANDLE_COMP_TRUE_RANGE_ASK, CANDLE_COMP_INTRABAR_QTY_DELTA,
CANDLE_COMP_TAI (= TF_BAR_START of the closed bar), CANDLE_COMP_BAR_SEQ.
All u64, all dff with en = CANDLE_BAR_BOUNDARY_NOW.

### 2.4 History ring (adapter display_ring pattern — branchless indexing)

```
ring: CANDLE_HIST
  depth: 256              (POWER OF TWO — required for the mask index cell)
  fields (15 per slot):   BID_OPEN BID_HIGH BID_LOW BID_CLOSE
                          ASK_OPEN ASK_HIGH ASK_LOW ASK_CLOSE
                          VOLUME_BID VOLUME_ASK TRUE_RANGE_BID TRUE_RANGE_ASK
                          INTRABAR_QTY_DELTA TAI BAR_SEQ
  count register:         CANDLE_BAR_SEQ
  slot index:             cell_and(CANDLE_BAR_SEQ, CANDLE_HIST_MASK)   [no %]
  write enable:           CANDLE_BAR_BOUNDARY_NOW
```

`CANDLE_HIST_MASK` is a const_node = depth−1 = 255 (register-backed constant,
no literal in the data path). Slot addressing is generator-level expansion
(one dff per slot×field; slot enable = cell_eqmask(slot_const_i, slot_idx)
AND boundary — one-hot select per CELLS.md table-select pattern), exactly as
adapter's gennet expands `display_ring`.

### 2.5 const_nodes

| Const | Value | Use |
|---|---|---|
| CANDLE_ONE | 1 | open_set hold value; bar_seq increment |
| CANDLE_ZERO | 0 | fresh-bar resets (volume, delta, open_set) |
| CANDLE_HIST_MASK | 255 | ring index mask (depth−1) |

---

## 3. READ → COMPUTE → WRITE Behavior (per clock edge)

### READ phase
Pre-read every input lane and every dff into locals:
`dom_best_bid_price, dom_best_ask_price, dom_best_bid_qty, dom_best_ask_qty,
tf_bar_seq, tf_bar_start` + all `CANDLE_*` dffs.

### COMPUTE phase — every comb_node, with cell, inputs, fed_by

Comparators `cmp_lt(a,b)` / `cmp_le(a,b)` are GATE NETLISTS: the 64-bit
carry chain of `cell_fa` cells computing a + ~b + 1 and returning the final
carry-out (cmp_le returns carry; cmp_lt(a,b) ≡ cmp_le(a,b) AND NOT eqmask(a,b),
or equivalently NOT cmp_le(b,a)) — adapter gennet's `cmp_le` is the reference
expansion. They are emitted by gennet as cell compositions, never native `<`.

**Boundary / tick detection (order matters — uses registered prevs):**

| # | comb node | cell | inputs | feeds (fed_by) |
|---|---|---|---|---|
| 1 | bar_seq_same | eqmask | CANDLE_LAST_TF_SEQ, TF_BAR_SEQ | — (intermediate) |
| 2 | bar_boundary_now | not | bar_seq_same | CANDLE_BAR_BOUNDARY (dff, en=1); all boundary muxes (bit0 used) |
| 3 | not_boundary | eqmask | bar_seq_same, bar_seq_same | — note: identically 1; instead use: not_boundary = bar_seq_same (bit0). Alias node, cell buf, input bar_seq_same |
| 4 | bid_tick_now | eqmask(+not) | DOM_BEST_BID_PRICE_REG, CANDLE_BID_CLOSE → cell_not, bit0 | CANDLE_BID_TICK (dff, en=1); volume add |
| 5 | ask_tick_now | eqmask(+not) | DOM_BEST_ASK_PRICE_REG, CANDLE_ASK_CLOSE → cell_not, bit0 | CANDLE_ASK_TICK (dff, en=1); volume add |

(`bit0` discipline: eqmask/not chains are masked `cell_and(x, CANDLE_ONE)`
when used as a mux select or addend, so only bit0 propagates.)

**Bid OHLC:**

| # | comb node | cell | inputs | feeds |
|---|---|---|---|---|
| 6 | open_seed_bid | mux | a=DOM_BEST_BID_PRICE_REG, b=CANDLE_BID_OPEN, sel=CANDLE_OPEN_SET | — |
| 7 | bid_open_next | mux | a=open_seed_bid, b=DOM_BEST_BID_PRICE_REG, sel=bar_boundary_now | CANDLE_BID_OPEN (dff, en=1). On boundary: re-seed with current price (new bar opens at first quote); else latch-or-hold per OPEN_SET |
| 8 | is_new_bid_high | cmp_lt | CANDLE_BID_HIGH, DOM_BEST_BID_PRICE_REG | — |
| 9 | bid_high_run | mux | a=CANDLE_BID_HIGH, b=DOM_BEST_BID_PRICE_REG, sel=is_new_bid_high | — |
| 10 | bid_high_next | mux | a=bid_high_run, b=DOM_BEST_BID_PRICE_REG, sel=bar_boundary_now | CANDLE_BID_HIGH (dff). Boundary re-seeds high=current price |
| 11 | is_new_bid_low | cmp_lt | DOM_BEST_BID_PRICE_REG, CANDLE_BID_LOW | — |
| 12 | bid_low_run | mux | a=CANDLE_BID_LOW, b=DOM_BEST_BID_PRICE_REG, sel=is_new_bid_low | — |
| 13 | bid_low_next | mux | a=bid_low_run, b=DOM_BEST_BID_PRICE_REG, sel=bar_boundary_now | CANDLE_BID_LOW (dff). Boundary re-seeds low=current price (fixes stub's unseeded min-of-zero bug) |
| 14 | bid_close_next | buf | DOM_BEST_BID_PRICE_REG | CANDLE_BID_CLOSE (dff) |

**Ask OHLC (symmetric, nodes 15–23):** identical structure with
DOM_BEST_ASK_PRICE_REG / CANDLE_ASK_* → CANDLE_ASK_OPEN, CANDLE_ASK_HIGH,
CANDLE_ASK_LOW, CANDLE_ASK_CLOSE.

**Volume (tick counting; reset on boundary):**

| # | comb node | cell | inputs | feeds |
|---|---|---|---|---|
| 24 | vol_bid_base | gate | val=CANDLE_VOLUME_BID, en=not_boundary | — (0 on boundary → bar reset) |
| 25 | bid_tick_bit | and | bid_tick_now, CANDLE_ONE | — |
| 26 | vol_bid_next | addsub(sub=0) | vol_bid_base, bid_tick_bit | CANDLE_VOLUME_BID (dff) |
| 27–29 | vol_ask_base / ask_tick_bit / vol_ask_next | gate / and / addsub(0) | (ask mirror) | CANDLE_VOLUME_ASK (dff) |

**True range (derived each tick from next high/low):**

| # | comb node | cell | inputs | feeds |
|---|---|---|---|---|
| 30 | tr_bid_next | addsub(sub=1) | bid_high_next, bid_low_next | CANDLE_TRUE_RANGE_BID (dff) |
| 31 | tr_ask_next | addsub(sub=1) | ask_high_next, ask_low_next | CANDLE_TRUE_RANGE_ASK (dff) |

**Intrabar quantity delta (reset on boundary):**

| # | comb node | cell | inputs | feeds |
|---|---|---|---|---|
| 32 | quote_delta | addsub(sub=1) | DOM_BEST_ASK_QTY_REG, DOM_BEST_BID_QTY_REG | — |
| 33 | delta_base | gate | val=CANDLE_INTRABAR_QTY_DELTA, en=not_boundary | — |
| 34 | delta_next | addsub(sub=0) | delta_base, quote_delta | CANDLE_INTRABAR_QTY_DELTA (dff) |

**Mid (power-of-two shift, NO division):**

| # | comb node | cell | inputs | feeds |
|---|---|---|---|---|
| 35 | mid_sum | addsub(sub=0) | bid_high_next, ask_low_next | — |
| 36 | mid_next | sar(shift=1) | mid_sum | CANDLE_MID (dff). `cell_sar` shift-right-1 = /2; generator-level bit-select expansion if cell_sar is not yet in canon (see open decision D4) |

**Open-set flag and TF edge bookkeeping:**

| # | comb node | cell | inputs | feeds |
|---|---|---|---|---|
| 37 | open_set_next | mux | a=CANDLE_ONE, b=CANDLE_ZERO, sel=bar_boundary_now | CANDLE_OPEN_SET (dff). Boundary→0 (fresh), else 1 |
| 38 | last_tf_next | buf | TF_BAR_SEQ | CANDLE_LAST_TF_SEQ (dff) |

**Completed-bar latch + bar counter + ring (the parts absent from the stub):**

| # | comb node | cell | inputs | feeds |
|---|---|---|---|---|
| 39 | bar_seq_inc | addsub(sub=0) | CANDLE_BAR_SEQ, CANDLE_ONE | — |
| 40 | bar_seq_next | mux | a=CANDLE_BAR_SEQ, b=bar_seq_inc, sel=bar_boundary_now | CANDLE_BAR_SEQ (dff) |
| 41 | hist_slot_idx | and | CANDLE_BAR_SEQ, CANDLE_HIST_MASK | ring slot select (one-hot eqmask fan-out, generator-expanded) |
| 42–56 | comp_*_latch ×15 | dff(en=bar_boundary_now) | d = the CLOSING value of each live register (the pre-boundary held value: CANDLE_BID_OPEN, CANDLE_BID_HIGH, …, CANDLE_INTRABAR_QTY_DELTA, TF_BAR_START, CANDLE_BAR_SEQ) | CANDLE_COMP_* (15 dffs) |
| 57.. | hist_slot_en_i | eqmask+and | eqmask(slot_const_i, hist_slot_idx) AND bar_boundary_now | ring slot i write enable (depth×15 dffs, en=hist_slot_en_i, d=comp values) — generator expansion, same as adapter display_ring |

### WRITE phase
Commit every dff exactly once, no read-after-write:
all live registers ← their `*_next` nodes (en=1 via cell_dff), COMP_* ←
closing values (en=boundary), ring slots ← COMP values (en=slot one-hot AND
boundary), CANDLE_BAR_SEQ ← bar_seq_next, CANDLE_LAST_TF_SEQ ← TF_BAR_SEQ.

Single-writer: each register has exactly one driving node (the `feeds` column
above is total and unique). No floating nodes: every comb node above is
consumed by a dff or another comb node.

---

## 4. Output Interface (Seam Nodes Published)

| Seam group | Lanes |
|---|---|
| CANDLE_LIVE_OUT | CANDLE_BID_OPEN/HIGH/LOW/CLOSE, CANDLE_ASK_OPEN/HIGH/LOW/CLOSE, CANDLE_MID |
| CANDLE_VOLUME_OUT | CANDLE_VOLUME_BID, CANDLE_VOLUME_ASK |
| CANDLE_TRUE_RANGE_OUT | CANDLE_TRUE_RANGE_BID, CANDLE_TRUE_RANGE_ASK |
| CANDLE_DELTA_OUT | CANDLE_INTRABAR_QTY_DELTA |
| CANDLE_COMP_OUT | all 15 CANDLE_COMP_* (consumed by fractal, CBR) |
| CANDLE_HIST_OUT | ring (256×15) + CANDLE_BAR_SEQ (consumed by fractal) |

---

## 5. Open Decisions for the Founder (do not silently choose)

- **D1 — History ring depth.** Recommended default: **256** (power of two,
  matches INDICATOR_ARCHITECTURE_TEMPLATE). Alternatives: 64 (fractal needs
  only ~5 bars), 1024 (deeper lookback). Affects register count: depth×15.
- **D2 — Boundary re-seed semantics.** Recommended default: **re-seed
  OHLC with the price present AT the boundary tick** (nodes 7/10/13: new bar
  opens at the quote standing when the bar rolls). Alternative: hold stale
  values until the first tick-change of the new bar (pure OPEN_SET latch).
- **D3 — Bar-open timestamp source.** Recommended default: **TF_BAR_START**
  (timeframe's published bar-open TAI). Alternative: a candle-local latch of
  DOM_LAST_FEED_TIME_REG at first tick of bar.
- **D4 — cell_sar canon status.** CANDLE_MID needs a 1-bit right shift.
  Recommended default: **add `cell_sar` (or a buf-with-shift generator
  expansion) to the canonical cells.h first** (CELLS.md "planned" section
  path); alternative: drop CANDLE_MID from the live set and let consumers
  derive it.
- **D5 — Volume definition.** Recommended default: **tick count** (number of
  best-price changes, per stub semantics). Alternative: qty-weighted
  (accumulate DOM_BEST_*_QTY_REG on tick) — still data-law-clean.
