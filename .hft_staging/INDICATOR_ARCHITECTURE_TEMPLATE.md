# Indicator Architecture Template — How to Specify Flip-Flop Logic

**Purpose:** Template for documenting indicator architectures at flip-flop level before code generation.

**Applies to:** candle, footprint, TPO, fractal, CBR

**Status:** Do not proceed with emitter-first build until architecture is documented per this template.

---

## ⚠️ MANDATORY: The Index Doctrine (CLAUDE.md Law #10, FOUNDER_VISION.md §8a)

Every indicator is a **price-indexed activity counter on a per-frame pip-canvas** —
NOT a store-and-allocate table. Before specifying any indicator, internalize:

- **Time-framed on the one tick axis.** The frame is a bounded count of internal
  clock ticks (`BAR_SEQ` from `timeframe`). The indicator accumulates within the
  frame and snapshots to history addressed by `BAR_SEQ` at the boundary, then resets.
- **Price is a pip-index *within* the frame, not an absolute coordinate.** Compute
  `offset = price − bar_open` (one `cell_addsub`) in pip units (`pip_resolver` gives
  the pip size); the offset *is* the address. The canvas spans only the bar's pip-range.
- **NO allocation, NO free-slot search, NO stored price keys, NO anchor/window
  stamping.** The index is the match; the position is the price. (The old FP_LVL +
  FP_ALLOC_CUR allocation pattern is RETIRED — do not reproduce it.)
- **Store price as a VALUE only when it is the measured quantity** (OHLC, published
  POC = `bar_open + offset`); never store it as the axis.
- Sizing knob: the **max pip-span a bar may occupy** (the canvas height), per symbol.

So: candle = bar pip-extremes; footprint = volume per price; tpo = time-touches per
price. See `memory/index_doctrine_price_time_as_index.md`.

**DOM is the source payload; the indicator does its OWN counting — never lift DOM's
aggregates.** The DOM snapshot is the enriched per-internal-tick, all-price payload.
The indicator keeps its **own** counters and **counts from** that payload into its own
registers, bounded by its timeframe, computing its **own** outputs (footprint
POC/VAH/VAL/HVN/LVN from its own bid/ask counts; candle total volume from its own
counter; tpo touches from its own tally). **DOM's POC ≠ footprint's POC** (different
time scope) — reading a DOM derived-aggregate as your output is a bug. The shared
internal clock guarantees the indicator's counter advances in lockstep with DOM's
payload, so no tick is lost. "footprint is DOM bounded by a timeframe" = the same kind
of counting, sourced from DOM's payload, on the indicator's own state over its own bar.

---

## Overview

Each indicator must specify:
1. **Input interface** — what comes from other modules (cross_module_inputs)
2. **Register state** — what state the indicator maintains (dff_nodes, tables, history_ring)
3. **Combinational logic** — how state transforms tick-by-tick (comb_nodes with gate primitives)
4. **Wiring** — how signals flow between logic blocks
5. **Output interface** — what the indicator publishes downstream (seam_nodes)

---

## Template: Candle Indicator

**Use this as reference for the other four indicators.**

### 1. Input Interface

```
From DOM:
  — DOM_BID_PRICE: best bid price (updated when bid changes)
  — DOM_ASK_PRICE: best ask price (updated when ask changes)
  — DOM_BID_QTY: bid quantity at indexed price level
  — DOM_ASK_QTY: ask quantity at indexed price level

From Timeframe:
  — TF_BAR_SEQ: bar boundary detection (increments on bar close)

From FIFO_RX (or ingress):
  — Quote stream: bid/ask ticks (implicitly: when DOM updates)
```

### 2. Register State

**Live (updated every tick during bar):**
```
CANDLE_BID_OPEN    — first bid price of bar
CANDLE_BID_HIGH    — running maximum bid price
CANDLE_BID_LOW     — running minimum bid price
CANDLE_BID_CLOSE   — most recent bid price

CANDLE_ASK_OPEN    — first ask price of bar
CANDLE_ASK_HIGH    — running maximum ask price
CANDLE_ASK_LOW     — running minimum ask price
CANDLE_ASK_CLOSE   — most recent ask price

CANDLE_VOLUME_BID  — cumulative bid ticks
CANDLE_VOLUME_ASK  — cumulative ask ticks

CANDLE_TRUE_RANGE_BID  — bid_high - bid_low
CANDLE_TRUE_RANGE_ASK  — ask_high - ask_low

CANDLE_INTRABAR_QTY_DELTA  — sum(ask_qty) - sum(bid_qty)

CANDLE_OPEN_SET    — flag: first tick processed (1) or not (0)
CANDLE_LAST_TF_SEQ — last timeframe sequence seen (for edge detection)
CANDLE_BAR_SEQ     — bar sequence counter
CANDLE_BAR_PARITY  — virtual-reset parity tag (bit 63)

CANDLE_MID         — convenience: (bid_high + ask_low) / 2
```

