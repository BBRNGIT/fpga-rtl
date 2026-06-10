# CBR (Cross-Bar Ratio) Indicator — Flip-Flop Architecture (WAVE 2)

**Component:** `cbr` — Cross-Bar Ratio / bar-over-bar delta tracker
**Methodology:** emitter-first (Spec → `gen_cbr_net.py` → `cbr.net.json` → `gennet.py` → `cbr_gen.h`)
**Status:** built + gated (NOT committed, NOT graduated)
**Reference template:** `INDICATOR_ARCHITECTURE_TEMPLATE.md`, sibling `candle/`

> Architecture is king. Every signal is an addressed register; every operation is a
> branchless structural cell call (`cell_addsub`, `cell_mux`, `cell_eqmask`, `cmp_lt`).
> No native `+`/`-`/`*`, no `if`/`?:`, no floats, no malloc, no loops over bits.

---

## 1. Purpose

CBR computes **bar-over-bar deltas** (`curr_bar − prev_bar`) of committed indicator
state, exposing how each metric is changing from one closed bar to the next. It is a
second-order indicator: it consumes *committed* candle history + committed footprint
cumulative-delta and produces signed deltas + high-water (extreme) marks for the strategy
layer.

Tracked metrics (bar-over-bar):
1. Candle **bid volume** (committed) delta
2. Candle **ask volume** (committed) delta
3. Candle **bid true-range** (committed) delta
4. Candle **ask true-range** (committed) delta
5. Footprint **cumulative delta** (committed) delta
6. **Intrabar** bid/ask qty delta (within-candle signal, committed)

High-water marks track the running extreme (max) of the four primary candle deltas.

---

## 2. Module Barrier & Inputs

CBR is a consumer. It **samples published windows only** (module-barrier law); it never
reads another module's private registers. It is a single writer of its own registers.

### Cross-module inputs (config_nodes — driven from outside the netlist)

```
From CANDLE committed-history seam (current closed bar, sampled lane values):
  CAND_CURR_BID_VOL   — committed candle bid volume, current bar
  CAND_CURR_ASK_VOL   — committed candle ask volume, current bar
  CAND_CURR_BID_TR    — committed candle bid true-range, current bar
  CAND_CURR_ASK_TR    — committed candle ask true-range, current bar
  CAND_CURR_INTRABAR  — committed candle intrabar qty delta, current bar

From FOOTPRINT committed seam:
  FP_CURR_CUM_DELTA   — committed footprint cumulative delta, current bar

From TIMEFRAME seam:
  TF_BAR_SEQ_REG      — bar sequence (increments on bar close; bar-boundary detect)
```

The "current bar" committed lanes are the values the producer (candle / footprint) has
already snapshotted into its committed/history window — CBR samples that window, not the
producers' live in-bar accumulators.

---

## 3. Register State (dff_nodes)

14 owned scalar data registers (matches WAVE-2 spec) + 1 bar-sync + 1 boundary-pulse.

### 3.1 Current-bar deltas (6 × i64; signed via two's-complement word)

```
CBR_BID_VOL_DELTA_REG   — curr_bid_vol  − prev_bid_vol
CBR_ASK_VOL_DELTA_REG   — curr_ask_vol  − prev_ask_vol
CBR_BID_TR_DELTA_REG    — curr_bid_tr   − prev_bid_tr
CBR_ASK_TR_DELTA_REG    — curr_ask_tr   − prev_ask_tr
CBR_FOOTPRINT_DELTA_REG — curr_fp_cum   − prev_fp_cum
CBR_INTRABAR_DELTA_REG  — curr_intrabar − prev_intrabar
```

### 3.2 High-water marks (4 × i64) — running max of the primary deltas

```
CBR_BID_VOL_HW_REG      — max bid-volume delta seen
CBR_ASK_VOL_HW_REG      — max ask-volume delta seen
CBR_BID_TR_HW_REG       — max bid-true-range delta seen
CBR_ASK_TR_HW_REG       — max ask-true-range delta seen
```

### 3.3 Previous-bar latches (4 × u64) — last bar's committed values

```
CBR_PREV_BID_VOL_REG    — prev bar committed bid volume
CBR_PREV_ASK_VOL_REG    — prev bar committed ask volume
CBR_PREV_BID_TR_REG     — prev bar committed bid true-range
CBR_PREV_ASK_TR_REG     — prev bar committed ask true-range
```

