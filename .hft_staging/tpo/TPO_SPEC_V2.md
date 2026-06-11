# TPO_SPEC_V2 — Complete Flip-Flop-Level Specification (Phase 2 prep)

**Status:** SPECIFICATION ONLY. No addresses, no placement, no cross-module
wiring assignment. Seam inputs referenced by symbolic name only.

**Fixes:** WAVE_1_AUDIT.md root cause. The stub netlist had 5 comb fragments
with no per-level storage, no period dedupe, no POC, no wiring/fed_by, and a
ghost selection trick (`DOM_TIME == FIFO_RX_TAI` against an un-indexed table
lane). This spec defines real Time-Price-Opportunity letter/period
accumulation: a ring of price levels, one TPO count per level per period
touched, POC by max TPO count, with every comb node's cell, inputs, and
fed_by attribution.

**Machine-readable companion:** `tpo_logic.yaml`.

---

## 0. Module Role and Clocking

TPO counts, per price level, the number of timeframe periods ("letters") in
which the market traded at that level during the current session. A level's
TPO count increments at most once per period (dedupe by last-touched period
sequence). POC = level with the maximum TPO count.

**Model mapping:** one timeframe bar (TF_BAR_SEQ increment) = one TPO period
(letter). A session = `TPO_PERIODS_PER_SESSION` consecutive periods
(Open Decision T2). Letters themselves are display vocabulary — the device
stores period counts; the external display renders letters.

**Clock conformance:** passive consumer — owns NO clock (no `clock`,
`counter`, `edge`, `run`, `run_power`, `run_bound` sections; the clock-rule
checker passes quietly). Period timing comes from the timeframe seam.

**Data law:** levels keyed by price (wire primitive); counts derive from
price × time (TF period boundaries). No invented fields, no floats.

---

## 1. Input Interface (Seam Registers Consumed)

From **DOM** (`dom.net.json` wiring map):

| Symbolic seam register | Use |
|---|---|
| `DOM_BEST_BID_PRICE_REG` | bid-side touch key |
| `DOM_BEST_ASK_PRICE_REG` | ask-side touch key |
| `DOM_LAST_FEED_TIME_REG` | TAI for optional time-at-price accumulation (T4) — replaces the stub's `FIFO_RX_TAI` reach-through; DOM's published last-feed TAI is the module-barrier-correct source |

From **Timeframe** (`timeframe.net.json`): `TF_BAR_SEQ` (period/letter
clock), `TF_BAR_START` (period-open TAI; session COMP timestamp).

---

## 2. Register Definitions

### 2.1 Per-price-level ring (NEW — the level store)

```
ring: TPO_LVL
  depth: 32 slots                 (OPEN DECISION T1 — power of two)
  per-slot registers (4 each; +2 optional under T4):
    TPO_LVL_PRICE_i       — level price key
    TPO_LVL_COUNT_i       — TPO count (periods touched) this session
    TPO_LVL_LAST_PERIOD_i — TF_BAR_SEQ of the most recent period in which
                            this level was touched (the dedupe register)
    TPO_LVL_PARITY_i      — session parity tag (virtual reset, as footprint)
    [TPO_LVL_TIME_i       — optional cumulative TAI ns at level (T4)]
  allocation cursor: TPO_ALLOC_CUR
```

Bucketing is eqmask-based one-hot table select, identical in structure to
footprint's FP_LVL ring (CELLS.md table-select pattern; generator-unrolled,
branchless).

### 2.2 Scalar live registers (stub registers reused where meaningful)

| Register | Origin | Function |
|---|---|---|
| TPO_LAST_TF_SEQ | reused | last TF_BAR_SEQ seen (period-boundary edge detect) |
| TPO_PREV_TAI | reused | last TAI processed (subtrahend for T4 elapsed time) |
| TPO_BAR_PARITY | reused (renamed role) | SESSION parity tag (virtual reset) |
| TPO_PERIOD_IN_SESSION | NEW | periods elapsed in current session (0..limit−1) |
| TPO_SESSION_SEQ | NEW | session counter (history-ring write cursor) |
| TPO_POC_PRICE | NEW (replaces stub TPO_BAR_POC_TOTAL pair) | price of max-TPO level |
| TPO_POC_COUNT | NEW | TPO count at POC |
| TPO_MIN_PRICE / TPO_MAX_PRICE / TPO_MIN_SET | NEW | session price range (seeded) |
| TPO_TOTAL | NEW | total TPO count across levels this session (profile mass) |
| TPO_ALLOC_CUR | NEW | level-ring allocation cursor |

Dropped from the stub: `TPO_BID_TIME` / `TPO_ASK_TIME` / `TPO_STATE`
(un-indexed scalar time accumulators with no level association — replaced by
the per-slot store; optional side-split returns under T4) and the
`FIFO_RX_TAI` config input (replaced by `DOM_LAST_FEED_TIME_REG`).

