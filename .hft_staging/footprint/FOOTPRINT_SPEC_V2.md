# FOOTPRINT_SPEC_V2 — Complete Flip-Flop-Level Specification (Phase 2 prep)

**Status:** SPECIFICATION ONLY. No addresses, no placement, no cross-module
wiring assignment. Seam inputs referenced by symbolic name only.

**Fixes:** WAVE_1_AUDIT.md root cause. The stub netlist had comb fragments but
(a) accumulated level volume into the POC registers themselves (no per-level
storage at all), (b) used `dom_count` as a phantom "current price index"
(ghost value — violates No-Ghost law), and (c) had no wiring, no per-level
bucketing, no bar reset, no history. This spec defines a real per-price-level
store with **eqmask bucketing into a ring of levels**, plus complete
comb_nodes with cell/inputs/fed_by, wiring, and bar-close behavior.

**Machine-readable companion:** `footprint_logic.yaml`.

---

## 0. Module Role and Clocking

Footprint accumulates per-price-level bid/ask volume within the current
timeframe bar, and derives POC (max-volume level), value-area edges
(VAH/VAL), strongest imbalance levels (HVN/LVN), min/max touched price,
bar total volume, and continuous CVD.

**Clock conformance:** passive consumer — owns NO clock (no `clock`,
`counter`, `edge`, `run`, `run_power`, `run_bound` sections; the clock-rule
checker passes quietly). No POWER/RUN_UNTIL registers.

**Data law:** levels are keyed by PRICE (u64 fixed-point, the wire primitive),
not by any invented index. Volumes derive from DOM best-quote quantities.
No floats, no heap, no ghost operands — the stub's `dom_count`-as-index is
removed.

---

## 1. Input Interface (Seam Registers Consumed)

From **DOM** (`dom.net.json` wiring map):

| Symbolic seam register | Use |
|---|---|
| `DOM_BEST_BID_PRICE_REG` | bid-side level key |
| `DOM_BEST_BID_QTY_REG`   | bid-side level volume increment |
| `DOM_BEST_ASK_PRICE_REG` | ask-side level key |
| `DOM_BEST_ASK_QTY_REG`   | ask-side level volume increment |
| `DOM_PREV_BID_PRICE` / `DOM_PREV_ASK_PRICE` | tick-change detect (accumulate only on change) |

From **Timeframe** (`timeframe.net.json`): `TF_BAR_SEQ` (boundary edge
detect), `TF_BAR_START` (bar-open TAI for the completed snapshot).

(Alternative input granularity — DOM's full per-level tables
`DOM_BID_QTY[16384]` / `DOM_ASK_QTY[16384]` — is Open Decision F2.)

---

## 2. Register Definitions

### 2.1 Per-price-level ring (NEW — the missing level store)

```
ring: FP_LEVEL
  depth: 32 slots                  (OPEN DECISION F1 — power of two)
  per-slot registers (4 each):
    FP_LVL_PRICE_i    — level price key (0 = unallocated this bar)
    FP_LVL_ASK_VOL_i  — accumulated ask qty at this price, this bar
    FP_LVL_BID_VOL_i  — accumulated bid qty at this price, this bar
    FP_LVL_PARITY_i   — bar parity tag (virtual reset: slot valid iff
                        FP_LVL_PARITY_i == FP_BAR_PARITY; flipping
                        FP_BAR_PARITY at bar close invalidates all slots
                        without touching N registers)
  allocation cursor:  FP_ALLOC_CUR (wraps: cell_and(cur, FP_LVL_MASK))
```

Bucketing is **eqmask-based**: a quote at price P matches slot i iff
`cell_eqmask(FP_LVL_PRICE_i, P) AND slot_valid_i`. The N-way match/select is
the CELLS.md table-select pattern (one-hot gate + OR-reduce), expanded by the
generator — no loops, no branches in the device.

### 2.2 Scalar live registers (reuse stub dff_nodes + extensions)

Reused: FP_POC_PRICE, FP_POC_VOL, FP_POC_ASK_VOL, FP_POC_BID_VOL, FP_DELTA,
FP_VAH_PRICE, FP_VAL_PRICE, FP_ASK_IMB_PRICE, FP_ASK_IMB_MAG,
FP_BID_IMB_PRICE, FP_BID_IMB_MAG, FP_MIN_PRICE, FP_MAX_PRICE,
FP_BAR_CUM_DELTA (CVD, continuous — NOT reset at bar), FP_BAR_TOTAL_VOL,
FP_BAR_PARITY, FP_LAST_TF_SEQ, FP_BAR_SEQ, FP_STACKED_IMB_BUY,
FP_STACKED_IMB_SELL.

NEW working registers:

| Register | Function |
|---|---|
| FP_ALLOC_CUR | level-ring allocation cursor |
| FP_MIN_SET | bit0: min/max seeded this bar (fixes unseeded min-of-zero) |

