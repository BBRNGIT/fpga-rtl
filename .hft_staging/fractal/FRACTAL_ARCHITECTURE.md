# Fractal Indicator — Flip-Flop Architecture (WAVE 2)

**Component:** `fractal`
**Chip owner:** PIPELINE_FPGA (250 MHz)
**Pattern:** 5-bar Bill Williams fractal detector.
**Reference:** `hft_pipeline/indicators/fractal/fractal.c` (lines 24–88).

> Spec authored per `.hft_staging/INDICATOR_ARCHITECTURE_TEMPLATE.md`. Every
> state-updating register has a corresponding `comb_node`; every `comb_node` is a
> single gate-level structural cell call (no native `+`/`-`/`*`, no `if`/`?:`).
> This is what makes gate stage 2d (cell_count > 0) pass with real logic, not a stub.

---

## Overview

A Bill Williams fractal is a 5-bar reversal pattern. Looking at five consecutive
completed bars (seq-5 … seq-1), the **middle bar** (seq-3, the `cs2` slot) is the
pivot:

- **UP fractal:** the middle bar's HIGH is strictly greater than the highs of the
  two bars on each side: `h2 > h0 ∧ h2 > h1 ∧ h2 > h3 ∧ h2 > h4`.
- **DN fractal:** the middle bar's LOW is strictly less than the lows of the two
  bars on each side: `l2 < l0 ∧ l2 < l1 ∧ l2 < l3 ∧ l2 < l4`.

Both are gated by `seq >= 5` (need five completed bars before any pattern exists).

On detection the indicator latches the pivot price into a high-water scalar
(`IND_FRAC_UP_PRICE_REG` / `IND_FRAC_DN_PRICE_REG`) and commits a per-bar record
into a 256-slot history ring. When no fractal is detected at a bar, the history
slot receives the sentinel `0xFFFFFFFFFFFFFFFF` (renders as `---.----`).

---

## 1. Input Interface (cross_module_inputs / config_nodes)

Fractal samples **published windows only** (module barrier). It never reads
another module's private registers.

```
From Timeframe:
  — TF_BAR_SEQ_REG   : bar sequence counter (completed-bar count); the seq>=5
                       guard and the five ring indices are derived from it.

From Candle (its published history ring):
  — CANDLE_HIST(slot, CANDLE_HIST_HIGH) : per-bar HIGH, indexed by ring slot
  — CANDLE_HIST(slot, CANDLE_HIST_LOW)  : per-bar LOW,  indexed by ring slot
```

The candle history ring is a power-of-two ring of depth `CANDLE_HIST_DEPTH`
(`CANDLE_HIST_MASK = depth - 1`). The five slots analysed each tick are:

```
cs0 = (seq - 1) & CANDLE_HIST_MASK      seq-1  (most recent completed bar)
cs1 = (seq - 2) & CANDLE_HIST_MASK      seq-2
cs2 = (seq - 3) & CANDLE_HIST_MASK      seq-3  (MIDDLE bar — the pivot)
cs3 = (seq - 4) & CANDLE_HIST_MASK      seq-4
cs4 = (seq - 5) & CANDLE_HIST_MASK      seq-5  (oldest of the five)
```