**Completed (written on bar boundary, carried to next bar):**
```
CANDLE_COMP_BID_OPEN
CANDLE_COMP_BID_HIGH
CANDLE_COMP_BID_LOW
CANDLE_COMP_BID_CLOSE

CANDLE_COMP_ASK_OPEN
CANDLE_COMP_ASK_HIGH
CANDLE_COMP_ASK_LOW
CANDLE_COMP_ASK_CLOSE

CANDLE_COMP_VOLUME_BID
CANDLE_COMP_VOLUME_ASK

CANDLE_COMP_TRUE_RANGE_BID
CANDLE_COMP_TRUE_RANGE_ASK

CANDLE_COMP_INTRABAR_QTY_DELTA

CANDLE_COMP_TAI         — bar open timestamp
CANDLE_COMP_BAR_SEQ     — bar sequence
```

**History Ring (16 fields per bar, 256 slots):**
```
CANDLE_HIST_BID_OPEN
CANDLE_HIST_BID_HIGH
CANDLE_HIST_BID_LOW
CANDLE_HIST_BID_CLOSE
CANDLE_HIST_ASK_OPEN
CANDLE_HIST_ASK_HIGH
CANDLE_HIST_ASK_LOW
CANDLE_HIST_ASK_CLOSE
CANDLE_HIST_VOLUME_BID
CANDLE_HIST_VOLUME_ASK
CANDLE_HIST_TRUE_RANGE_BID
CANDLE_HIST_TRUE_RANGE_ASK
CANDLE_HIST_INTRABAR_QTY_DELTA
CANDLE_HIST_TAI
CANDLE_HIST_BAR_SEQ
CANDLE_HIST_PARITY
```

### 3. Combinational Logic (The Actual RTL Primitives)

**Bid-side OHLC updates:**

```
CANDLE_BID_OPEN_UPDATE:
  Input:  CANDLE_BID_OPEN, DOM_BID_PRICE, CANDLE_OPEN_SET
  Logic:  cell_mux(CANDLE_OPEN_SET, DOM_BID_PRICE, CANDLE_BID_OPEN)
  Output: new_bid_open
  Comment: First bid of bar (latch when open_set=1, hold otherwise)

CANDLE_BID_HIGH_UPDATE:
  Input:  CANDLE_BID_HIGH, DOM_BID_PRICE
  Logic:  is_new_high = cell_cmp_lt(CANDLE_BID_HIGH, DOM_BID_PRICE)
          cell_mux(is_new_high, DOM_BID_PRICE, CANDLE_BID_HIGH)
  Output: new_bid_high
  Comment: Running maximum (update if DOM_BID_PRICE > current high)

CANDLE_BID_LOW_UPDATE:
  Input:  CANDLE_BID_LOW, DOM_BID_PRICE
  Logic:  is_new_low = cell_cmp_lt(DOM_BID_PRICE, CANDLE_BID_LOW)
          cell_mux(is_new_low, DOM_BID_PRICE, CANDLE_BID_LOW)
  Output: new_bid_low
  Comment: Running minimum (update if DOM_BID_PRICE < current low)

CANDLE_BID_CLOSE_UPDATE:
  Input:  DOM_BID_PRICE
  Logic:  passthrough (always latch most recent)
  Output: new_bid_close = DOM_BID_PRICE
```

**Ask-side OHLC updates (symmetric to bid):**
```
CANDLE_ASK_OPEN_UPDATE:    cell_mux(CANDLE_OPEN_SET, DOM_ASK_PRICE, CANDLE_ASK_OPEN)
CANDLE_ASK_HIGH_UPDATE:    cmp_lt + mux (max)
CANDLE_ASK_LOW_UPDATE:     cmp_lt + mux (min)
CANDLE_ASK_CLOSE_UPDATE:   passthrough
```

**Volume accumulation:**
```
CANDLE_VOLUME_BID_UPDATE:
  Input:  CANDLE_VOLUME_BID, (quote was bid?)
  Logic:  is_bid_tick = (DOM_BID_PRICE != CANDLE_PREV_BID_PRICE)
          new_vol = cell_addsub(CANDLE_VOLUME_BID, cell_gate(1, is_bid_tick), 0)
  Output: new_volume_bid

CANDLE_VOLUME_ASK_UPDATE:
  Input:  CANDLE_VOLUME_ASK, (quote was ask?)
  Logic:  is_ask_tick = (DOM_ASK_PRICE != CANDLE_PREV_ASK_PRICE)
          new_vol = cell_addsub(CANDLE_VOLUME_ASK, cell_gate(1, is_ask_tick), 0)
  Output: new_volume_ask
```