### 2.3 Completed-session snapshot (en = session_close_now)

TPO_COMP_POC_PRICE, TPO_COMP_POC_COUNT, TPO_COMP_MIN_PRICE,
TPO_COMP_MAX_PRICE, TPO_COMP_TOTAL, TPO_COMP_TAI (session-open TAI),
TPO_COMP_SESSION_SEQ. (7 registers.)

### 2.4 History ring

```
ring: TPO_HIST — depth 16 sessions (OPEN DECISION T3, power of two),
  7 fields/slot (the TPO_COMP_* set),
  slot = cell_and(TPO_SESSION_SEQ, TPO_HIST_MASK),
  write en = session_close_now.
```

### 2.5 const_nodes

TPO_ONE=1, TPO_ZERO=0, TPO_LVL_MASK=31, TPO_HIST_MASK=15,
TPO_PERIODS_PER_SESSION (default 48 — Open Decision T2).

---

## 3. READ → COMPUTE → WRITE Behavior (per clock edge)

### READ
Pre-read all seam lanes and every TPO_* dff (incl. 32×4 slot registers).

### COMPUTE — comb_nodes (cell, inputs, fed_by)

**3.1 Period and session boundary detection**

| comb node | cell | inputs | feeds |
|---|---|---|---|
| period_same | eqmask | TPO_LAST_TF_SEQ, TF_BAR_SEQ | — |
| period_close_now | not(bit0) | period_same | TPO count harvest, period counter |
| pis_inc | addsub(0) | TPO_PERIOD_IN_SESSION, gated TPO_ONE (en=period_close_now) | — |
| session_full | eqmask | pis_inc, TPO_PERIODS_PER_SESSION | — |
| session_close_now | and | period_close_now, session_full | COMP latches, parity flip, resets |
| pis_next | mux | a=pis_inc, b=TPO_ZERO, sel=session_close_now | TPO_PERIOD_IN_SESSION (dff) |
| last_tf_next | buf | TF_BAR_SEQ | TPO_LAST_TF_SEQ (dff) |
| not_session_close | not(bit0) | session_close_now | reset gates |

**3.2 Level matching and allocation (slot i, generator-unrolled; identical
structure to footprint §3.2–3.3)**

| comb node | cell | inputs | feeds |
|---|---|---|---|
| slot_valid_i | eqmask | TPO_LVL_PARITY_i, TPO_BAR_PARITY | — |
| match_bid_i / match_ask_i | and(eqmask(TPO_LVL_PRICE_i, DOM_BEST_*_PRICE_REG), slot_valid_i) | — | touch enables |
| touched_i | or | match_bid_i, match_ask_i, alloc_sel_*_i | last-period latch enable |
| any_match_bid / any_match_ask | or-reduce | match_*_i | — |
| alloc_bid / ask_hits_new_bid / alloc_ask / cur0 / cur1 / alloc_cur_next / alloc_sel_bid_i / alloc_sel_ask_i | (exactly the footprint allocation netlist with TPO names) | … | TPO_ALLOC_CUR, slot price latches |

**3.3 Touch marking (every tick)**

| comb node | cell | inputs | feeds |
|---|---|---|---|
| lvl_price_next_i | mux chain | hold / take bid price on alloc_sel_bid_i / take ask price on alloc_sel_ask_i | TPO_LVL_PRICE_i (dff) |
| lvl_lastp_next_i | mux | a=TPO_LVL_LAST_PERIOD_i, b=TF_BAR_SEQ, sel=touched_i | TPO_LVL_LAST_PERIOD_i (dff) — "this level was touched during period TF_BAR_SEQ" |
| lvl_parity_next_i | mux | a=TPO_LVL_PARITY_i, b=TPO_BAR_PARITY, sel=or(alloc_sel_bid_i, alloc_sel_ask_i) | TPO_LVL_PARITY_i (dff) |

**3.4 TPO count harvest (on period close — the letter accumulation)**

On the tick where period_close_now=1, TPO_LAST_TF_SEQ still holds the seq of
the period that just closed (pre-read value). Each slot whose
LAST_PERIOD == closed period gets +1:

| comb node | cell | inputs | feeds |
|---|---|---|---|
| touched_in_closed_i | eqmask | TPO_LVL_LAST_PERIOD_i, TPO_LAST_TF_SEQ | — |
| harvest_i | and | touched_in_closed_i, period_close_now, slot_valid_i | — |
| count_base_i | gate | TPO_LVL_COUNT_i, and(slot_valid_i, not_session_close) | session reset |
| lvl_count_next_i | addsub(0) | count_base_i, harvest_bit_i | TPO_LVL_COUNT_i (dff) |
| total_inc | addsub-reduce(0) | harvest_bit_0..N−1 (balanced adder tree, generator-expanded) | — |
| total_base | gate | TPO_TOTAL, not_session_close | — |
| total_next | addsub(0) | total_base, total_inc | TPO_TOTAL (dff) |

