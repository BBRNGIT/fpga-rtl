# Candle Indicator — Flip-Flop-Level Architecture

**Status:** Specification complete (comb_nodes + wiring specified). Ready for emitter-first build.

**Authority:**
- `DECISIONS.md` §B — dual bid/ask OHLC register names, CANDLE_HIST layout, data source (authoritative).
- `.hft_staging/INDICATOR_ARCHITECTURE_TEMPLATE.md` §"Template: Candle Indicator" — combinational-logic reference.
- `tools/generators/candle.yaml` — register spec (dff_nodes, history_ring, seam_nodes).

**Gate primitives used (and ONLY these):**
`cell_addsub(a,b,sub)` · `cell_mux(a,b,sel)` · `cell_cmp_lt(a,b)` / `cmp_lt(a,b)` · `cell_eqmask(a,b)` · `cell_gate(val,en)`.
No native `+ - * /`, no `if/else`, no `?:`, no loops over bits. Every branch is a `cell_mux`; every compare is `cmp_lt` or `cell_eqmask`; every add/sub is `cell_addsub`.

> **Primitive note.** `cmp_lt(a,b) → 1 iff a < b` (unsigned) is the carry-chain comparator emitted by `gennet.py` (see `.hft_staging/timeframe/gennet.py::emit_cmp_lt`); `cell_cmp_lt` is the template's abstract name for the same cell. `cell_addsub(a,b,1)` computes `a − b` via two's complement (`a + ~b + 1`), never a native `−`.

---

## 1. Input Interface

All inputs are read in the CLOCK_PHASE_READ phase as `const` locals. Candle samples published windows only — it never reads another module's private registers (module barrier).

### From DOM (`.hft_staging/dom/` published window)
```
DOM_BID_PRICE   u64   Best bid price (highest bid level).      → bid OHLC comparators + open latch
DOM_ASK_PRICE   u64   Best ask price (lowest ask level).       → ask OHLC comparators + open latch
DOM_BID_QTY     u64   Bid quantity at indexed price level.     → intrabar qty-delta accumulation
DOM_ASK_QTY     u64   Ask quantity at indexed price level.     → intrabar qty-delta accumulation
```

### From Timeframe (`.hft_staging/timeframe/` published window)
```
TF_BAR_SEQ_REG  u64   Bar sequence; increments on bar close.   → bar-boundary detection
```

### From the time base (in-domain, via the published TAI window)
```
TAI value       u64   Current timestamp (MAC/pipeline-domain TAI, already CDC-resolved upstream).
                      → latched into CANDLE_COMP_TAI on bar boundary (bar-open timestamp).
```

### Quote stream (implicit, via FIFO_RX → DOM)
A "tick" is implied by a change in the published DOM price. Candle does **not** read FIFO_RX raw; it detects bid/ask ticks by comparing the current DOM price against the previous-cycle DOM price held in `CANDLE_BID_CLOSE` / `CANDLE_ASK_CLOSE` (the last-latched price). No `is_buy`/`is_sell`/trade-side ghost fields are ever read (DECISIONS §A/§B operand law).

---

## 2. Register State

### Live (`CANDLE_*`) — updated every tick during the bar
```
CANDLE_BID_OPEN          First bid price of bar
CANDLE_BID_HIGH          Running max bid price
CANDLE_BID_LOW           Running min bid price
CANDLE_BID_CLOSE         Most recent bid price (also = previous-bid for tick detection)

CANDLE_ASK_OPEN          First ask price of bar
CANDLE_ASK_HIGH          Running max ask price
CANDLE_ASK_LOW           Running min ask price
CANDLE_ASK_CLOSE         Most recent ask price (also = previous-ask for tick detection)

CANDLE_VOLUME_BID        Cumulative bid ticks this bar
CANDLE_VOLUME_ASK        Cumulative ask ticks this bar

CANDLE_TRUE_RANGE_BID    bid_high − bid_low
CANDLE_TRUE_RANGE_ASK    ask_high − ask_low

CANDLE_INTRABAR_QTY_DELTA  Cumulative (ask_qty − bid_qty) over the bar

CANDLE_OPEN_SET          Flag: first tick of bar processed (1) / fresh bar (0)
CANDLE_LAST_TF_SEQ       Last TF_BAR_SEQ seen (bar-boundary edge detect)
CANDLE_BAR_SEQ           Bar sequence counter (candle-local)
CANDLE_BAR_PARITY        Virtual-reset parity tag (bit 63)
CANDLE_PREV_TRADE_CNT    Last trade count (reserved for delta calc)

CANDLE_MID               Convenience: (bid_high + ask_low) >> 1 (non-blocking, read-only)
```

