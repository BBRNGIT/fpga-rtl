# Footprint Indicator — Flip-Flop-Level Architecture

**Purpose:** Complete gate-level (RTL) specification for the footprint (order-flow imprint)
indicator. This document supplies the **combinational logic** (`comb_nodes`) and **wiring** that
`footprint.yaml` is missing (per `WAVE_1_AUDIT.md`), so the emitter-first pipeline produces real
flip-flop logic instead of a register stub.

**Pipeline position:** `tools/generators/footprint.yaml` (spec) → `gen_footprint_net.py` (emitter)
→ `footprint.net.json` (netlist) → `gennet.py` (generator) → `footprint_gen.h` (device C).

**Clock domain:** internal / pipeline FPGA (250 MHz). All inputs arrive on published DOM /
timeframe lanes already in-domain — no CDC inside footprint.

**Status:** Architecture complete; ready to fold into `footprint.yaml` `comb_nodes`.

---

## Gate Primitive Vocabulary (authoritative signatures)

These are the **only** primitives permitted in the COMPUTE phase. Signatures are taken verbatim
from `cells.h`. **Note the argument order of `cell_mux` — it is `(false_case, true_case, sel)`,
NOT `(sel, true, false)`.** All logic below is written in the real `cells.h` order.

| Cell | Signature | Meaning |
|---|---|---|
| `cell_addsub` | `cell_addsub(a, b, sub)` | `sub=0 → a+b`; `sub=1 → a-b` (two's complement). Returns 64-bit **sum word**. |
| `cell_mux` | `cell_mux(a, b, sel)` | `sel ? b : a`. `a` = hold/false value, `b` = new/true value, `sel` = bit0 selector. |
| `cell_eqmask` | `cell_eqmask(a, b)` | `1` (bit0) iff `a == b`, else `0`. Branchless zero-reduction equality. |
| `cell_gate` | `cell_gate(val, en)` | `en ? val : 0`. Power-gates a value to zero. |
| `cmp_lt` | `cmp_lt(a, b)` | `1` iff `a < b`, else `0`. The **less-than comparator netlist**: the final carry-out of the `a - b` ripple-carry subtract chain (carry-out = 0 ⇒ borrow ⇒ `a < b`). Same carry chain as `cell_addsub`, but returns the **carry bit**, not the sum word. Referred to as `cell_cmp_lt` in `INDICATOR_ARCHITECTURE_TEMPLATE.md`; identical primitive. |
| `cell_and` / `cell_or` / `cell_xor` / `cell_not` | bitwise | Boolean glue for combining selector bits (e.g. AND two conditions). |

**Greater-than** is expressed as `cmp_lt(b, a)`. **`a >= b`** is `cell_not(cmp_lt(a, b)) & 1`.
There is no native `<`, `>`, `==`, `?:`, `+`, `-`, `if`, or loop anywhere below.

---

## 1. Input Interface

All inputs are sampled in the READ phase from **published lanes only** (module-barrier law — never
read DOM or timeframe internals).

### From DOM (price-indexed depth-of-market tables)

| Lane | Type | Indexing | Role |
|---|---|---|---|
| `DOM_ASK_QTY[PRICE_IDX]` | u64 | per price level | Ask quantity resting at the level — the ask side of footprint volume. |
| `DOM_BID_QTY[PRICE_IDX]` | u64 | per price level | Bid quantity resting at the level — the bid side of footprint volume. |
| `DOM_COUNT[PRICE_IDX]` | u64 | per price level | Event count per level (trade activity intensity). |
| `DOM_TIME[PRICE_IDX]` | u64 | per price level | Latest TAI timestamp touching the level. |

`PRICE_IDX` is the dense 0..16383 price-bucket index DOM already maintains. Footprint **reuses the
same index space** so its `FP_ASK_VOL` / `FP_BID_VOL` / `FP_PROFILE` tables align 1:1 with DOM.

### From Timeframe

| Lane | Type | Role |
|---|---|---|
| `TF_BAR_SEQ_REG` | u64 | Bar sequence counter. Increments on each bar close. Edge vs. `FP_LAST_TF_SEQ` is the **only** bar-boundary trigger. |

### Implicit iteration model (no C loops)

Per-price work (`POC_PRICE_UPDATE`, `VAH/VAL`, `STACKED_IMBALANCE`) is expressed **per index**, not
as a C `for` loop. The emitter unrolls the index space into the netlist; the generator instantiates
one gate chain per active level. The COMPUTE phase that runs each tick processes the **current
level** `PRICE_IDX` (the level the active quote touched, derived from the DOM update), folding it
into the running aggregates held in DFFs. Table indexing — not loop iteration — drives coverage of
the price ladder. (See `INDICATOR_ARCHITECTURE_TEMPLATE.md` §"Key Constraints": *iteration over
price levels happens implicitly via table indexing, not C loops*.)

---

## 2. Register State

Organized by function. All are `u64` DFF nodes (`dff_nodes` in YAML) unless marked as a table.

### POC tracking (running-maximum volume)

| Register | Role |
|---|---|
| `FP_POC_PRICE` | Price index of the level holding the maximum total volume (the Point of Control). |
| `FP_POC_VOL` | Total volume (ask+bid) at the POC level — the running maximum being tracked. |
| `FP_POC_ASK_VOL` | Ask-side volume at the POC level. |
| `FP_POC_BID_VOL` | Bid-side volume at the POC level. |
| `FP_DELTA` | POC-level delta = `ask_vol − bid_vol` at the POC level. |

### Value area / diagonal imbalance (HVN/LVN)

| Register | Role |
|---|---|
| `FP_VAH_PRICE` | Value Area High — highest price index where ask volume dominates bid (`ask > bid`). |
| `FP_VAL_PRICE` | Value Area Low — lowest price index where bid volume dominates ask (`bid > ask`). |
| `FP_ASK_IMB_PRICE` | Price index of the strongest ask-imbalanced level (High Volume Node, HVN). |
| `FP_BID_IMB_PRICE` | Price index of the strongest bid-imbalanced level (Low Volume Node, LVN). |

### Bar state (per-bar running aggregates + reset bookkeeping)

| Register | Role |
|---|---|
| `FP_MIN_PRICE` | Lowest price index touched this bar (running minimum). |
| `FP_MAX_PRICE` | Highest price index touched this bar (running maximum). |
| `FP_BAR_CUM_DELTA` | Cumulative Volume Delta (CVD) — running `Σ(ask_qty − bid_qty)` across the bar. |
| `FP_BAR_TOTAL_VOL` | Total bar volume (running `Σ(ask_qty + bid_qty)`). |
| `FP_BAR_PARITY` | Virtual-reset parity tag (bit 63 of per-level table entries). Toggles each bar close; see §6. |
| `FP_LAST_TF_SEQ` | Last `TF_BAR_SEQ` observed — edge detector for bar boundary. |
| `FP_BAR_SEQ` | Footprint's own bar sequence counter. |

### Stacked imbalance (consecutive imbalanced levels)

| Register | Role |
|---|---|
| `FP_STACKED_IMB_BUY` | Count of consecutive ask-imbalanced levels **above** POC (buy-side stack). |
| `FP_STACKED_IMB_SELL` | Count of consecutive bid-imbalanced levels **below** POC (sell-side stack). |

### Tables (price-indexed accumulators, depth 16384, indexed by `PRICE_IDX`)

| Table | Role |
|---|---|
| `FP_ASK_VOL[PRICE_IDX]` | Per-level ask volume accumulator (parity-tagged in bit 63). |
| `FP_BID_VOL[PRICE_IDX]` | Per-level bid volume accumulator (parity-tagged in bit 63). |
| `FP_PROFILE[PRICE_IDX]` | Per-level total volume (`ask+bid`) — the volume profile. |

### Snapshot / history (written on bar close — see §6)

`FP_HIST_*` ring (depth 256): `POC_PRICE`, `VAH_PRICE`, `VAL_PRICE`, `NET_DELTA`, `TOTAL_VOL`,
`BAR_SEQ`, `ASK_IMB_PRICE`, `BID_IMB_PRICE`, `POC_DELTA`, `STK_BUY`, `STK_SELL`, `MIN_PRICE`,
`MAX_PRICE`, `BAR_TAI`.

---

## 3. Combinational Logic (`comb_nodes`)

Each block names its outputs, lists inputs (all READ-phase const locals), and gives the exact gate
expression. Outputs are committed in WRITE phase. **Every state-updating register has an explicit
gate chain below** (audit requirement).

### 3.0 Per-tick level aggregation (feeds everything below)

Computes the current level's accumulated ask/bid/total volume from the table, folding in the new
DOM quantities. `cur_idx` = `PRICE_IDX` of the level the active quote touched.

```
LEVEL_ASK_ACCUM:
  inputs:  FP_ASK_VOL[cur_idx], DOM_ASK_QTY[cur_idx], lvl_valid (parity, §6)
  logic:   held_ask  = cell_gate(FP_ASK_VOL[cur_idx] & PARITY_DATA_MASK, lvl_valid)
           new_ask   = cell_addsub(held_ask, DOM_ASK_QTY[cur_idx], 0)        # add
  output:  new_ask         # ungated parity re-applied in WRITE (§6)

LEVEL_BID_ACCUM:
  inputs:  FP_BID_VOL[cur_idx], DOM_BID_QTY[cur_idx], lvl_valid
  logic:   held_bid  = cell_gate(FP_BID_VOL[cur_idx] & PARITY_DATA_MASK, lvl_valid)
           new_bid   = cell_addsub(held_bid, DOM_BID_QTY[cur_idx], 0)        # add
  output:  new_bid

LEVEL_TOTAL:
  inputs:  new_ask, new_bid
  logic:   level_vol = cell_addsub(new_ask, new_bid, 0)                      # ask+bid
  output:  level_vol   # also written to FP_PROFILE[cur_idx]

LEVEL_DELTA:
  inputs:  new_ask, new_bid
  logic:   level_delta = cell_addsub(new_ask, new_bid, 1)                    # ask-bid (sub=1)
  output:  level_delta
```

`PARITY_DATA_MASK = ~(1ULL << 63)` strips the parity tag bit before arithmetic.

### 3.1 POC_PRICE_UPDATE (running maximum volume)

```
POC_PRICE_UPDATE:
  inputs:  FP_POC_VOL, level_vol (from LEVEL_TOTAL), cur_idx, FP_POC_PRICE
  logic:   is_new_max   = cmp_lt(FP_POC_VOL, level_vol)          # 1 iff current POC < this level
           new_poc_price = cell_mux(FP_POC_PRICE, cur_idx, is_new_max)   # hold | take cur_idx
           new_poc_vol   = cell_mux(FP_POC_VOL,  level_vol, is_new_max)
  outputs: new_poc_price → FP_POC_PRICE
           new_poc_vol   → FP_POC_VOL

POC_SIDE_VOL_UPDATE:
  inputs:  is_new_max, FP_POC_ASK_VOL, FP_POC_BID_VOL, new_ask, new_bid
  logic:   new_poc_ask = cell_mux(FP_POC_ASK_VOL, new_ask, is_new_max)
           new_poc_bid = cell_mux(FP_POC_BID_VOL, new_bid, is_new_max)
  outputs: new_poc_ask → FP_POC_ASK_VOL
           new_poc_bid → FP_POC_BID_VOL
```

`is_new_max` is the single selector shared by POC price, volume, side-volumes, and delta — they all
move together (atomic POC update). Tie (`level_vol == FP_POC_VOL`) holds the existing POC because
`cmp_lt` is strict — first-seen-wins, standard footprint POC convention.

### 3.2 POC_DELTA (delta at the POC level)

```
POC_DELTA:
  inputs:  is_new_max (from POC_PRICE_UPDATE), level_delta (from LEVEL_DELTA), FP_DELTA
  logic:   new_delta = cell_mux(FP_DELTA, level_delta, is_new_max)
  output:  new_delta → FP_DELTA
```

`level_delta = cell_addsub(new_ask, new_bid, 1)` (ask − bid). The mux latches the level delta only
when this level becomes the new POC; otherwise the prior POC delta holds.

### 3.3 VAH_PRICE / VAL_PRICE (diagonal imbalance extremes)

Per level, classify the imbalance, then extend the value-area extremes.

```
IMBALANCE_CLASSIFY:
  inputs:  new_ask, new_bid
  logic:   ask_dom = cmp_lt(new_bid, new_ask)     # 1 iff ask > bid  (ask-imbalanced)
           bid_dom = cmp_lt(new_ask, new_bid)     # 1 iff bid > ask  (bid-imbalanced)
  outputs: ask_dom, bid_dom

VAH_PRICE_UPDATE:                                 # highest price where ask > bid
  inputs:  ask_dom, cur_idx, FP_VAH_PRICE
  logic:   higher    = cmp_lt(FP_VAH_PRICE, cur_idx)        # 1 iff cur_idx > current VAH
           take_vah  = cell_and(ask_dom, higher)            # ask-dominant AND higher
           new_vah   = cell_mux(FP_VAH_PRICE, cur_idx, take_vah)
  output:  new_vah → FP_VAH_PRICE

VAL_PRICE_UPDATE:                                 # lowest price where bid > ask
  inputs:  bid_dom, cur_idx, FP_VAL_PRICE
  logic:   lower     = cmp_lt(cur_idx, FP_VAL_PRICE)        # 1 iff cur_idx < current VAL
           take_val  = cell_and(bid_dom, lower)             # bid-dominant AND lower
           new_val   = cell_mux(FP_VAL_PRICE, cur_idx, take_val)
  output:  new_val → FP_VAL_PRICE
```

### 3.4 ASK_IMB_PRICE (HVN) / BID_IMB_PRICE (LVN)

Track the price of the **strongest** imbalanced level (largest magnitude), not merely the extreme
price. `level_delta` (ask − bid) is positive for ask-dominant, negative (high bit set) for
bid-dominant. Magnitude comparison uses the two one-sided gated values.

```
ASK_IMB_PRICE_UPDATE:                             # HVN — strongest ask-over-bid node
  inputs:  ask_dom, level_delta, FP_ASK_IMB_MAG (internal mag tracker), FP_ASK_IMB_PRICE, cur_idx
  logic:   ask_mag       = cell_gate(level_delta, ask_dom)             # delta if ask-dom else 0
           is_stronger   = cmp_lt(FP_ASK_IMB_MAG, ask_mag)
           take_hvn      = cell_and(ask_dom, is_stronger)
           new_ask_price = cell_mux(FP_ASK_IMB_PRICE, cur_idx,  take_hvn)
           new_ask_mag   = cell_mux(FP_ASK_IMB_MAG,   ask_mag,  take_hvn)
  outputs: new_ask_price → FP_ASK_IMB_PRICE ; new_ask_mag → FP_ASK_IMB_MAG

BID_IMB_PRICE_UPDATE:                             # LVN — strongest bid-over-ask node
  inputs:  bid_dom, new_bid, new_ask, FP_BID_IMB_MAG, FP_BID_IMB_PRICE, cur_idx
  logic:   bid_excess    = cell_gate(cell_addsub(new_bid, new_ask, 1), bid_dom)  # (bid-ask) if bid-dom else 0
           is_stronger   = cmp_lt(FP_BID_IMB_MAG, bid_excess)
           take_lvn      = cell_and(bid_dom, is_stronger)
           new_bid_price = cell_mux(FP_BID_IMB_PRICE, cur_idx,    take_lvn)
           new_bid_mag   = cell_mux(FP_BID_IMB_MAG,   bid_excess, take_lvn)
  outputs: new_bid_price → FP_BID_IMB_PRICE ; new_bid_mag → FP_BID_IMB_MAG
```

`FP_ASK_IMB_MAG` / `FP_BID_IMB_MAG` are two internal DFF magnitude trackers to add to `dff_nodes`
(they hold the running-strongest magnitude so HVN/LVN is **flip-flop level, computed inline** — not
a post-process scan). Both reset to 0 on bar close (§6). Using `bid_excess = bid − ask` keeps the
bid magnitude positive so a single `cmp_lt` magnitude compare works on both sides.

### 3.5 BAR_CUM_DELTA (CVD — continuous accumulation)

```
BAR_CUM_DELTA:
  inputs:  DOM_ASK_QTY[cur_idx], DOM_BID_QTY[cur_idx], FP_BAR_CUM_DELTA
  logic:   quote_delta = cell_addsub(DOM_ASK_QTY[cur_idx], DOM_BID_QTY[cur_idx], 1)  # ask-bid
           new_cvd     = cell_addsub(FP_BAR_CUM_DELTA, quote_delta, 0)               # accumulate
  output:  new_cvd → FP_BAR_CUM_DELTA
```

CVD is a **continuous `cell_addsub` accumulation** — every quote delta folds into the running sum
the same tick it arrives (audit requirement: *CVD accumulation is continuous `cell_addsub`, not
aggregation*). No bar-end summation pass exists.

### 3.6 BAR_TOTAL_VOL (running total)

```
BAR_TOTAL_VOL:
  inputs:  DOM_ASK_QTY[cur_idx], DOM_BID_QTY[cur_idx], FP_BAR_TOTAL_VOL
  logic:   quote_vol = cell_addsub(DOM_ASK_QTY[cur_idx], DOM_BID_QTY[cur_idx], 0)   # ask+bid
           new_total = cell_addsub(FP_BAR_TOTAL_VOL, quote_vol, 0)
  output:  new_total → FP_BAR_TOTAL_VOL
```

### 3.7 MIN_PRICE / MAX_PRICE (bar price range)

```
MIN_PRICE_UPDATE:
  inputs:  cur_idx, FP_MIN_PRICE
  logic:   is_lower = cmp_lt(cur_idx, FP_MIN_PRICE)
           new_min  = cell_mux(FP_MIN_PRICE, cur_idx, is_lower)
  output:  new_min → FP_MIN_PRICE

MAX_PRICE_UPDATE:
  inputs:  cur_idx, FP_MAX_PRICE
  logic:   is_higher = cmp_lt(FP_MAX_PRICE, cur_idx)
           new_max   = cell_mux(FP_MAX_PRICE, cur_idx, is_higher)
  output:  new_max → FP_MAX_PRICE
```

### 3.8 STACKED_IMBALANCE (consecutive imbalanced counters)

A buy stack increments when the level is ask-imbalanced **and** above POC; a sell stack increments
when bid-imbalanced **and** below POC. A non-qualifying level resets that side's counter to 0
(consecutive semantics). All branchless via `cell_gate` + `cell_addsub`.

```
STACKED_IMB_BUY:
  inputs:  ask_dom (§3.3), cur_idx, FP_POC_PRICE, FP_STACKED_IMB_BUY
  logic:   above_poc  = cmp_lt(FP_POC_PRICE, cur_idx)        # cur_idx > POC
           qualifies  = cell_and(ask_dom, above_poc)
           incremented = cell_addsub(FP_STACKED_IMB_BUY, 1, 0)         # +1
           # qualifies ? incremented : 0   →  reset-on-miss
           new_buy    = cell_gate(incremented, qualifies)
  output:  new_buy → FP_STACKED_IMB_BUY

STACKED_IMB_SELL:
  inputs:  bid_dom (§3.3), cur_idx, FP_POC_PRICE, FP_STACKED_IMB_SELL
  logic:   below_poc  = cmp_lt(cur_idx, FP_POC_PRICE)        # cur_idx < POC
           qualifies  = cell_and(bid_dom, below_poc)
           incremented = cell_addsub(FP_STACKED_IMB_SELL, 1, 0)        # +1
           new_sell   = cell_gate(incremented, qualifies)
  output:  new_sell → FP_STACKED_IMB_SELL
```

`cell_gate(incremented, qualifies)` is the branchless `qualifies ? count+1 : 0` — the gate masks the
incremented value to zero on a non-qualifying level, which is exactly the consecutive-run reset.

### 3.9 Table writes (parity-tagged)

```
FP_ASK_VOL[cur_idx]  ← (new_ask  & PARITY_DATA_MASK) | (FP_BAR_PARITY << 63)
FP_BID_VOL[cur_idx]  ← (new_bid  & PARITY_DATA_MASK) | (FP_BAR_PARITY << 63)
FP_PROFILE[cur_idx]  ← (level_vol & PARITY_DATA_MASK) | (FP_BAR_PARITY << 63)
```

Re-tagging with the current `FP_BAR_PARITY` on every write is what makes the next bar's first read
of a stale level (with last bar's parity) resolve to "invalid → treat as 0" (§6) — no clear needed.

### 3.10 Bar-boundary pulse

```
BAR_BOUNDARY_DETECTED:
  inputs:  FP_LAST_TF_SEQ, TF_BAR_SEQ_REG
  logic:   same        = cell_eqmask(FP_LAST_TF_SEQ, TF_BAR_SEQ_REG)
           bar_pulse   = cell_not(same) & 1ULL          # 1 iff seq changed
  output:  bar_pulse   (drives §6 snapshot + parity toggle)
```

---

## 4. Wiring (Signal Flow)

```
READ PHASE (pre-read const locals, no compute on registers mid-write):
  DOM_ASK_QTY[cur_idx], DOM_BID_QTY[cur_idx], DOM_COUNT[cur_idx], DOM_TIME[cur_idx]
  FP_ASK_VOL[cur_idx], FP_BID_VOL[cur_idx], FP_PROFILE[cur_idx]
  FP_POC_PRICE, FP_POC_VOL, FP_POC_ASK_VOL, FP_POC_BID_VOL, FP_DELTA
  FP_VAH_PRICE, FP_VAL_PRICE, FP_ASK_IMB_PRICE, FP_ASK_IMB_MAG,
  FP_BID_IMB_PRICE, FP_BID_IMB_MAG
  FP_BAR_CUM_DELTA, FP_BAR_TOTAL_VOL, FP_MIN_PRICE, FP_MAX_PRICE
  FP_STACKED_IMB_BUY, FP_STACKED_IMB_SELL
  FP_BAR_PARITY, FP_LAST_TF_SEQ, FP_BAR_SEQ, TF_BAR_SEQ_REG

COMPUTE PHASE (combinational only — uses the pre-read locals):
  LEVEL_ASK_ACCUM ┐
  LEVEL_BID_ACCUM ┘→ new_ask, new_bid
                     ├→ LEVEL_TOTAL  → level_vol ──┐
                     ├→ LEVEL_DELTA  → level_delta │
                     └→ IMBALANCE_CLASSIFY → ask_dom, bid_dom
                                                   │
  level_vol ─→ POC_PRICE_UPDATE → is_new_max ──────┼─→ POC_SIDE_VOL_UPDATE
                                                   ├─→ POC_DELTA (uses level_delta)
  ask_dom ──→ VAH_PRICE_UPDATE ; ASK_IMB_PRICE_UPDATE ; STACKED_IMB_BUY
  bid_dom ──→ VAL_PRICE_UPDATE ; BID_IMB_PRICE_UPDATE ; STACKED_IMB_SELL
  DOM qtys ─→ BAR_CUM_DELTA (CVD) ; BAR_TOTAL_VOL
  cur_idx ──→ MIN_PRICE_UPDATE ; MAX_PRICE_UPDATE ; VAH/VAL ; STACKED (vs FP_POC_PRICE)
  TF seq ───→ BAR_BOUNDARY_DETECTED → bar_pulse

  Bar-boundary fan-out (bar_pulse selects live vs reset for each register — §6):
    bar_pulse → snapshot mux on every FP_* live register
    bar_pulse → FP_BAR_PARITY toggle
    bar_pulse → FP_BAR_SEQ increment, FP_LAST_TF_SEQ ← TF_BAR_SEQ_REG

WRITE PHASE (write-only, no REG_R):
  FP_ASK_VOL[cur_idx], FP_BID_VOL[cur_idx], FP_PROFILE[cur_idx]   (parity-tagged, §3.9)
  All scalar FP_* DFFs ← their §6 bar-boundary mux outputs
  FP_HIST_* ring slot ← snapshot (on bar_pulse)
  Seam outputs (§5)
```

**Selector reuse (single-writer discipline):** each register has exactly one writer and one
combinational driver. `is_new_max` drives POC price/vol/side/delta atomically; `ask_dom`/`bid_dom`
are shared read-only selectors. No register is written by two blocks.

---

## 5. Output Interface (Seam Nodes)

Published relay lanes; downstream (strategy, risk, custom indicators) sample these — never footprint
internals.

| Seam | Source register | Consumer use |
|---|---|---|
| `FP_POC_OUT` | `FP_POC_PRICE` | POC price for mean-reversion / value reference. |
| `FP_POC_VOL_OUT` | `FP_POC_VOL` | POC volume (conviction weight). |
| `FP_VAH_OUT` | `FP_VAH_PRICE` | Value-area high boundary. |
| `FP_VAL_OUT` | `FP_VAL_PRICE` | Value-area low boundary. |
| `FP_DELTA_OUT` | `FP_BAR_CUM_DELTA` | CVD — order-flow imbalance signal. |

**Recommended additions** (so downstream can act on imbalance without re-deriving): `FP_ASK_IMB_OUT`
← `FP_ASK_IMB_PRICE` (HVN), `FP_BID_IMB_OUT` ← `FP_BID_IMB_PRICE` (LVN), `FP_STK_BUY_OUT` ←
`FP_STACKED_IMB_BUY`, `FP_STK_SELL_OUT` ← `FP_STACKED_IMB_SELL`. Each is a passthrough relay (source
register → lane), no compute in the seam.

All seam writes are passive lane deposits: `FP_*_OUT ← FP_*` source, updated whenever the source DFF
updates. No logic in the relay — `seam_nodes` are pure `from:` references.

---

## 6. Bar Boundary Behavior

Two mechanisms: **snapshot** (carry the bar's result forward) and **virtual reset** (clear live
accumulators without memset or loop).

### Snapshot to COMP_*/HIST on bar close

On `bar_pulse = 1` (`BAR_BOUNDARY_DETECTED`, §3.10):

```
SNAPSHOT (one history ring slot, indexed by FP_BAR_SEQ & 0xFF):
  FP_HIST_POC_PRICE     ← FP_POC_PRICE
  FP_HIST_VAH_PRICE     ← FP_VAH_PRICE
  FP_HIST_VAL_PRICE     ← FP_VAL_PRICE
  FP_HIST_NET_DELTA     ← FP_BAR_CUM_DELTA
  FP_HIST_TOTAL_VOL     ← FP_BAR_TOTAL_VOL
  FP_HIST_BAR_SEQ       ← FP_BAR_SEQ
  FP_HIST_ASK_IMB_PRICE ← FP_ASK_IMB_PRICE
  FP_HIST_BID_IMB_PRICE ← FP_BID_IMB_PRICE
  FP_HIST_POC_DELTA     ← FP_DELTA
  FP_HIST_STK_BUY       ← FP_STACKED_IMB_BUY
  FP_HIST_STK_SELL      ← FP_STACKED_IMB_SELL
  FP_HIST_MIN_PRICE     ← FP_MIN_PRICE
  FP_HIST_MAX_PRICE     ← FP_MAX_PRICE
  FP_HIST_BAR_TAI       ← DOM_TIME[cur_idx]   (bar-close TAI)
```

Each `FP_HIST_*` write is gated by `bar_pulse` (`cell_gate` / mux against the prior slot value), so
the ring only advances on a true boundary.

### Live-register update vs reset (branchless mux on bar_pulse)

Each live register's WRITE-phase value is a mux between *its computed-this-tick value* and *its
bar-open reset value*, selected by `bar_pulse`:

```
FP_POC_VOL          ← cell_mux(new_poc_vol,        0,      bar_pulse)   # reset max tracker
FP_POC_PRICE        ← cell_mux(new_poc_price,       0,      bar_pulse)
FP_POC_ASK_VOL      ← cell_mux(new_poc_ask,         0,      bar_pulse)
FP_POC_BID_VOL      ← cell_mux(new_poc_bid,         0,      bar_pulse)
FP_DELTA            ← cell_mux(new_delta,           0,      bar_pulse)
FP_BAR_CUM_DELTA    ← cell_mux(new_cvd,             0,      bar_pulse)   # CVD resets per bar
FP_BAR_TOTAL_VOL    ← cell_mux(new_total,           0,      bar_pulse)
FP_VAH_PRICE        ← cell_mux(new_vah,             0,      bar_pulse)
FP_VAL_PRICE        ← cell_mux(new_val,  PRICE_IDX_MAX,     bar_pulse)   # min seeds at max
FP_ASK_IMB_PRICE    ← cell_mux(new_ask_price,       0,      bar_pulse)
FP_ASK_IMB_MAG      ← cell_mux(new_ask_mag,         0,      bar_pulse)
FP_BID_IMB_PRICE    ← cell_mux(new_bid_price,       0,      bar_pulse)
FP_BID_IMB_MAG      ← cell_mux(new_bid_mag,         0,      bar_pulse)
FP_MIN_PRICE        ← cell_mux(new_min,  PRICE_IDX_MAX,     bar_pulse)   # min seeds at max
FP_MAX_PRICE        ← cell_mux(new_max,             0,      bar_pulse)   # max seeds at 0
FP_STACKED_IMB_BUY  ← cell_mux(new_buy,             0,      bar_pulse)
FP_STACKED_IMB_SELL ← cell_mux(new_sell,            0,      bar_pulse)
FP_BAR_SEQ          ← cell_mux(FP_BAR_SEQ, cell_addsub(FP_BAR_SEQ,1,0), bar_pulse)  # +1 on close
FP_LAST_TF_SEQ      ← cell_mux(FP_LAST_TF_SEQ, TF_BAR_SEQ_REG, bar_pulse)
```

`PRICE_IDX_MAX = 16383` (named constant) seeds running-minimum registers so the first real level
always wins the `cmp_lt`. Running-maximum registers seed at 0.

### Parity-tag virtual reset for the 16384-entry tables (no memset, no loop)

The three price-indexed tables are **never cleared**. Each entry carries the writing bar's parity in
bit 63. `FP_BAR_PARITY` toggles on bar close:

```
FP_BAR_PARITY ← cell_mux(FP_BAR_PARITY, cell_not(FP_BAR_PARITY) & 1ULL, bar_pulse)
```

On read, a level is *valid* only if its stored parity matches the current bar parity; otherwise its
data is treated as 0 (stale = belongs to a previous bar):

```
PARITY_VALIDATE (per level, READ phase):
  raw       = REG_R(FP_ASK_VOL[cur_idx])             # or BID / PROFILE
  stored_par = raw >> 63
  lvl_valid  = cell_eqmask(stored_par, FP_BAR_PARITY)        # 1 iff parities match
  data       = cell_gate(raw & PARITY_DATA_MASK, lvl_valid)  # valid ? data : 0
```

`lvl_valid` is exactly the gate fed into `LEVEL_ASK_ACCUM` / `LEVEL_BID_ACCUM` (§3.0). The first
touch of a level in a new bar sees a parity mismatch → starts from 0 → no per-bar table clear is
ever executed. This satisfies the *no-memset / no-loop reset* law for the full 16384-entry ladder.

---

## Audit Cross-Check

| Requirement | Where satisfied |
|---|---|
| Every register update has explicit gate-level logic | §3.1–3.9 (live) + §6 (bar-boundary mux for every `FP_*`). |
| Imbalance (HVN/LVN) is flip-flop level, not post-process | §3.4 — `FP_ASK_IMB_MAG`/`FP_BID_IMB_MAG` DFF trackers updated inline each tick via `cmp_lt`+`cell_mux`. |
| CVD accumulation is continuous `cell_addsub`, not aggregation | §3.5 — `new_cvd = cell_addsub(FP_BAR_CUM_DELTA, quote_delta, 0)` each tick. |
| Reset via parity tag, no memset / no loop | §6 — parity toggle + per-level `cell_eqmask` validate; tables never cleared. |
| Only gate primitives; no native `+ - * == != ?: if` / loops | §3–6 — all logic in `cell_addsub`/`cell_mux`/`cell_eqmask`/`cell_gate`/`cmp_lt`/`cell_and`/`cell_not`. |
| Implicit price-level iteration via table indexing, not C loops | §1 "Implicit iteration model" + §3.0 per-`cur_idx` aggregation. |

## New registers to add to `footprint.yaml` `dff_nodes`

`FP_ASK_IMB_MAG`, `FP_BID_IMB_MAG` (HVN/LVN magnitude trackers, §3.4). Named constants:
`PARITY_DATA_MASK = ~(1ULL<<63)`, `PRICE_IDX_MAX = 16383`.