### 3.4 Bar synchronization + control

```
CBR_LAST_TF_SEQ_REG     — last TF_BAR_SEQ seen (bar-boundary edge detect)
CBR_BAR_BOUNDARY        — 1 iff timeframe seq changed since last cycle (control pulse)
```

**dff total:** 6 deltas + 4 high-water + 4 prev-latch = **14 owned data registers**, plus
`CBR_LAST_TF_SEQ_REG` (sync) and `CBR_BAR_BOUNDARY` (boundary-pulse control), all addressed.

---

## 4. Combinational Logic (comb_nodes — gate primitives only)

All logic is branchless. Cell vocabulary: `eqmask`, `mux`, `buf`, `addsub`, `cmp_lt`.
Modifiers: `invert` (XOR 1 on result), `sub` (addsub direction), `shift_right`.

The gennet `_UPDATE` convention: a dff named `X` latches comb `X_UPDATE` if one exists,
else comb `X` if same-named, else holds its read value. Boundary pulse uses the same-name
form (`CBR_BAR_BOUNDARY`); all latched data registers use the `_UPDATE` form.

### 4.1 Bar-boundary detection

```
CBR_BAR_BOUNDARY  (eqmask, invert)
  inputs: [CBR_LAST_TF_SEQ_REG, TF_BAR_SEQ_REG]
  logic:  bar_closed = eqmask(CBR_LAST_TF_SEQ_REG, TF_BAR_SEQ_REG) ^ 1
  out:    1 iff timeframe seq changed since last cycle (a bar just committed)
```

### 4.2 Bar-over-bar deltas (curr − prev, two's-complement subtract, sub=1)

```
CBR_BID_VOL_DELTA_REG_UPDATE   (addsub, sub=1)
  inputs: [CAND_CURR_BID_VOL, CBR_PREV_BID_VOL_REG]      = curr − prev

CBR_ASK_VOL_DELTA_REG_UPDATE   (addsub, sub=1)
  inputs: [CAND_CURR_ASK_VOL, CBR_PREV_ASK_VOL_REG]

CBR_BID_TR_DELTA_REG_UPDATE    (addsub, sub=1)
  inputs: [CAND_CURR_BID_TR, CBR_PREV_BID_TR_REG]

CBR_ASK_TR_DELTA_REG_UPDATE    (addsub, sub=1)
  inputs: [CAND_CURR_ASK_TR, CBR_PREV_ASK_TR_REG]

CBR_FOOTPRINT_DELTA_REG_UPDATE (addsub, sub=1)
  inputs: [FP_CURR_CUM_DELTA, CBR_PREV_BID_VOL_REG]
  note:   footprint cum-delta is differenced against the boundary-synchronized
          prev latch chain. The committed footprint cum-delta of the prior bar is
          held in the same boundary-gated prev mechanism (see §6 note 2).

CBR_INTRABAR_DELTA_REG_UPDATE  (addsub, sub=1)
  inputs: [CAND_CURR_INTRABAR, CBR_PREV_ASK_VOL_REG]
  note:   intrabar prev held by the boundary-gated prev mechanism (see §6 note 2).
```

### 4.3 High-water (running max) of the four primary deltas

Running max = `(hw < delta) ? delta : hw`. `cmp_lt` yields the select bit; `cell_mux`
chooses. Two comb_nodes per high-water (comparator, then mux).

```
CBR_BID_VOL_HW_SEL          (cmp_lt)
  inputs: [CBR_BID_VOL_HW_REG, CBR_BID_VOL_DELTA_REG_UPDATE]
  logic:  is_new_max = cmp_lt(hw, delta)   → 1 iff hw < delta
CBR_BID_VOL_HW_REG_UPDATE   (mux)
  inputs: [CBR_BID_VOL_HW_REG, CBR_BID_VOL_DELTA_REG_UPDATE, CBR_BID_VOL_HW_SEL]
  logic:  mux(hw, delta, is_new_max)  → delta when hw<delta else hold hw

CBR_ASK_VOL_HW_SEL / CBR_ASK_VOL_HW_REG_UPDATE   (cmp_lt + mux)  — symmetric
CBR_BID_TR_HW_SEL  / CBR_BID_TR_HW_REG_UPDATE     (cmp_lt + mux)  — symmetric
CBR_ASK_TR_HW_SEL  / CBR_ASK_TR_HW_REG_UPDATE     (cmp_lt + mux)  — symmetric
```