**3.5 POC — argmax over slot counts (combinational tournament chain,
evaluated every tick from the *next* counts; generator-unrolled N stages)**

| comb node | cell | inputs | feeds |
|---|---|---|---|
| poc_c_0 = gate(lvl_count_next_0, slot_valid_0); poc_p_0 = lvl_price_next_0 | gate/buf | slot 0 | chain seed |
| beat_i (i=1..N−1) | cmp_lt | poc_c_{i−1}, gate(lvl_count_next_i, slot_valid_i) | — |
| poc_c_i | mux | a=poc_c_{i−1}, b=lvl_count_next_i, sel=beat_i | chain |
| poc_p_i | mux | a=poc_p_{i−1}, b=lvl_price_next_i, sel=beat_i | chain |
| poc_price_next | mux | a=poc_p_{N−1}, b=TPO_ZERO, sel=session_close_now | TPO_POC_PRICE (dff) |
| poc_count_next | mux | a=poc_c_{N−1}, b=TPO_ZERO, sel=session_close_now | TPO_POC_COUNT (dff) |

(Linear chain depth N=32; a log-depth tournament tree is an equivalent
generator choice — same cells, same count.)

**3.6 Session min/max price (seeded, as footprint §3.6)** — candidates are
DOM_BEST_BID_PRICE_REG (min side) and DOM_BEST_ASK_PRICE_REG (max side);
cmp_lt+mux, seed via TPO_MIN_SET, reset on session_close_now. Feeds
TPO_MIN_PRICE, TPO_MAX_PRICE, TPO_MIN_SET.

**3.7 Optional time-at-price (Open Decision T4):** elapsed =
addsub(DOM_LAST_FEED_TIME_REG, TPO_PREV_TAI, 1); charge_i =
gate(elapsed, touched_i); TPO_LVL_TIME_i += charge_i;
TPO_PREV_TAI ← DOM_LAST_FEED_TIME_REG (buf). Adds 1 reg/slot + 1 scalar.

**3.8 Session close bookkeeping**

| comb node | cell | inputs | feeds |
|---|---|---|---|
| parity_next | mux(TPO_BAR_PARITY, xor(TPO_BAR_PARITY, TPO_ONE), session_close_now) | — | TPO_BAR_PARITY (dff) — virtual reset of all slots |
| session_seq_next | mux(TPO_SESSION_SEQ, addsub(TPO_SESSION_SEQ, TPO_ONE, 0), session_close_now) | — | TPO_SESSION_SEQ (dff) |
| hist_slot_idx | and | TPO_SESSION_SEQ, TPO_HIST_MASK | TPO_HIST slot one-hot |
| 7 × TPO_COMP_* | dff(en=session_close_now) | closing POC/min/max/total/TF_BAR_START/TPO_SESSION_SEQ | TPO_COMP_* |

### WRITE
Commit every dff once from its single `*_next` driver; no read-after-write.

---

## 4. Output Interface (Seam Nodes Published)

| Seam group | Lanes |
|---|---|
| TPO_POC_OUT | TPO_POC_PRICE, TPO_POC_COUNT |
| TPO_RANGE_OUT | TPO_MIN_PRICE, TPO_MAX_PRICE |
| TPO_PROFILE_OUT | TPO_LVL_PRICE_i, TPO_LVL_COUNT_i, TPO_LVL_PARITY_i ×N (raw profile; display renders letters) |
| TPO_TOTAL_OUT | TPO_TOTAL, TPO_PERIOD_IN_SESSION, TPO_SESSION_SEQ |
| TPO_COMP_OUT / TPO_HIST_OUT | session snapshots + history ring |

---

## 5. Open Decisions for the Founder

- **T1 — Level-ring depth.** Recommended default: **32** (power of two).
  Alternatives: 16, 64. Sessions span more price than bars — if sessions are
  long, 64 may be safer; founder call with T2.
- **T2 — Periods per session.** Recommended default: **48** (e.g. 30-min
  letters over a 24h session, classic market-profile granularity), as the
  const TPO_PERIODS_PER_SESSION. Alternatives: 24, 96, or "session = 1
  timeframe bar of a slower timeframe instance" (consume a second TF seam
  instead of a counter — needs device-level wiring decision).
- **T3 — History ring depth.** Recommended default: **16 sessions**.
  Alternatives: 8, 64.
- **T4 — Time-at-price accumulators.** Recommended default: **omit** (pure
  letter counting; keeps slot cost at 4 regs). Alternative: include
  TPO_LVL_TIME_i + TPO_PREV_TAI (stub's TAI-delta idea, done per-level and
  via DOM_LAST_FEED_TIME_REG instead of the FIFO reach-through).
- **T5 — Touch definition.** Recommended default: **both best bid AND best
  ask touch their own price levels** (dual-side, consistent with candle's
  dual OHLC §B decision). Alternative: mid-price only (single touch/tick).