### Completed (`CANDLE_COMP_*`) — snapshot written on bar boundary, held for the next bar
```
CANDLE_COMP_BID_OPEN   CANDLE_COMP_BID_HIGH   CANDLE_COMP_BID_LOW   CANDLE_COMP_BID_CLOSE
CANDLE_COMP_ASK_OPEN   CANDLE_COMP_ASK_HIGH   CANDLE_COMP_ASK_LOW   CANDLE_COMP_ASK_CLOSE
CANDLE_COMP_VOLUME_BID CANDLE_COMP_VOLUME_ASK
CANDLE_COMP_TRUE_RANGE_BID  CANDLE_COMP_TRUE_RANGE_ASK
CANDLE_COMP_INTRABAR_QTY_DELTA
CANDLE_COMP_TAI        CANDLE_COMP_BAR_SEQ
```

### History Ring — 256 slots × 16 fields (DECISIONS §B layout, window `0x2200000`)
```
0 BID_OPEN   1 BID_HIGH   2 BID_LOW    3 BID_CLOSE
4 ASK_OPEN   5 ASK_HIGH   6 ASK_LOW    7 ASK_CLOSE
8 VOLUME_BID 9 VOLUME_ASK 10 TRUE_RANGE_BID 11 TRUE_RANGE_ASK
12 INTRABAR_QTY_DELTA  13 TAI  14 BAR_SEQ  15 PARITY
```
`CANDLE_HIST_MASK = depth − 1 = 0xFF` (slot index = `CANDLE_BAR_SEQ & CANDLE_HIST_MASK`).

---

## 3. Combinational Logic (comb_nodes — explicit gate primitives)

Each comb_node names its inputs, its gate expression (ONLY cell primitives), and its output (the `d` input to the corresponding `cell_dff`). Every live register has exactly one update rule.

### 3.1 Tick-detection signals (shared, computed first)

```
BID_TICK:
  inputs:  DOM_BID_PRICE, CANDLE_BID_CLOSE
  logic:   bid_changed = cell_eqmask(DOM_BID_PRICE, CANDLE_BID_CLOSE) ^ 1ULL
  output:  bid_tick   (1 iff price differs from last latched bid)
  comment: cell_eqmask = 1 when equal; XOR 1 inverts to "changed". No native !=.

ASK_TICK:
  inputs:  DOM_ASK_PRICE, CANDLE_ASK_CLOSE
  logic:   ask_changed = cell_eqmask(DOM_ASK_PRICE, CANDLE_ASK_CLOSE) ^ 1ULL
  output:  ask_tick
```

### 3.2 Bid-side OHLC

