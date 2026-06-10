# INTERNAL — 250 MHz Pipeline Metronome Clock

`internal` is the **250 MHz pipeline metronome**: the sample rate for all pipeline-domain modules
(DOM, indicators, risk, strategy, outbound). It is a **separate reference oscillator** from the MAC
clock (125 MHz, NIC domain) and from the TAI timebase. In the flip-flop model it is a free-running
counter that emits one edge strobe per cycle; pipeline modules fire on `INTERNAL_EDGE`.

```
  power bit ──► INTERNAL_CYCLE [64-bit free-running counter] ──► INTERNAL_EDGE (1 strobe / cycle)
                                                                      │
                                                                      ▼  (pipeline module trigger)
```

## Register Window (base 0x1E00000)

| Offset | Name                  | Width | Type            | Purpose                                                  |
|--------|-----------------------|-------|-----------------|----------------------------------------------------------|
| +0x00  | INTERNAL_POWER        | 1     | config (power)  | set once; counter self-runs while bit0 = 1               |
| +0x08  | INTERNAL_RUN_UNTIL    | 64    | config          | configured self-run stop count (set once by starter)     |
| +0x10  | INTERNAL_CYCLE        | 64    | dff (counter)   | free-running 250 MHz cycle count; += 1 per powered tick   |
| +0x18  | INTERNAL_EDGE         | 1     | dff (strobe)    | pipeline metronome edge: 1 every powered tick            |

Window: 0x1E00000 – 0x1E00018 (4 registers, 32 bytes).

## Operation (READ → COMPUTE → WRITE)

1. **READ:** `INTERNAL_POWER` (bit0), `INTERNAL_CYCLE`.
2. **COMPUTE:** `step = gate(1, power)`; `cycle_next = cell_addsub(cycle, step, 0)`; `edge_next = power`.
3. **WRITE:** latch `INTERNAL_CYCLE`, `INTERNAL_EDGE`.

`INTERNAL_RATIO_TO_MAC` is a read-only config constant (set by the starter), never written by the device.
Structural arithmetic only (cell_addsub) — no native `+`.

## Clock Domain

- **internal domain** owns all registers. Pipeline modules sample `INTERNAL_EDGE` as their metronome
  and read `INTERNAL_CYCLE` in-domain (no CDC needed for same-domain reads).
- Separate from MAC and from TAI. Cross-domain transfers (NIC→pipeline) cross via CDC fifos; the TAI
  value reaches the MAC domain via `tai_cdc` (this clock does not participate in that crossing).

## Single-Writer Contract

- **Writer:** `internal_tick()` (generated) — sole writer of CYCLE and EDGE.
- **Readers:** all pipeline modules (sample `INTERNAL_EDGE`, read `INTERNAL_CYCLE`); fifo depth /
  rate-ratio logic (read `INTERNAL_RATIO_TO_MAC`); external probe/display (read-only).
- `INTERNAL_POWER` / `INTERNAL_RUN_UNTIL` / `INTERNAL_RATIO_TO_MAC` are input lanes (set by starter).

## Self-Running

`while ((INTERNAL_POWER & 1) && cmp_lt(INTERNAL_CYCLE, INTERNAL_RUN_UNTIL)) internal_tick(r);`

