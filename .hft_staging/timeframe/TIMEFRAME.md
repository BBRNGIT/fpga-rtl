# TIMEFRAME — Bar-boundary clock authority (pure combinational rollover)

`timeframe` is the reference bar clock (SPEC_REGISTERS.md §2). It is a **guide, not a master**: each
downstream bar module carries its own multiple of the base period and closes its own bars by watching
`TF_BAR_SEQ_REG` against its private `*_LAST_TF_SEQ_REG`. This module's only job is the base rollover:
detect when the elapsed time since the current bar opened reaches the configured period, and on that
boundary advance the bar sequence, pulse a closed strobe, and re-anchor the bar start.

```
  TIME_TAI_NS  ──►┐
                  │   elapsed = TAI - BAR_START          (cell_addsub, sub)
  TF_PERIOD_NS ──►┤   rollover = elapsed >= PERIOD       (cmp_ge: ~cmp_lt)
                  │
                  ▼
        ┌──────────────────────────────────────────────┐
        │  rollover ? :                                 │
        │    BAR_SEQ      <= BAR_SEQ + rollover          │ (increment on boundary)
        │    BAR_CLOSED   <= rollover                    │ (0→1 one-tick pulse)
        │    BAR_START    <= rollover ? TAI : BAR_START  │ (re-anchor on boundary)
        └──────────────────────────────────────────────┘
                  │
                  ▼  TF_BAR_SEQ / TF_BAR_CLOSED / TF_BAR_START_TAI
                     (read by candle, footprint, tpo, fractal, cbr, grid)
```

All selection is mask algebra (`cell_mux` / `cell_gate`); the subtract and increment are the
structural ripple-carry `cell_addsub` (no native `+`/`-`); the comparator is the gate-netlist
`cmp_lt` carry chain (no native `>=`). Zero `if`/`?:`/`switch`/`%` in the generated tick.

## Module barrier (inputs are presented on this device's OWN lanes)

The spec lists the inputs as `TIME_TAI_NS_REG` and `TF_PERIOD_NS_REG`. By the single-writer /
module-barrier law, `timeframe` does **not** reach into the time_source or operator registers. The
sampled TAI value is presented on this device's own input lane `TF_TAI_IN`, and the period on its own
config lane `TF_PERIOD_NS` (operator-written before the first tick). The starter wires the producer's
published value onto these lanes at integration time — exactly as `tai_cdc` carries the sampled `tai`
value on `TAI_IN`. The device tick only ever reads its own window.

## Register Window (base 0x2000000)

| Offset | Name           | Width | Type           | Purpose                                                         |
|--------|----------------|-------|----------------|-----------------------------------------------------------------|
| +0x00  | TF_POWER       | 1     | config (power) | set once; the rollover detect runs while bit0 = 1               |
| +0x08  | TF_RUN_UNTIL   | 64    | config         | configured self-run tick budget (set once by starter)           |
| +0x10  | TF_TAI_IN      | 64    | config (input) | sampled `TIME_TAI_NS_REG` value presented on this device's lane |
| +0x18  | TF_PERIOD_NS   | 64    | config (input) | bar period in ns (= operator `REG_TF_CONFIG`); written once     |
| +0x20  | TF_TICKS       | 64    | dff (counter)  | self-run tick counter (run-loop bookkeeping; bounds the run)    |
| +0x28  | TF_BAR_SEQ     | 64    | dff            | bar sequence; += 1 when elapsed ≥ period (= `REG_TF_COUNTER`)    |
| +0x30  | TF_BAR_CLOSED  | 64    | dff (bitfield) | 0→1 one-tick pulse at a bar boundary (= `TIMEFRAME_DIRTY_BIT`)   |
| +0x38  | TF_BAR_START   | 64    | dff            | TAI at the current bar open (= `TIMEFRAME_CURRENT_CANDLE_OPEN`)  |