```
CANDLE_BID_OPEN_UPDATE:
  inputs:  CANDLE_OPEN_SET, DOM_BID_PRICE, CANDLE_BID_OPEN
  logic:   cell_mux(DOM_BID_PRICE, CANDLE_BID_OPEN, CANDLE_OPEN_SET)
  output:  new_bid_open
  comment: sel=CANDLE_OPEN_SET → 0 = fresh bar, latch DOM_BID_PRICE (mux arg a);
           1 = already open, hold CANDLE_BID_OPEN (mux arg b). cell_mux(a,b,sel)=sel?b:a.

CANDLE_BID_HIGH_UPDATE:
  inputs:  CANDLE_BID_HIGH, DOM_BID_PRICE, CANDLE_OPEN_SET
  logic:   is_new_high = cmp_lt(CANDLE_BID_HIGH, DOM_BID_PRICE)
           cmp_sel     = cell_or(is_new_high, CANDLE_OPEN_SET ^ 1ULL)   /* force-take on fresh bar */
           cell_mux(CANDLE_BID_HIGH, DOM_BID_PRICE, cmp_sel)
  output:  new_bid_high
  comment: Running max. On the bar's first tick (OPEN_SET=0) the stale high is
           overridden so high seeds from the first price, not a carried value.

CANDLE_BID_LOW_UPDATE:
  inputs:  CANDLE_BID_LOW, DOM_BID_PRICE, CANDLE_OPEN_SET
  logic:   is_new_low = cmp_lt(DOM_BID_PRICE, CANDLE_BID_LOW)
           cmp_sel    = cell_or(is_new_low, CANDLE_OPEN_SET ^ 1ULL)
           cell_mux(CANDLE_BID_LOW, DOM_BID_PRICE, cmp_sel)
  output:  new_bid_low
  comment: Running min, with fresh-bar seed override (same pattern as high).

CANDLE_BID_CLOSE_UPDATE:
  inputs:  DOM_BID_PRICE
  logic:   cell_buf(DOM_BID_PRICE)      /* passthrough — always latch most recent */
  output:  new_bid_close
```

### 3.3 Ask-side OHLC (symmetric to bid)

```
CANDLE_ASK_OPEN_UPDATE:
  logic:   cell_mux(DOM_ASK_PRICE, CANDLE_ASK_OPEN, CANDLE_OPEN_SET)
  output:  new_ask_open

CANDLE_ASK_HIGH_UPDATE:
  logic:   is_new_high = cmp_lt(CANDLE_ASK_HIGH, DOM_ASK_PRICE)
           cmp_sel     = cell_or(is_new_high, CANDLE_OPEN_SET ^ 1ULL)
           cell_mux(CANDLE_ASK_HIGH, DOM_ASK_PRICE, cmp_sel)
  output:  new_ask_high

CANDLE_ASK_LOW_UPDATE:
  logic:   is_new_low = cmp_lt(DOM_ASK_PRICE, CANDLE_ASK_LOW)
           cmp_sel    = cell_or(is_new_low, CANDLE_OPEN_SET ^ 1ULL)
           cell_mux(CANDLE_ASK_LOW, DOM_ASK_PRICE, cmp_sel)
  output:  new_ask_low

CANDLE_ASK_CLOSE_UPDATE:
  logic:   cell_buf(DOM_ASK_PRICE)
  output:  new_ask_close
```

### 3.4 Volume accumulation (gated increment)

```
CANDLE_VOLUME_BID_UPDATE:
  inputs:  CANDLE_VOLUME_BID, bid_tick (from BID_TICK)
  logic:   inc     = cell_gate(1ULL, bid_tick)                  /* 1 on bid tick, else 0 */
           cell_addsub(CANDLE_VOLUME_BID, inc, 0ULL)            /* add, sub=0 */
  output:  new_volume_bid
  comment: cell_gate masks the increment to 0 when no bid tick → branchless conditional add.

CANDLE_VOLUME_ASK_UPDATE:
  inputs:  CANDLE_VOLUME_ASK, ask_tick (from ASK_TICK)
  logic:   inc     = cell_gate(1ULL, ask_tick)
           cell_addsub(CANDLE_VOLUME_ASK, inc, 0ULL)
  output:  new_volume_ask
```

### 3.5 True Range (high − low, after H/L updated this tick)

```
CANDLE_TRUE_RANGE_BID_UPDATE:
  inputs:  new_bid_high, new_bid_low
  logic:   cell_addsub(new_bid_high, new_bid_low, 1ULL)         /* sub=1 → high − low (2's comp) */
  output:  new_tr_bid
  comment: Consumes the just-computed new_bid_high/new_bid_low, so TR tracks the
           same-tick range. No native subtraction.

CANDLE_TRUE_RANGE_ASK_UPDATE:
  inputs:  new_ask_high, new_ask_low
  logic:   cell_addsub(new_ask_high, new_ask_low, 1ULL)
  output:  new_tr_ask
```