### 2.3 Completed-bar snapshot (en = bar_boundary_now)

FP_COMP_POC_PRICE, FP_COMP_POC_VOL, FP_COMP_DELTA, FP_COMP_VAH_PRICE,
FP_COMP_VAL_PRICE, FP_COMP_ASK_IMB_PRICE, FP_COMP_ASK_IMB_MAG,
FP_COMP_BID_IMB_PRICE, FP_COMP_BID_IMB_MAG, FP_COMP_MIN_PRICE,
FP_COMP_MAX_PRICE, FP_COMP_TOTAL_VOL, FP_COMP_CVD, FP_COMP_TAI,
FP_COMP_BAR_SEQ. (15 registers.)

### 2.4 History ring (summary per bar — adapter display_ring pattern)

```
ring: FP_HIST — depth 64 (OPEN DECISION F3, power of two), 15 fields/slot
  (the FP_COMP_* set), slot = cell_and(FP_BAR_SEQ, FP_HIST_MASK),
  write en = bar_boundary_now, fed_by the closing FP_COMP values.
```

### 2.5 const_nodes

FP_ONE=1, FP_ZERO=0, FP_LVL_MASK=31, FP_HIST_MASK=63,
FP_IMB_RATIO_SHIFT (Open Decision F4; imbalance threshold as shift, e.g. 1 →
dominant side > 2× other side — multiplication-free via cell shift/addsub).

---

## 3. READ → COMPUTE → WRITE Behavior (per clock edge)

### READ
Pre-read all seam lanes and every FP_* dff (including all 32×4 level-slot
registers) into locals.

### COMPUTE — comb_nodes (cell, inputs, fed_by)

`cmp_lt`/`cmp_le` are carry-chain gate netlists (cell_fa chain, adapter
gennet reference). Bit0 discipline applies to all flag nodes.

**3.1 Boundary and tick detect**

| comb node | cell | inputs | feeds |
|---|---|---|---|
| bar_seq_same | eqmask | FP_LAST_TF_SEQ, TF_BAR_SEQ | — |
| bar_boundary_now | not(bit0) | bar_seq_same | resets, COMP latches, parity flip |
| not_boundary | buf(bit0) | bar_seq_same | reset gates |
| bid_tick | eqmask+not | DOM_BEST_BID_PRICE_REG, DOM_PREV_BID_PRICE | bid accumulate enable |
| ask_tick | eqmask+not | DOM_BEST_ASK_PRICE_REG, DOM_PREV_ASK_PRICE | ask accumulate enable |

**3.2 Level matching (per slot i = 0..N−1, generator-unrolled)**

| comb node | cell | inputs | feeds |
|---|---|---|---|
| slot_valid_i | eqmask | FP_LVL_PARITY_i, FP_BAR_PARITY | match gates |
| match_bid_i | and(eqmask(FP_LVL_PRICE_i, DOM_BEST_BID_PRICE_REG), slot_valid_i) | — | bid slot enable |
| match_ask_i | and(eqmask(FP_LVL_PRICE_i, DOM_BEST_ASK_PRICE_REG), slot_valid_i) | — | ask slot enable |
| any_match_bid | or-reduce | match_bid_0..N−1 | allocation decision |
| any_match_ask | or-reduce | match_ask_0..N−1 | allocation decision |

**3.3 Allocation (branchless, ≤2 new slots/tick)**

| comb node | cell | inputs | feeds |
|---|---|---|---|
| alloc_bid | and(bid_tick, not(any_match_bid)) | — | bid alloc enable |
| ask_hits_new_bid | and(eqmask(DOM_BEST_ASK_PRICE_REG, DOM_BEST_BID_PRICE_REG), alloc_bid) | — | route ask into bid's new slot |
| alloc_ask | and(ask_tick, not(any_match_ask), not(ask_hits_new_bid)) | — | ask alloc enable |
| cur0 | and | FP_ALLOC_CUR, FP_LVL_MASK | slot index for bid alloc |
| cur1 | and(addsub(FP_ALLOC_CUR, alloc_bid_bit, 0), FP_LVL_MASK) | — | slot index for ask alloc |
| alloc_cur_next | addsub(sub=0) | FP_ALLOC_CUR, (alloc_bid_bit + alloc_ask_bit via addsub) | FP_ALLOC_CUR dff; reset to 0 on boundary via mux |
| alloc_sel_bid_i | eqmask(slot_const_i, cur0) AND alloc_bid | — | slot i alloc-as-bid enable |
| alloc_sel_ask_i | eqmask(slot_const_i, cur1) AND alloc_ask | — | slot i alloc-as-ask enable |

**3.4 Per-slot accumulation (slot i)**