**True Range (difference between high and low):**
```
CANDLE_TRUE_RANGE_BID_UPDATE:
  Input:  CANDLE_BID_HIGH, CANDLE_BID_LOW
  Logic:  cell_addsub(CANDLE_BID_HIGH, CANDLE_BID_LOW, 1)  [subtract via 2's complement]
  Output: new_tr_bid

CANDLE_TRUE_RANGE_ASK_UPDATE:
  Input:  CANDLE_ASK_HIGH, CANDLE_ASK_LOW
  Logic:  cell_addsub(CANDLE_ASK_HIGH, CANDLE_ASK_LOW, 1)
  Output: new_tr_ask
```

**Intrabar delta (sum of ask_qty - sum of bid_qty):**
```
CANDLE_INTRABAR_QTY_DELTA_UPDATE:
  Input:  CANDLE_INTRABAR_QTY_DELTA, DOM_ASK_QTY, DOM_BID_QTY
  Logic:  quote_delta = cell_addsub(DOM_ASK_QTY, DOM_BID_QTY, 1)  [ask - bid]
          new_delta = cell_addsub(CANDLE_INTRABAR_QTY_DELTA, quote_delta, 0)
  Output: new_intrabar_delta
```

**Bar boundary detection:**
```
BAR_BOUNDARY_DETECTED:
  Input:  CANDLE_LAST_TF_SEQ, TF_BAR_SEQ
  Logic:  bar_closed = cell_eqmask(CANDLE_LAST_TF_SEQ, TF_BAR_SEQ) ? 0 : 1
          [if seq changed, bar boundary; otherwise no change]
  Output: bar_boundary_pulse (1 if bar closed, 0 otherwise)
```

**Mid price (optional, convenience):**
```
CANDLE_MID_UPDATE:
  Input:  CANDLE_BID_HIGH, CANDLE_ASK_LOW
  Logic:  (no division yet; use fixed-point reciprocal multiply instead)
          mid_approx = cell_addsub(CANDLE_BID_HIGH, CANDLE_ASK_LOW, 0) >> 1  [shift right = /2]
  Output: new_mid
  Note:   Full (bid_high + ask_low)/2 requires DSP division (4-stage pipeline, out of scope for core tick)
```

### 4. Wiring (Signal Flow)

```
Inputs from DOM:
  DOM_BID_PRICE       → all bid-side comparators + OPEN latch
  DOM_ASK_PRICE       → all ask-side comparators + OPEN latch
  DOM_BID_QTY         → intrabar delta accumulation
  DOM_ASK_QTY         → intrabar delta accumulation

Inputs from Timeframe:
  TF_BAR_SEQ          → bar boundary detection

Cross-module wiring:
  CANDLE_OPEN_SET (latch pulse from bar boundary)
  CANDLE_PREV_BID_PRICE (previous bid price, for tick detection)
  CANDLE_PREV_ASK_PRICE (previous ask price, for tick detection)

On bar boundary:
  All CANDLE_* live registers → copy to CANDLE_COMP_* snapshot registers
  Snapshot registers → write to history ring slot
  BAR_BOUNDARY_DETECTED → increment CANDLE_BAR_SEQ
  BAR_BOUNDARY_DETECTED → reset CANDLE_OPEN_SET, CANDLE_VOLUME_BID, CANDLE_VOLUME_ASK, CANDLE_INTRABAR_QTY_DELTA
  BAR_BOUNDARY_DETECTED → latch CANDLE_COMP_TAI = current TAI timestamp
```

### 5. Output Interface (Seam Nodes)

```
Published relay outputs (downstream modules sample these):

CANDLE_BID_OHLC_OUT
  Lanes: CANDLE_BID_OPEN, CANDLE_BID_HIGH, CANDLE_BID_LOW, CANDLE_BID_CLOSE
  Purpose: fractal, custom indicators use bid-side OHLC

CANDLE_ASK_OHLC_OUT
  Lanes: CANDLE_ASK_OPEN, CANDLE_ASK_HIGH, CANDLE_ASK_LOW, CANDLE_ASK_CLOSE
  Purpose: fractal, custom indicators use ask-side OHLC (configurable)

CANDLE_VOLUME_OUT
  Lanes: CANDLE_VOLUME_BID, CANDLE_VOLUME_ASK
  Purpose: CBR uses volume for ratio calculations

CANDLE_TRUE_RANGE_OUT
  Lanes: CANDLE_TRUE_RANGE_BID, CANDLE_TRUE_RANGE_ASK
  Purpose: ATR-like calculations

CANDLE_DELTA_OUT
  Lane: CANDLE_INTRABAR_QTY_DELTA
  Purpose: imbalance-driven trading signals
```