### 3.6 Intrabar quantity delta (cumulative ask_qty − bid_qty)

```
CANDLE_INTRABAR_QTY_DELTA_UPDATE:
  inputs:  CANDLE_INTRABAR_QTY_DELTA, DOM_ASK_QTY, DOM_BID_QTY
  logic:   quote_delta = cell_addsub(DOM_ASK_QTY, DOM_BID_QTY, 1ULL)            /* ask − bid */
           cell_addsub(CANDLE_INTRABAR_QTY_DELTA, quote_delta, 0ULL)           /* accumulate */
  output:  new_intrabar_delta
  comment: Two cell_addsub in series (one subtract, one add). DECISIONS §A:
           operands are quote quantities only; no DOM_BUY_VOL/DOM_SELL_VOL.
```

### 3.7 Convenience mid (non-blocking)

```
CANDLE_MID_UPDATE:
  inputs:  new_bid_high, new_ask_low
  logic:   cell_addsub(new_bid_high, new_ask_low, 0ULL) >> 1ULL   /* sum then >>1 = /2 */
  output:  new_mid
  comment: Shift-by-1 is the structural /2 (no native division, no DSP needed for a
           power-of-two divisor). Read-only convenience; nothing downstream blocks on it.
```

### 3.8 Bar-boundary detection

```
BAR_BOUNDARY_DETECTED:
  inputs:  CANDLE_LAST_TF_SEQ, TF_BAR_SEQ_REG
  logic:   bar_boundary = cell_eqmask(CANDLE_LAST_TF_SEQ, TF_BAR_SEQ_REG) ^ 1ULL
  output:  bar_boundary   (1 iff timeframe seq changed since last cycle → bar closed)
  comment: eqmask=1 when unchanged; XOR 1 → 1 on change. Single-cycle pulse: the
           same tick updates CANDLE_LAST_TF_SEQ ← TF_BAR_SEQ_REG (passthrough latch).

CANDLE_LAST_TF_SEQ_UPDATE:
  inputs:  TF_BAR_SEQ_REG
  logic:   cell_buf(TF_BAR_SEQ_REG)
  output:  new_last_tf_seq
```

### 3.9 Bar-control state (driven by bar_boundary)

```
CANDLE_OPEN_SET_UPDATE:
  inputs:  CANDLE_OPEN_SET, bar_boundary
  logic:   /* on boundary → 0 (fresh, force next tick to seed open); else → 1 (open) */
           cell_mux(1ULL, 0ULL, bar_boundary)
  output:  new_open_set
  comment: After a boundary the next tick sees OPEN_SET=0 and latches OPEN/HIGH/LOW
           from the first price. Steady state holds 1.

CANDLE_BAR_SEQ_UPDATE:
  inputs:  CANDLE_BAR_SEQ, bar_boundary
  logic:   inc_seq = cell_addsub(CANDLE_BAR_SEQ, bar_boundary, 0ULL)   /* +1 only on boundary */
  output:  new_bar_seq
  comment: bar_boundary is 0/1, so this adds 1 exactly on a boundary, else holds.

CANDLE_BAR_PARITY_UPDATE:
  inputs:  CANDLE_BAR_PARITY, bar_boundary
  logic:   flip   = cell_gate(1ULL, bar_boundary)
           toggled = cell_addsub(CANDLE_BAR_PARITY, flip, 0ULL)
           new_parity = cell_and(toggled, 1ULL)                        /* keep low bit */
  output:  new_bar_parity
  comment: Toggles the parity tag on each boundary (virtual-reset of the oldest ring slot).
```

### Reset-on-boundary for accumulators (volume + delta)

The accumulators must clear at the new bar. Done branchlessly by gating the *carried* value with `bar_boundary ^ 1` (hold when not a boundary, zero when a boundary). This composes with §3.4 / §3.6:

```
VOLUME / DELTA carry-with-reset (applies to BID, ASK, INTRABAR_QTY_DELTA):
  base   = cell_gate(CANDLE_<ACC>, bar_boundary ^ 1ULL)   /* 0 at boundary, hold otherwise */
  then the §3.4 / §3.6 add is applied to `base` instead of the raw register.
  e.g. new_volume_bid = cell_addsub( cell_gate(CANDLE_VOLUME_BID, bar_boundary ^ 1ULL),
                                     cell_gate(1ULL, bid_tick), 0ULL )
  comment: On a boundary the accumulator starts from 0, then takes this tick's increment.
           No memset, no if — a synchronous gated clear (CLAUDE.md reset-on-edge model).
```

---

## 4. Wiring (Signal Flow)

```
READ phase (sample published windows into const locals):
  DOM_BID_PRICE, DOM_ASK_PRICE, DOM_BID_QTY, DOM_ASK_QTY   ← dom window
  TF_BAR_SEQ_REG                                           ← timeframe window
  TAI value                                                ← time window
  CANDLE_* live registers (own state)                      ← REG_R

COMPUTE phase (pure gate algebra, no REG_R/REG_W):
  Step A  tick detect:    bid_tick, ask_tick           (3.1)
  Step B  boundary:       bar_boundary, new_last_tf_seq (3.8)
  Step C  OHLC:           new_bid_{open,high,low,close} (3.2)
                          new_ask_{open,high,low,close} (3.3)
  Step D  ranges:         new_tr_bid, new_tr_ask        (3.5)  [consume Step C highs/lows]
  Step E  accumulators:   new_volume_bid/ask            (3.4 + reset gate)
                          new_intrabar_delta            (3.6 + reset gate)
  Step F  convenience:    new_mid                        (3.7)  [consume Step C]
  Step G  control:        new_open_set, new_bar_seq, new_bar_parity (3.9)
  Step H  snapshot mux:   for every COMP field,
                            new_comp = cell_mux(CANDLE_COMP_X, <live value>, bar_boundary)
                          (hold prior COMP when not a boundary; latch live on boundary)
                          new_comp_tai = cell_mux(CANDLE_COMP_TAI, TAI_value, bar_boundary)
  Step I  ring address:   slot = new_bar_seq & CANDLE_HIST_MASK   (index math only)

WRITE phase (write-only; values from COMPUTE locals):
  CANDLE_BID_*  ← new_bid_*          CANDLE_ASK_*  ← new_ask_*
  CANDLE_VOLUME_BID/ASK ← new_volume_*
  CANDLE_TRUE_RANGE_BID/ASK ← new_tr_*
  CANDLE_INTRABAR_QTY_DELTA ← new_intrabar_delta
  CANDLE_MID ← new_mid
  CANDLE_OPEN_SET ← new_open_set     CANDLE_LAST_TF_SEQ ← new_last_tf_seq
  CANDLE_BAR_SEQ ← new_bar_seq       CANDLE_BAR_PARITY ← new_bar_parity
  CANDLE_COMP_* ← new_comp_*  (only changes on boundary via Step H mux)
  CANDLE_HIST(slot, field) ← gated write (see §4.1)
```

### 4.1 History-ring write logic (snapshot CANDLE_* → CANDLE_COMP_* → ring)

On a bar boundary the just-frozen `CANDLE_COMP_*` snapshot is committed to ring slot `slot = new_bar_seq & CANDLE_HIST_MASK`. The write is gated so non-boundary ticks leave the ring untouched (single-writer per slot per bar):

```
For each ring field f mapped to live value live_f:
  HIST_WRITE(f):
    inputs:  CANDLE_HIST(slot, f), new_comp_f (from Step H), bar_boundary
    logic:   cell_mux(CANDLE_HIST(slot, f), new_comp_f, bar_boundary)
    output:  ring[slot][f] = hold prior content off-boundary, write snapshot on boundary

  PARITY field (15):
    ring[slot][15] = cell_mux(CANDLE_HIST(slot,15), new_bar_parity, bar_boundary)
    comment: parity tag marks the slot's bar generation (virtual-reset of stale slots
             without a memset — readers compare slot parity to expected, §Correct Patterns).
```