| comb node | cell | inputs | feeds (fed_by of the slot dffs) |
|---|---|---|---|
| en_bid_i | or | and(match_bid_i, bid_tick), alloc_sel_bid_i, and(ask_hits_new_bid... routed) | — |
| en_ask_i | or | and(match_ask_i, ask_tick), alloc_sel_ask_i, and(alloc_sel_bid_i, ask_hits_new_bid) | — |
| lvl_price_next_i | mux chain | hold FP_LVL_PRICE_i; take DOM_BEST_BID_PRICE_REG on alloc_sel_bid_i; take DOM_BEST_ASK_PRICE_REG on alloc_sel_ask_i | FP_LVL_PRICE_i (dff) |
| lvl_bid_inc_i | gate | DOM_BEST_BID_QTY_REG, en_bid_i | — |
| lvl_bid_base_i | gate | FP_LVL_BID_VOL_i, and(slot_valid_i, not_boundary) | (stale/foreign-parity slot contributes 0) |
| lvl_bid_next_i | addsub(0) | lvl_bid_base_i, lvl_bid_inc_i | FP_LVL_BID_VOL_i (dff) |
| lvl_ask_*_i | (mirror) | … | FP_LVL_ASK_VOL_i (dff) |
| lvl_parity_next_i | mux | a=FP_LVL_PARITY_i, b=FP_BAR_PARITY, sel=or(alloc_sel_bid_i, alloc_sel_ask_i) | FP_LVL_PARITY_i (dff) |
| lvl_vol_i | addsub(0) | lvl_ask_next_i, lvl_bid_next_i | POC scan |
| lvl_delta_i | addsub(1) | lvl_ask_next_i, lvl_bid_next_i | imbalance scan |

**3.5 POC — running max over the ACTIVE slots (event-driven, correct
because per-level volumes only grow within a bar).** The two touched slots
this tick are selected via one-hot OR-reduce:

| comb node | cell | inputs | feeds |
|---|---|---|---|
| act_vol_b | or-reduce of gate(lvl_vol_i, en_bid_i) | — | bid-side candidate |
| act_price_b | or-reduce of gate(lvl_price_next_i, en_bid_i) | — | |
| act_delta_b | or-reduce of gate(lvl_delta_i, en_bid_i) | — | |
| poc_beat_b | cmp_lt | FP_POC_VOL, act_vol_b | — |
| poc_price_1 | mux(FP_POC_PRICE, act_price_b, poc_beat_b) | — | — |
| poc_vol_1 / poc_delta_1 / poc_ask_1 / poc_bid_1 | mux | (same pattern) | — |
| (repeat vs ask-side candidate act_*_a → poc_*_2) | cmp_lt+mux | poc_*_1 vs act_vol_a | — |
| poc_*_next | mux | a=poc_*_2, b=FP_ZERO/act seeds, sel=bar_boundary_now (boundary resets POC to the boundary-tick state) | FP_POC_PRICE, FP_POC_VOL, FP_POC_ASK_VOL, FP_POC_BID_VOL, FP_DELTA (dffs) |

**3.6 Min/max price touched (seeded; fixes stub bug)**

min/max maintained over act_price_b and act_price_a with cmp_lt+mux, seeded
on first tick of bar via FP_MIN_SET (mux to candidate when FP_MIN_SET=0),
reset by boundary (FP_MIN_SET ← 0). Feeds FP_MIN_PRICE, FP_MAX_PRICE,
FP_MIN_SET dffs.

**3.7 Imbalance / value area (per active slot candidate)**

| comb node | cell | inputs | feeds |
|---|---|---|---|
| ask_dom | cmp_lt | act_bid_vol, shifted ask vol (threshold via FP_IMB_RATIO_SHIFT, Open Decision F4) | — |
| bid_dom | cmp_lt | act_ask_vol(shifted), act_bid_vol | — |
| take_vah | and(ask_dom, cmp_lt(FP_VAH_PRICE, act_price)) | — | FP_VAH_PRICE via mux |
| take_val | and(bid_dom, cmp_lt(act_price, FP_VAL_PRICE)) | — | FP_VAL_PRICE via mux (seeded like min) |
| hvn: ask_mag=gate(act_delta, ask_dom); take_hvn=and(ask_dom, cmp_lt(FP_ASK_IMB_MAG, ask_mag)) | — | — | FP_ASK_IMB_PRICE / FP_ASK_IMB_MAG via mux |
| lvn: bid_excess=addsub(act_bid_vol, act_ask_vol, 1) gated by bid_dom; take_lvn analogous | — | — | FP_BID_IMB_PRICE / FP_BID_IMB_MAG via mux |
| stacked: buy_qualifies=and(ask_dom, cmp_lt(FP_POC_PRICE, act_price)); new_buy=gate(addsub(FP_STACKED_IMB_BUY, FP_ONE, 0), buy_qualifies) | — | — | FP_STACKED_IMB_BUY (reset-on-miss); sell mirror → FP_STACKED_IMB_SELL |