These slots are presented to fractal as already-resolved register lanes
`H0..H4` and `L0..L4` (the candle producer publishes the indexed values; fractal
samples them — it does not index into another module's private array). The ring
indices `cs0..cs4` are computed structurally from `seq` so the model stays
faithful (subtraction via `cell_addsub`, mask via `&`).

---

## 2. Register State (dff_nodes + history table)

**Scalar high-water marks (2 dff registers):**
```
IND_FRAC_UP_PRICE_REG   — high-water mark of detected UP fractal pivot highs.
                          Updates to h2 on an UP match, else latches its value.
IND_FRAC_DN_PRICE_REG   — high-water mark of detected DN fractal pivot lows.
                          Updates to l2 on a DN match, else latches its value.
```

**History ring (2 fields × 256 slots = 512 register lanes):**
```
IND_FRAC_HIST[256][2]
  field FRAC_HIST_UP : UP pivot high at this bar, or sentinel if no UP fractal.
  field FRAC_HIST_DN : DN pivot low  at this bar, or sentinel if no DN fractal.
```
Depth 256 is a power of two; `FRAC_HIST_MASK = 255`. The slot written each tick
is the middle-bar slot `cs2 & FRAC_HIST_MASK` (the fractal is confirmed on the
pivot bar). Sentinel = `0xFFFFFFFFFFFFFFFF`.

---

## 3. Combinational Logic (comb_nodes — gate primitives only)

All operations below are single structural cell calls. Cell vocabulary:
`cell_addsub`, `cmp_lt` (emitted gate comparator), `cell_and`, `cell_mux`,
`cell_eqmask`. No native `+`/`-`/`*`, no `if`/`?:`.

### 3.1 Pivot history-write slot (structural subtract + mask)

Fractal owns exactly **one** ring index — the slot into its OWN history ring
where the pivot record is committed:

```
CS2 = addsub(seq, 3, sub=1) & FRAC_HIST_MASK      ; seq-3 (pivot / write slot)
```

The read-side slots that resolve the five neighbour bars
(`cs0=seq-1, cs1=seq-2, cs3=seq-4, cs4=seq-5`) belong to the **candle seam**, not
to fractal. The candle producer indexes its own history ring and publishes the
resolved `H0..H4` / `L0..L4` lanes; fractal samples those lanes (module barrier).
Recomputing those indices inside the fractal device would be dead logic with no
consumer (and would trip `-Werror -Wunused-variable`). Fractal therefore derives
only `cs2`, which it actually consumes (the WRITE phase addresses
`IND_FRAC_HIST[cs2]`). `H0..H4`, `L0..L4` are sampled register reads.

### 3.2 seq >= 5 guard

```
SEQ_LT5 = cmp_lt(seq, 5)            ; 1 iff seq < 5
SEQ_GE5 = SEQ_LT5 ^ 1              ; 1 iff seq >= 5   (boolean invert)
```

### 3.3 UP fractal predicate (h2 strictly greater than 4 neighbours)

`a > b` is expressed as `cmp_lt(b, a)` (strict greater-than via the gate
comparator with operands swapped).

```
UP_GT0 = cmp_lt(H0, H2)            ; h2 > h0
UP_GT1 = cmp_lt(H1, H2)            ; h2 > h1
UP_GT3 = cmp_lt(H3, H2)            ; h2 > h3
UP_GT4 = cmp_lt(H4, H2)            ; h2 > h4

UP_AND_A = and(UP_GT0, UP_GT1)
UP_AND_B = and(UP_GT3, UP_GT4)
UP_AND_C = and(UP_AND_A, UP_AND_B)
IS_UP    = and(UP_AND_C, SEQ_GE5)  ; final UP detection (bit0)
```

### 3.4 DN fractal predicate (l2 strictly less than 4 neighbours)

`a < b` is `cmp_lt(a, b)` directly.

```
DN_LT0 = cmp_lt(L2, L0)            ; l2 < l0
DN_LT1 = cmp_lt(L2, L1)            ; l2 < l1
DN_LT3 = cmp_lt(L2, L3)            ; l2 < l3
DN_LT4 = cmp_lt(L2, L4)            ; l2 < l4

DN_AND_A = and(DN_LT0, DN_LT1)
DN_AND_B = and(DN_LT3, DN_LT4)
DN_AND_C = and(DN_AND_A, DN_AND_B)
IS_DN    = and(DN_AND_C, SEQ_GE5)  ; final DN detection (bit0)
```

### 3.5 Scalar high-water updates (latch pivot on match, else hold)

`cell_mux(a, b, sel) = sel ? b : a`.

```
IND_FRAC_UP_PRICE_REG_UPDATE = mux(IND_FRAC_UP_PRICE_REG, H2, IS_UP)
    ; IS_UP -> latch h2, else hold prior high-water UP price.
IND_FRAC_DN_PRICE_REG_UPDATE = mux(IND_FRAC_DN_PRICE_REG, L2, IS_DN)
    ; IS_DN -> latch l2, else hold prior high-water DN price.
```

### 3.6 History-slot records (pivot price on match, else sentinel)

```
NEXT_HU = mux(FRAC_SENTINEL, H2, IS_UP)    ; IS_UP -> h2, else sentinel
NEXT_HD = mux(FRAC_SENTINEL, L2, IS_DN)    ; IS_DN -> l2, else sentinel
```
`FRAC_SENTINEL` is a const lane = `0xFFFFFFFFFFFFFFFF`. `NEXT_HU` writes
`IND_FRAC_HIST(cs2 & FRAC_HIST_MASK, FRAC_HIST_UP)`; `NEXT_HD` writes the DN
field of the same slot.

---

## 4. Wiring (signal flow)

```
TF_BAR_SEQ_REG ─┬─> CS0..CS4 (addsub + mask)         -> H0..H4, L0..L4 lane reads
                └─> SEQ_LT5 (cmp_lt seq,5) -> SEQ_GE5 (^1) ─┐
                                                            │
H0..H4 ─> UP_GT0/1/3/4 (cmp_lt swapped) -> UP_AND_* -> IS_UP <┤
L0..L4 ─> DN_LT0/1/3/4 (cmp_lt)         -> DN_AND_* -> IS_DN <┘

IS_UP ─> mux(prev_up, H2)  -> IND_FRAC_UP_PRICE_REG   (scalar high-water)
IS_DN ─> mux(prev_dn, L2)  -> IND_FRAC_DN_PRICE_REG

IS_UP ─> mux(sentinel, H2) -> NEXT_HU -> IND_FRAC_HIST[cs2].UP
IS_DN ─> mux(sentinel, L2) -> NEXT_HD -> IND_FRAC_HIST[cs2].DN
```

READ→COMPUTE→WRITE: all candle lanes + seq + prior scalars are pre-read in READ;
all predicates and muxes computed in COMPUTE via cells; the two scalars and the
two history fields written in WRITE (no read-after-write).

---

## 5. Output Interface (seam_nodes)

```
IND_FRAC_UP_PRICE_REG  — relayed to strategy/display: most recent UP fractal high.
IND_FRAC_DN_PRICE_REG  — relayed to strategy/display: most recent DN fractal low.
```
Downstream (strategy, display) samples these published lanes; fractal is the
single writer. The history ring is readable for back-N fractal queries
(`IND_FRAC_HIST(slot, field)`), sentinel-tagged where no fractal occurred.

---

## 6. Single-writer / module-barrier contract

- **Writes (owned):** `IND_FRAC_UP_PRICE_REG`, `IND_FRAC_DN_PRICE_REG`, and the
  512 `IND_FRAC_HIST` lanes. Nothing else writes these.
- **Reads (sampled windows):** `TF_BAR_SEQ_REG` (timeframe), candle HIGH/LOW
  history lanes. No private cross-module reads.
- **Clock domain:** PIPELINE_FPGA (250 MHz), single domain — no CDC/SLR seam.

---

## 7. Open decisions (flagged, not silently chosen)

1. **Candle history depth vs fractal history depth.** Candle uses
   `CANDLE_HIST_DEPTH` (256 in `hft_pipeline`); fractal's own ring is 256. The
   `cs2 & FRAC_HIST_MASK` slot mapping assumes both depths align; if candle's
   published ring depth differs, the fractal slot index must mask with the
   candle depth on read and the fractal depth on write (already separated:
   `CANDLE_HIST_MASK` for the read index, `FRAC_HIST_MASK` for the write slot).
2. **bid vs ask HIGH/LOW.** The reference reads a single HIGH/LOW per bar.
   `hft_pipeline` candle exposes dual bid/ask OHLC (DECISIONS §B). This spec
   consumes candle's published HIGH/LOW lanes; which side (bid/ask/combined)
   those lanes carry is a candle-seam decision, not a fractal decision —
   fractal is agnostic and reads whatever HIGH/LOW the candle seam publishes.
