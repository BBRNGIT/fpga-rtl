# TAISOC — TAI Oscillator Reference Clock

`taiosc` is the **TAI oscillator reference**: the crystal that defines the TAI timebase. In the
flip-flop model an oscillator is a free-running counter that emits one **edge strobe** per cycle.
`taiosc` owns no discipline and no timestamp value — it only produces the rate. The `tai` counter
counts these edges; the GNSS/PPS discipline (when reconciled) acts on `tai`, never on `taisoc`.

```
  power bit ──► TAISOC_CYCLE [64-bit free-running counter] ──► TAISOC_EDGE (1 strobe / cycle)
                                                                    │
                                                                    ▼  (read by `tai`)
```

## Register Window (base 0x1B00000)

| Offset | Name           | Width | Type            | Purpose                                              |
|--------|----------------|-------|-----------------|------------------------------------------------------|
| +0x00  | TAISOC_POWER   | 1     | config (power)  | set once; counter self-runs while bit0 = 1           |
| +0x08  | TAISOC_CYCLE   | 64    | dff (counter)   | free-running cycle count; += 1 per tick while powered |
| +0x10  | TAISOC_EDGE    | 1     | dff (strobe)    | 1 on every powered tick (the oscillator edge `tai` counts) |

Window: 0x1B00000 – 0x1B00018 (3 registers, 24 bytes).

## Operation (READ → COMPUTE → WRITE)

1. **READ:** `TAISOC_POWER` (bit0), `TAISOC_CYCLE`.
2. **COMPUTE:** `step = gate(1, power)` (advance only when powered); `cycle_next = cycle + step`;
   `edge_next = power` (strobe high every powered tick).
3. **WRITE:** latch `TAISOC_CYCLE = cycle_next`, `TAISOC_EDGE = edge_next`.

All arithmetic is the structural `cell_addsub` ripple-carry adder — no native `+`. The increment-by-step
is `cell_addsub(cycle, step, 0)` where `step ∈ {0,1}`.

## Clock Domain

- **taisoc domain** owns all three registers. It is the master rate reference for the TAI timebase.
- It is a **separate oscillator from MAC and from internal** — never conflate the sample clock (MAC)
  or pipeline metronome (internal) with the TAI rate. (CLAUDE.md two-clock model: MAC = sample RATE,
  TAI = timestamp VALUE; taisoc is the TAI VALUE's rate source.)

## Single-Writer Contract

- **Writer:** `taisoc_tick()` (generated device) — sole writer of CYCLE and EDGE.
- **Readers:** `tai` (counts `TAISOC_EDGE`); external probe/display (read-only).
- `TAISOC_POWER` is an input lane: set once by the starter, never written by the device.

## Self-Running

`while (TAISOC_POWER & 1) taisoc_tick(r);` — nothing external advances it.

## Open Decisions (for the founder)

- **Edge semantics:** `TAISOC_EDGE` is high on *every* powered tick (1:1 with the oscillator).
  If `tai` is meant to run slower than `taisoc` (decimated), the divisor belongs here as a strobe
  every-N-cycles. Current build: 1:1 (taisoc edge == tai increment), matching TAI.md's "full rate".