The 16 ring fields map: BID_O/H/L/C ← new_bid_*; ASK_O/H/L/C ← new_ask_*; VOLUME_BID/ASK ← new_volume_*; TRUE_RANGE_BID/ASK ← new_tr_*; INTRABAR_QTY_DELTA ← new_intrabar_delta; TAI ← TAI value; BAR_SEQ ← new_bar_seq; PARITY ← new_bar_parity.

---

## 5. Output Interface (seam_nodes)

Downstream modules (fractal, CBR, OHLCV dome, custom indicators) sample these published relay windows — they never read candle's private registers. Per-module `ohlc_source = "bid" | "ask" | "custom"` config (DECISIONS §B) selects which series a consumer reads.

```
CANDLE_BID_OHLC_OUT
  lanes:   CANDLE_BID_OPEN, CANDLE_BID_HIGH, CANDLE_BID_LOW, CANDLE_BID_CLOSE
  consumers: fractal (h2/l2/c0/c1), custom indicators

CANDLE_ASK_OHLC_OUT
  lanes:   CANDLE_ASK_OPEN, CANDLE_ASK_HIGH, CANDLE_ASK_LOW, CANDLE_ASK_CLOSE
  consumers: CBR (configurable), custom indicators

CANDLE_VOLUME_OUT
  lanes:   CANDLE_VOLUME_BID, CANDLE_VOLUME_ASK
  consumers: CBR (volume ratios)

CANDLE_TRUE_RANGE_OUT
  lanes:   CANDLE_TRUE_RANGE_BID, CANDLE_TRUE_RANGE_ASK
  consumers: ATR-like calculations

CANDLE_DELTA_OUT
  lane:    CANDLE_INTRABAR_QTY_DELTA
  consumers: imbalance-driven signals
```

History-ring slots (`CANDLE_HIST(slot, field)`) are additionally readable for N-bars-back lookback (slot = `(CANDLE_BAR_SEQ − N) & CANDLE_HIST_MASK`, parity-checked).

---

## Validation Checklist

- [x] **Every live register has an explicit update rule.** BID O/H/L/C, ASK O/H/L/C, VOLUME_BID/ASK, TRUE_RANGE_BID/ASK, INTRABAR_QTY_DELTA, OPEN_SET, LAST_TF_SEQ, BAR_SEQ, BAR_PARITY, MID — each has a comb_node in §3. COMP_* and HIST fields driven by boundary-gated muxes (§4 Step H / §4.1).
- [x] **Every comb_node uses ONLY gate cell names.** `cell_addsub`, `cell_mux`, `cell_cmp_lt`/`cmp_lt`, `cell_eqmask`, `cell_gate`, `cell_or`, `cell_and`, `cell_buf`. No native `+ − * /`, no `==`/`!=`, no `?:`, no `if`, no loops over bits.
- [x] **Wiring is complete:** inputs (§1) → READ → COMPUTE Steps A–I (§4) → WRITE → outputs (§5). True range and mid consume same-tick OHLC outputs; accumulators carry-with-reset gated on `bar_boundary`.
- [x] **Bar boundary triggers snapshots:** `bar_boundary` (§3.8) drives the COMP mux (Step H) and the ring write (§4.1); seq/parity advance (§3.9); accumulators reset via gated carry.
- [x] **History-ring write specified:** boundary-gated `cell_mux` per field at `slot = bar_seq & CANDLE_HIST_MASK`, parity tag for virtual reset (§4.1).
- [x] **Module barrier honored:** reads only DOM/timeframe/TAI published windows; ghost fields (`is_buy`, `is_sell`, `DOM_BUY_VOL`, `DOM_SELL_VOL`) never referenced (DECISIONS §A/§B).