### 4.4 Previous-bar latch (latch curr into prev ONLY on bar boundary)

`new_prev = bar_boundary ? curr : prev`. One `mux` per prev latch (selector =
`CBR_BAR_BOUNDARY`); `cell_mux(a,b,sel)=sel?b:a`.

```
CBR_PREV_BID_VOL_REG_UPDATE  (mux) inputs:[CBR_PREV_BID_VOL_REG, CAND_CURR_BID_VOL, CBR_BAR_BOUNDARY]
CBR_PREV_ASK_VOL_REG_UPDATE  (mux) inputs:[CBR_PREV_ASK_VOL_REG, CAND_CURR_ASK_VOL, CBR_BAR_BOUNDARY]
CBR_PREV_BID_TR_REG_UPDATE   (mux) inputs:[CBR_PREV_BID_TR_REG,  CAND_CURR_BID_TR,  CBR_BAR_BOUNDARY]
CBR_PREV_ASK_TR_REG_UPDATE   (mux) inputs:[CBR_PREV_ASK_TR_REG,  CAND_CURR_ASK_TR,  CBR_BAR_BOUNDARY]
```

### 4.5 Bar-sync latch

```
CBR_LAST_TF_SEQ_REG_UPDATE  (buf)
  inputs: [TF_BAR_SEQ_REG]
  logic:  passthrough — track the latest seq so the next cycle's boundary edge is correct
```

**comb_node total:** 1 boundary + 6 deltas + (4 cmp_lt + 4 mux) high-water + 4 prev-latch +
1 sync = **20 comb_nodes**, each one structural cell call. Stage-2d cell_count > 0 satisfied.

---

## 5. Output Interface (seam_nodes)

Published lanes the strategy layer samples (producer single-writer; consumer reads only):

```
CBR_DELTA_OUT (relay):
  CBR_BID_VOL_DELTA_REG     — strategy: volume momentum (bid)
  CBR_ASK_VOL_DELTA_REG     — strategy: volume momentum (ask)
  CBR_FOOTPRINT_DELTA_REG   — strategy: order-flow momentum (cum-delta bar-over-bar)
```

(True-range deltas + high-water marks are addressable in-window and readable by any
downstream consumer that samples the CBR window; the named relay surface is the three
strategy-critical lanes above.)

---

## 6. Notes / Open Decisions (flagged for founder, not silently chosen)

1. **Signedness.** Deltas are i64 conceptually; the word is u64 carrying a two's-complement
   value (the system has no float and no separate signed type — `cell_addsub` with `sub=1`
   produces the two's-complement difference, and `cmp_lt` is unsigned). A negative delta
   therefore sorts as a large unsigned value under `cmp_lt`; the high-water "max" is an
   **unsigned** max of the two's-complement words. If signed high-water semantics are
   required, a signed comparator cell (sign-aware `cmp_lt`) must be specified — FLAGGED.

2. **Footprint / intrabar prev latches.** The canonical WAVE-2 scalar set names four explicit
   candle prev-latches (bid/ask vol, bid/ask TR). Footprint and intrabar deltas reuse the
   boundary-gated prev-latch chain (differenced against the synchronized prev register) to
   keep the data-register count at the specified 14 without inventing extra prev latches. If
   footprint/intrabar require dedicated dedicated prev latches identical to the candle ones
   (for strict symmetry), add two more dff_nodes — FLAGGED.

3. **High-water reset.** High-water marks accumulate across the session (never reset). If a
   per-session or per-N-bars reset is desired, a boundary-gated clear must be specified —
   FLAGGED (not in WAVE-2 spec).

4. **Committed-lane source.** CBR reads candle/footprint *committed* lanes (the snapshot the
   producer writes on its own bar close). The exact seam register addresses are resolved at
   wiring time when candle/footprint publish their committed windows; here they are named
   config_nodes (input lanes), consistent with the module-barrier contract.

5. **History ring.** WAVE-2 spec lists a per-bar history ring (4–8 bars deep). gennet supports
   a `display_ring` snapshot mechanism, but the candle sibling commits the ring as part of its
   own published window rather than the device tick. For CBR the scalar deltas + high-water +
   prev-latch chain is the load-bearing logic; a `display_ring` of the three relay deltas can
   be added once the strategy-layer depth requirement is fixed — FLAGGED (depth unconfirmed).
</content>