All of these reset on boundary via the not_boundary gate / boundary mux,
EXCEPT FP_BAR_CUM_DELTA (CVD) which accumulates continuously.

**3.8 Bar totals and CVD**

| comb node | cell | inputs | feeds |
|---|---|---|---|
| quote_delta | addsub(1) | gate(DOM_BEST_ASK_QTY_REG, ask_tick), gate(DOM_BEST_BID_QTY_REG, bid_tick) | — |
| cvd_next | addsub(0) | FP_BAR_CUM_DELTA, quote_delta | FP_BAR_CUM_DELTA (dff, NO bar reset) |
| quote_vol | addsub(0) | gated ask qty, gated bid qty | — |
| total_base | gate | FP_BAR_TOTAL_VOL, not_boundary | — |
| total_next | addsub(0) | total_base, quote_vol | FP_BAR_TOTAL_VOL (dff) |

**3.9 Bar close bookkeeping**

| comb node | cell | inputs | feeds |
|---|---|---|---|
| parity_flip | xor | FP_BAR_PARITY, FP_ONE | — |
| parity_next | mux | a=FP_BAR_PARITY, b=parity_flip, sel=bar_boundary_now | FP_BAR_PARITY (dff) — virtual reset of all level slots |
| bar_seq_next | mux(FP_BAR_SEQ, addsub(FP_BAR_SEQ, FP_ONE, 0), bar_boundary_now) | — | FP_BAR_SEQ (dff) |
| last_tf_next | buf | TF_BAR_SEQ | FP_LAST_TF_SEQ (dff) |
| hist_slot_idx | and | FP_BAR_SEQ, FP_HIST_MASK | FP_HIST slot one-hot |
| 15 × FP_COMP_* | dff(en=bar_boundary_now) | closing values of POC/VAH/VAL/imb/min/max/total/CVD/TF_BAR_START/FP_BAR_SEQ | FP_COMP_* |

### WRITE
Commit every dff once (live scalars, all N×4 slot registers, COMP latches,
ring slots). Single writer per register; no read-after-write (all `*_next`
computed from pre-read state).

---

## 4. Output Interface (Seam Nodes Published)

| Seam group | Lanes |
|---|---|
| FP_POC_OUT | FP_POC_PRICE, FP_POC_VOL, FP_POC_ASK_VOL, FP_POC_BID_VOL, FP_DELTA |
| FP_VALUE_AREA_OUT | FP_VAH_PRICE, FP_VAL_PRICE |
| FP_IMBALANCE_OUT | FP_ASK_IMB_PRICE/MAG, FP_BID_IMB_PRICE/MAG, FP_STACKED_IMB_BUY/SELL |
| FP_RANGE_OUT | FP_MIN_PRICE, FP_MAX_PRICE |
| FP_FLOW_OUT | FP_BAR_CUM_DELTA (CVD), FP_BAR_TOTAL_VOL |
| FP_LEVEL_OUT | FP_LVL_PRICE/ASK_VOL/BID_VOL/PARITY ×N (raw level table for display) |
| FP_COMP_OUT / FP_HIST_OUT | snapshots + history ring (CBR consumes) |

---

## 5. Open Decisions for the Founder

- **F1 — Level-ring depth (price-level granularity per bar).** Recommended
  default: **32 slots** (covers typical intra-bar best-price excursion;
  4 regs/slot → 128 regs + unrolled match logic). Alternatives: 16 (small),
  64 (wide bars / high timeframes). Power of two required.
- **F2 — Input granularity.** Recommended default: **best-quote seam regs**
  (DOM_BEST_*_REG; event-driven, bounded logic). Alternative: consume DOM's
  full 16384-deep DOM_BID_QTY/DOM_ASK_QTY tables with a sweep cursor (full
  book footprint, +16k-wide select logic — large).
- **F3 — History ring depth.** Recommended default: **64 bars** of FP_COMP
  summaries. Alternatives: 16, 256. Note: history stores summaries only, not
  the per-level table (a full level-table history is depth×N×4 registers —
  founder call if needed).
- **F4 — Imbalance threshold.** Recommended default: **shift-based ratio,
  FP_IMB_RATIO_SHIFT = 1** (dominant side > 2× the other; multiplication-free).
  Alternatives: shift 0 (any excess, the stub's implicit semantics), shift 2
  (>4×). A non-power-of-two ratio (e.g. 3:1 classic footprint) needs
  cell-based multiply — founder call.
- **F5 — Ring-full policy.** Recommended default: **drop new levels when all
  N slots are this-bar valid** (alloc enable AND NOT all_valid; min/max
  registers still track the full range). Alternative: overwrite
  oldest (cursor wraps and evicts) — corrupts POC history within bar.