---

## Pattern: Footprint (POC Tracking Example)

**Simplified architecture for the POC (point of control) register:**

```
Live State:
  FP_POC_PRICE       — price level with maximum volume
  FP_POC_VOL         — volume at POC price
  FP_POC_DELTA       — delta at POC level (ask_qty - bid_qty)

Logic:
  For each price level indexed by PRICE_IDX:
    current_vol = cell_addsub(DOM_ASK_QTY[PRICE_IDX], DOM_BID_QTY[PRICE_IDX], 0)  [add]
    is_new_max = cell_cmp_lt(FP_POC_VOL, current_vol)
    new_poc_price = cell_mux(is_new_max, PRICE_IDX, FP_POC_PRICE)
    new_poc_vol = cell_mux(is_new_max, current_vol, FP_POC_VOL)
    new_poc_delta = cell_mux(is_new_max, 
                              cell_addsub(DOM_ASK_QTY[PRICE_IDX], DOM_BID_QTY[PRICE_IDX], 1),
                              FP_POC_DELTA)
```

**Key insight:** Running maximum requires:
- cell_cmp_lt (carry-chain comparator)
- cell_mux (multiplexer to select old or new value)
- Looped iteration over all price levels (via table indexing logic)

---

## Pattern: TPO (Time-per-Price Accumulation)

```
Live State (per bar):
  TPO_BAR_POC_PRICE  — price level with most time in bar
  TPO_BAR_POC_TIME   — cumulative time at POC level

Logic:
  For each price level indexed by PRICE_IDX:
    If quote arrives at this level:
      elapsed_time = current_TAI - last_TAI[PRICE_IDX]
      new_time_total = cell_addsub(TPO_TIME[PRICE_IDX], elapsed_time, 0)  [add]
      is_new_max_time = cell_cmp_lt(TPO_BAR_POC_TIME, new_time_total)
      new_poc_price = cell_mux(is_new_max_time, PRICE_IDX, TPO_BAR_POC_PRICE)
      new_poc_time = cell_mux(is_new_max_time, new_time_total, TPO_BAR_POC_TIME)
      
      TPO_TIME[PRICE_IDX] = new_time_total
      TPO_BAR_POC_PRICE = new_poc_price
      TPO_BAR_POC_TIME = new_poc_time
```

---

## Why This Matters

Once you specify the indicator at this level (registers + combinational logic with explicit cell primitives):

1. **Emitter can generate complete netlists** — Parser reads comb_nodes, emits `"fed_by": "cell_type"` in netlist
2. **gennet can generate real device C** — Translates comb_nodes to cell function calls
3. **Gate 2d validates logic content** — Checks cell_count > 0, confirms not a stub
4. **Downstream modules can be built** — Fractal + CBR read from candle seam outputs

---

## Next Steps

1. **Document candle architecture** per this template (specify all comb_nodes)
2. **Document footprint architecture** (POC tracking, imbalance detection, delta, CVD)
3. **Document TPO architecture** (time-per-price, bid/ask split)
4. **Update candle.yaml, footprint.yaml, tpo.yaml** with comb_nodes sections
5. **Regenerate emitters** (partslist-to-emitter.py with new emitter template that reads comb_nodes)
6. **Regenerate netlists** (gen_*_net.py)
7. **Regenerate device C** (gennet.py)
8. **Run gate.sh** with new 2d check — should pass with real cell calls
9. **Graduate to vault** with confirmed RTL logic

---

## Key Constraints

- **No loops in COMPUTE phase** — iteration over price levels happens implicitly via table indexing, not C loops
- **No division** — if needed, use DSP pipeline stage (4 stages, not inline)
- **No C operators (+, -, *)** — all arithmetic via cell_addsub, cell_mul
- **No `if` statements** — all branching via cell_mux (ternary)
- **No function calls** — all logic is inline gate expressions
- **No memory allocation** — all state in addressed registers (fixed size)
- **Branchless data path** — every operation is a gate chain, not conditional code

These constraints are *enforced by gate 2b* (grep for operators) and *will be validated by gate 2d* (check for actual cells).
