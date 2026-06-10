# TPO (Time Price Opportunity) — Flip-Flop-Level Architecture

**Purpose:** Gate-level architectural specification for the TPO indicator. Documents the
combinational logic (comb_nodes) that turns the register state in `tpo.yaml` into a complete,
buildable circuit. This is the load-bearing companion to `tpo.yaml` — without explicit comb_nodes
the emitter produces a register stub with no flip-flop logic (see CLAUDE.md §"Specification
Completeness Before Code Generation", gate stage 2d).

**Pipeline:** this doc → `gen_tpo_net.py` (emitter) → `tpo.net.json` (netlist) → `gennet.py` →
`tpo_gen.h` (generated device C).

**Pattern reference:** `.hft_staging/INDICATOR_ARCHITECTURE_TEMPLATE.md` §"Pattern: TPO" and
§"Template: Candle Indicator". Reference implementation for bar-boundary / snapshot / min-max
patterns: `hft_pipeline/candle/candle.c`.

**Register spec:** `tools/generators/tpo.yaml` (dff_nodes, tables, seam_nodes, cross_module_inputs).

**Date:** 2026-06-09
**Status:** Architecture complete — comb_nodes specified; ready for emitter implementation.

---

## What TPO Computes

TPO measures **how much time price spent at each level** during a bar, rather than how much volume
traded there (that is footprint's job). The level that accumulated the most time is the bar's
**Point of Control (POC)**. TPO splits accumulated time into a **bid side** and an **ask side** so
the POC carries a directional `time_delta = ask_time − bid_time`.

The core insight, and the reason the logic differs from candle/footprint:

> **Time is accumulated *continuously* — one `cell_addsub` of `elapsed` per tick into the level
> that is currently active — NOT once per quote.** Every clock edge measures the time that has
> passed since the previous edge (`current_TAI − TPO_PREV_TAI`) and adds it to the live level's
> running total. A level that stays active for many ticks accrues many small `elapsed` additions.

---

## Gate Primitives (the only allowed operations)

All logic below is expressed with structural cells from `cells.h`. No native `+ - * == != ?: if`,
no loops over data, no function calls in the tick. Exact signatures (note argument order):

| Primitive | Signature | Semantics |
|---|---|---|
| `cell_addsub` | `cell_addsub(a, b, sub)` | `sub=0 → a+b`; `sub=1 → a−b` (ripple-carry, two's complement). Returns the 64-bit sum word. |
| `cell_mux` | `cell_mux(a, b, sel)` | `sel ? b : a` — selected value is the **second** argument; mask algebra, branchless. |
| `cell_eqmask` | `cell_eqmask(a, b)` | `1` iff `a == b`, else `0`. Branchless equality. |
| `cell_gate` | `cell_gate(val, en)` | `en ? val : 0` — power-gates a multi-bit value, no branch. |
| `cmp_lt` | (generator-expanded carry chain) | `1` iff `a < b`. Built from the `cell_fa` carry-out chain; emitted by gennet, not a hand-written cell. |

> **Argument-order note:** the architecture descriptions below sometimes read `cell_mux(sel, A, B)`
> for clarity of intent ("select A when sel"). The canonical `cells.h` order is
> `cell_mux(a_when_false, b_when_true, sel)`. The emitter/gennet bind to the canonical order; the
> intent ("when the condition holds, take the new value") is what matters and is stated explicitly
> per node.

---

## 1. Input Interface

Consumed from upstream modules via published lanes only (module-barrier law — TPO never reads
another module's internal state).

```
From FIFO_RX (ingress timestamp):
  FIFO_RX_TAI        — authoritative TAI timestamp of the current ingress event.
                       This is the clock that drives time accumulation. The
                       difference between consecutive ticks' TAI values is the
                       elapsed time charged to the active price level.

From DOM (per-price-level state, indexed by PRICE_IDX):
  DOM_TIME           — latest TAI timestamp at which each price level was active.
                       Identifies WHICH level is live this tick (level whose
                       DOM_TIME advanced).
  DOM_BID_QTY        — bid quantity at the level (used to classify the active
                       quote as a bid event).
  DOM_ASK_QTY        — ask quantity at the level (used to classify the active
                       quote as an ask event).
  DOM_COUNT          — per-level event count (delta vs TPO_PREV_TRADE_CNT detects
                       a new event at the level).

From Timeframe (bar boundary authority):
  TF_BAR_SEQ_REG     — bar sequence counter. Timeframe owns the bar boundary;
                       TPO detects a boundary by comparing this against its own
                       last-seen value (same contract candle.c uses with
                       CANDLE_LAST_TF_SEQ_REG).
```

---

## 2. Register State

Mirrors `tpo.yaml`. Organized by purpose.

### Bar-level running state (live, updated every tick during the bar)

```
TPO_BAR_POC_PRICE   — price level (PRICE_IDX) with the most accumulated time so far this bar
TPO_BAR_POC_TOTAL   — total accumulated time at the running POC level  (the "POC time")
TPO_BAR_POC_BID_TIME— bid-side accumulated time at the running POC level
TPO_BAR_POC_ASK_TIME— ask-side accumulated time at the running POC level
TPO_BAR_TIME_DELTA  — ask_time − bid_time at the running POC level
TPO_BAR_MIN_PRICE   — minimum price touched this bar
TPO_BAR_MAX_PRICE   — maximum price touched this bar
TPO_BAR_START_TAI   — TAI when the bar opened
TPO_OPEN_SET        — first-level-seen flag (bar open latch; 0 until first event)
```

> The task brief names these `TPO_BAR_POC_TIME`; the committed `tpo.yaml` field is
> `TPO_BAR_POC_TOTAL` (total time at POC). They are the same quantity — this doc uses the yaml name
> as canonical and notes the alias here so the two read consistently.

### Per-level time tables (the primary accumulators, indexed by PRICE_IDX)

```
TPO_BID_TIME[16384] — cumulative bid-side time at each price level (parity-tagged, bit 63)
TPO_ASK_TIME[16384] — cumulative ask-side time at each price level (parity-tagged, bit 63)
```

### Completed bar snapshot (written on bar boundary, carried into next bar)

```
TPO_COMP_POC_PRICE     — completed-bar POC price
TPO_COMP_POC_BID_TIME  — completed-bar POC bid time
TPO_COMP_POC_ASK_TIME  — completed-bar POC ask time
TPO_COMP_TIME_DELTA    — completed-bar time delta (ask − bid at POC)
TPO_COMP_MIN_PRICE     — completed-bar minimum price
TPO_COMP_MAX_PRICE     — completed-bar maximum price
TPO_COMP_BAR_SEQ       — completed-bar sequence number
TPO_COMP_BAR_TAI       — completed-bar close TAI timestamp
```

### Control

```
TPO_BAR_SEQ            — bar sequence counter (increments on boundary)
TPO_BAR_PARITY         — virtual-reset parity tag (bit 63 of per-level table entries);
                         flips on every bar close so a level read in the new bar whose
                         parity does not match is treated as 0 without a memset/loop
TPO_PREV_TAI           — last TAI processed (the subtrahend for elapsed-time)
TPO_PREV_TRADE_CNT     — last DOM_COUNT seen (new-event detection)
TPO_BAR_CLOSED         — bar-close pulse latch (1 the tick a boundary is crossed)
```

### History ring (256 slots, 8 fields)

```
TPO_HIST_POC_PRICE, TPO_HIST_POC_BID_TIME, TPO_HIST_POC_ASK_TIME, TPO_HIST_TIME_DELTA,
TPO_HIST_BAR_SEQ, TPO_HIST_MIN_PRICE, TPO_HIST_MAX_PRICE, TPO_HIST_BAR_TAI
```

---

## 3. Combinational Logic (comb_nodes)

Every node below is explicit gate-level. READ phase pre-reads all inputs/state; COMPUTE phase is
pure cell algebra over those locals; WRITE phase latches results (no `REG_R` after WRITE).

### 3.1 — `TPO_TIME_DELTA` (elapsed time this tick)

The continuous, per-tick time measurement. This is the heart of TPO.

```
Inputs:  FIFO_RX_TAI (current_TAI), TPO_PREV_TAI
Logic:   elapsed = cell_addsub(current_TAI, TPO_PREV_TAI, 1)      [sub=1 → subtract]
Output:  elapsed   (nanoseconds since previous clock edge)
Note:    computed EVERY tick, independent of whether a new quote arrived. elapsed
         is the amount of time charged to whatever level is currently active.
```

### 3.2 — `TPO_TIME_ACCUMULATE` (charge elapsed to the active level, track POC)

For the price level indexed by `PRICE_IDX` that is active this tick, add `elapsed` to its running
total and re-evaluate whether it has become the POC. Iteration over levels is **structural** (table
indexing in the netlist), never a C loop over data.

```
Per active level (PRICE_IDX):

  active        = cell_eqmask(DOM_TIME[PRICE_IDX], current_TAI)   [1 if level is live this tick]
  charge        = cell_gate(elapsed, active)                       [elapsed if active, else 0]

  new_time_total= cell_addsub(TPO_TIME[PRICE_IDX], charge, 0)      [sub=0 → add; per-level total]

  is_new_max_time = cmp_lt(TPO_BAR_POC_TOTAL, new_time_total)      [1 if this level now leads]

  new_poc_price = cell_mux(TPO_BAR_POC_PRICE, PRICE_IDX,       is_new_max_time)
  new_poc_total = cell_mux(TPO_BAR_POC_TOTAL, new_time_total,  is_new_max_time)
```

Where `TPO_TIME[PRICE_IDX]` is the level's combined running time — realized as the
`TPO_BID_TIME` / `TPO_ASK_TIME` tables (see §3.5). The `charge` gate is what makes accumulation
continuous-but-targeted: only the active level receives `elapsed`; all others gate to 0 and hold.

> Running-max-time is the time analogue of candle's running-high (`cmp_lt + cell_mux`) and
> footprint's POC-by-volume — identical structure, different accumuland.

### 3.3 — `TPO_MIN_MAX_TRACKING` (price range, symmetric to candle)

```
Inputs:  TPO_BAR_MIN_PRICE, TPO_BAR_MAX_PRICE, active_price (PRICE_IDX of live level)

  is_new_min = cmp_lt(active_price, TPO_BAR_MIN_PRICE)
  new_min    = cell_mux(TPO_BAR_MIN_PRICE, active_price, is_new_min)

  is_new_max = cmp_lt(TPO_BAR_MAX_PRICE, active_price)
  new_max    = cell_mux(TPO_BAR_MAX_PRICE, active_price, is_new_max)
```

Identical to candle's `BID_LOW`/`BID_HIGH` running min/max (`cmp_lt` + `cell_mux`).

### 3.4 — `TPO_BAR_CLOSED` (boundary detection + snapshot trigger)

```
Inputs:  TF_BAR_SEQ_REG (tf_seq), TPO_LAST_TF_SEQ (last_tf_seq)

  bar_same   = cell_eqmask(tf_seq, last_tf_seq)          [1 if sequence unchanged]
  bar_close  = cell_addsub(1, bar_same, 1)               [1 − bar_same → 1 iff boundary crossed]
```

`bar_close` is a one-tick pulse. It gates every BAR → COMP snapshot write (§4) and the parity flip.
Same authority contract as `candle.c` (`tf_seq != last_tf_seq`), expressed branchlessly via
`cell_eqmask` per the task's validation requirement.

On `bar_close == 1`:
- snapshot: `TPO_COMP_* ← TPO_BAR_*` (POC price/bid/ask time, delta, min, max, seq, TAI)
- write history ring slot `TPO_BAR_SEQ & TPO_HIST_MASK`
- `TPO_BAR_SEQ ← cell_addsub(TPO_BAR_SEQ, 1, 0)`
- `TPO_BAR_PARITY ← cell_xor(TPO_BAR_PARITY, bar_close)`  (virtual reset of per-level tables)
- reset running state: POC totals, min/max, `TPO_OPEN_SET` gated back to 0

Each COMP write is `cell_mux(comp_old, bar_value, bar_close)` — hold previous snapshot on
non-close ticks, latch new on close (the candle.c `bar_close ? new : comp` pattern, branchless).

---

## 3.5 — Bid/Ask Split (branchless side classification)

`TPO_BID_TIME` and `TPO_ASK_TIME` are separate per-level tables. The same `elapsed` is charged to
the active level, but routed to the bid table or the ask table depending on which side the active
event was. Classification is **branchless** — `cell_gate`, never `if/else`.

```
Classify the active event's side (per active level):

  is_bid = cell_eqmask( ... bid-event condition ... )    [1 if the active quote was a bid]
  is_ask = cell_addsub(1, is_bid, 1)                      [1 − is_bid; mutually exclusive]

Route elapsed to the correct side table, gated:

  bid_charge = cell_gate(charge, is_bid)                  [charge if bid event, else 0]
  ask_charge = cell_gate(charge, is_ask)                  [charge if ask event, else 0]

  new_bid_time = cell_addsub(TPO_BID_TIME[PRICE_IDX], bid_charge, 0)   [add]
  new_ask_time = cell_addsub(TPO_ASK_TIME[PRICE_IDX], ask_charge, 0)   [add]
```

When the active level is the POC, its `new_bid_time` / `new_ask_time` flow into the POC's
directional fields and delta:

```
  TPO_BAR_POC_BID_TIME = cell_mux(TPO_BAR_POC_BID_TIME, new_bid_time, is_new_max_time)
  TPO_BAR_POC_ASK_TIME = cell_mux(TPO_BAR_POC_ASK_TIME, new_ask_time, is_new_max_time)
  TPO_BAR_TIME_DELTA   = cell_addsub(TPO_BAR_POC_ASK_TIME, TPO_BAR_POC_BID_TIME, 1)  [ask − bid]
```

> `cell_gate(charge, is_bid)` is the branchless replacement for `if (is_bid) bid += charge`. The
> increment lands in exactly one table because `is_bid` and `is_ask` are complementary, so exactly
> one of `bid_charge` / `ask_charge` is non-zero each tick.

---

## 4. Wiring (signal flow)

```
FIFO_RX_TAI ─┬─→ TPO_TIME_DELTA (elapsed = current_TAI − TPO_PREV_TAI)        [§3.1]
             └─→ TPO_PREV_TAI latch (WRITE: TPO_PREV_TAI ← current_TAI)

elapsed ─────→ cell_gate(active) ──→ charge ─┬─→ TPO_TIME_ACCUMULATE          [§3.2]
                                             ├─→ cell_gate(is_bid) → TPO_BID_TIME[idx]   [§3.5]
                                             └─→ cell_gate(is_ask) → TPO_ASK_TIME[idx]   [§3.5]

DOM_TIME[idx] ─→ cell_eqmask(current_TAI) → active (which level is live)
DOM_BID_QTY / DOM_ASK_QTY / DOM_COUNT ─→ side classification (is_bid / is_ask) [§3.5]
DOM_COUNT ─→ delta vs TPO_PREV_TRADE_CNT → new-event detection

TF_BAR_SEQ_REG ─→ cell_eqmask(TPO_LAST_TF_SEQ) → bar_close pulse              [§3.4]

bar_close ─┬─→ snapshot  TPO_BAR_* → TPO_COMP_*   (each via cell_mux(comp,bar,bar_close))
           ├─→ history ring write  (slot = TPO_BAR_SEQ & TPO_HIST_MASK)
           ├─→ TPO_BAR_SEQ increment  (cell_addsub(seq,1,0))
           ├─→ TPO_BAR_PARITY flip    (cell_xor(parity,bar_close)) → virtual table reset
           └─→ reset running POC / min-max / OPEN_SET

active_price ─→ TPO_MIN_MAX_TRACKING (cmp_lt + cell_mux)                      [§3.3]
```

Phase discipline (READ → COMPUTE → WRITE), mirroring `candle.c`:
- **READ:** pre-read FIFO_RX_TAI, all DOM_* lanes, TF_BAR_SEQ, all TPO_* state, and the current
  history-ring slot (so non-close ticks restore ring data instead of zeroing it — candle.c H-05).
- **COMPUTE:** all cell algebra above over the pre-read locals. No `REG_R`.
- **WRITE:** latch running state, table updates, COMP snapshot (gated by `bar_close`), ring,
  control. No `REG_R` in WRITE.

---

## 5. Output Interface (seam_nodes)

Published relay lanes; downstream modules sample these, never TPO internals.

```
TPO_POC_OUT         ← TPO_COMP_POC_PRICE       — completed-bar POC price level
TPO_POC_BID_OUT     ← TPO_COMP_POC_BID_TIME    — completed-bar bid-side time at POC
TPO_POC_ASK_OUT     ← TPO_COMP_POC_ASK_TIME    — completed-bar ask-side time at POC
TPO_TIME_DELTA_OUT  ← TPO_COMP_TIME_DELTA      — completed-bar ask_time − bid_time at POC
```

Consumers: strategy / imbalance modules use the directional `TPO_TIME_DELTA_OUT` (a level where ask
time dominates bid time signals persistent ask-side interest); `TPO_POC_OUT` gives the time-weighted
fair-value level for the bar.

---

## 6. Validation Checklist (gate-level invariants)

- [x] **Continuous accumulation:** time is charged once per tick via `cell_addsub(total, charge, 0)`,
      where `charge = cell_gate(elapsed, active)` — not once per quote. (§3.1, §3.2)
- [x] **Every time-at-price accumulation is an explicit gate-level `cell_addsub`.** (§3.2, §3.5)
- [x] **Bar boundary detection uses `cell_eqmask`** on the timeframe sequence (`bar_close`). (§3.4)
- [x] **Snapshot (BAR → COMP) is gated by the `bar_close` pulse** — every COMP write is
      `cell_mux(comp_old, bar_value, bar_close)`. (§3.4, §4)
- [x] **Bid/ask split is branchless** — `cell_gate(charge, is_bid)` / `cell_gate(charge, is_ask)`,
      with `is_ask = 1 − is_bid`; no `if/else`. (§3.5)
- [x] **Only gate primitives used:** `cell_addsub`, `cell_mux`, `cell_eqmask`, `cell_gate`,
      `cell_xor`, `cmp_lt`. No native `+ − * == != ?: if`, no loops over data, no calls in tick.
- [x] **Module barrier:** inputs from published lanes only (FIFO_RX, DOM, Timeframe); outputs via
      seam_nodes only.
- [x] **gate stage 2d:** comb_nodes specified for every state-updating register → device C will
      contain `cell_*(` calls (cell_count > 0), not a stub.

---

## 7. Next Steps

1. Encode §3 comb_nodes into `tpo.yaml` (`comb_nodes:` section), using the canonical `cells.h`
   argument order.
2. Regenerate the emitter (`partslist-to-emitter.py`) so it reads `comb_nodes`.
3. `python3 gen_tpo_net.py > tpo.net.json` → `python3 validate.py tpo.net.json`
   → `python3 gennet.py tpo.net.json > tpo_gen.h`.
4. `.hft_staging/gate.sh .hft_staging/tpo` — all stages incl. 2d (cell_count > 0) must pass.
5. Commit (user name only; no AI attribution) and graduate.