Window: 0x2000000 – 0x2000040 (8 registers, 64 bytes). Spec register-name mapping:
`TF_PERIOD_NS` = `TF_PERIOD_NS_REG`, `TF_BAR_SEQ` = `TF_BAR_SEQ_REG`,
`TF_BAR_CLOSED` = `TF_BAR_CLOSED_REG`, `TF_BAR_START` = `TF_BAR_START_TAI_REG`,
`TF_TAI_IN` ← `TIME_TAI_NS_REG` (presented on the input lane).

## Operation (READ → COMPUTE → WRITE)

1. **READ:** `TF_POWER` (bit0), `TF_TAI_IN`, `TF_PERIOD_NS`, `TF_BAR_SEQ`, `TF_BAR_CLOSED`, `TF_BAR_START`.
2. **COMPUTE (branchless):**
   - `elapsed   = cell_addsub(tai, bar_start, 1)` — `TAI - BAR_START` (two's-complement subtract).
   - `lt        = cmp_lt(elapsed, period)` — 1 iff `elapsed < period` (carry-chain comparator).
   - `rollover  = cell_gate(lt ^ 1, power)` — `(elapsed >= period) AND powered`.
   - `seq_next  = cell_addsub(bar_seq, rollover, 0)` — `BAR_SEQ + rollover`.
   - `closed_next = cell_gate(rollover, power)` — pulse high on boundary, else 0 (one-tick).
   - `start_next  = cell_mux(bar_start, tai, rollover)` — re-anchor to TAI on boundary, else hold.
3. **WRITE:** latch `TF_BAR_SEQ`, `TF_BAR_CLOSED`, `TF_BAR_START`.

`TF_BAR_CLOSED` is naturally a one-tick pulse: it equals `rollover`, and the same tick that fires the
boundary re-anchors `BAR_START = TAI`, so the next tick's `elapsed` is small and `rollover` falls to 0.

## Clock Domain

- `timeframe` lives in the **pipeline / internal (250 MHz) domain** — it reads the TAI VALUE (sampled
  onto its input lane), not a cross-domain raw counter. It produces a bar sequence consumed by the
  bar-state modules (candle, footprint, tpo, fractal, cbr) and the spatial grid `REG_GRID_X_ADDR`.
- It is a **guide, not a master** (SPEC_REGISTERS.md §2): consumers carry their own period multiples
  and detect a new bar by `TF_BAR_SEQ != my_last_seq`.

## Single-Writer Contract

- **Writer:** `timeframe_tick()` (generated) — sole writer of `TF_BAR_SEQ`, `TF_BAR_CLOSED`,
  `TF_BAR_START`, `TF_TICKS`.
- **Readers:** candle / footprint / tpo / fractal / cbr / grid (each reads the published bus lanes,
  not these private registers); external probe/display.
- `TF_POWER` / `TF_RUN_UNTIL` / `TF_TAI_IN` / `TF_PERIOD_NS` are input/config lanes (set by the starter).

## Self-Running

`while ((TF_POWER & 1) && cmp_lt(TF_TICKS, TF_RUN_UNTIL)) { timeframe_tick(r); TF_TICKS += 1; }` —
the rollover detector self-runs from the power bit, bounded by a configured tick budget (config, not
external stepping). At integration the TAI value on `TF_TAI_IN` advances each tick from the upstream
time source; the standalone thin test presents a fixed sample to demonstrate boundary detection
without injecting data mid-loop (test-harness law).

## Open decisions (flagged for the founder)

- **TAI advance at integration.** Standalone, `TF_TAI_IN` is a fixed presented sample, so the loop
  demonstrates a single boundary evaluation per configured tick budget. At integration the upstream
  time source must drive a fresh TAI value onto `TF_TAI_IN` each tick (the producer publishes; the
  starter wires it). This is the same producer→lane wiring `tai_cdc` uses for `TAI_IN`; confirm the
  integration wiring when the pipeline-domain time crossing for the 250 MHz side is built.
- **First-bar anchor.** On power-on `TF_BAR_START = 0`, so the first nonzero `TF_TAI_IN` ≥ `period`
  fires bar 1 immediately and anchors. If the founder wants bar 0 to anchor at the first observed TAI
  without a phantom rollover, the starter should pre-load `TF_BAR_START = first_tai` before power-on
  (a config write, not device logic). Flagged — not silently chosen.
