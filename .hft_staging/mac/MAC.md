# MAC — 125 MHz MAC Sample Clock

`mac` is the **125 MHz MAC clock**: the NIC's sample/copy RATE — when the NIC reads the wire and
stamps packets. Per the founder's two-clock model (CLAUDE.md): **MAC = the sample/copy RATE**, a
*separate clock from TAI* (TAI = the timestamp VALUE). The NIC samples on the MAC edge and stamps
with TAI's value brought into the MAC domain via CDC. MAC ≠ TAI — never conflate the sample clock
with the time clock.

In the flip-flop model the MAC clock is a free-running counter that emits one edge strobe per cycle;
the NIC fires its sample on `MAC_EDGE`.

```
  power bit ──► MAC_CYCLE [64-bit free-running counter] ──► MAC_EDGE (1 strobe / cycle)
                                                                │
                                                                ▼  (NIC sample trigger)
```

## Register Window (base 0x1D00000)

| Offset | Name          | Width | Type            | Purpose                                                |
|--------|---------------|-------|-----------------|--------------------------------------------------------|
| +0x00  | MAC_POWER     | 1     | config (power)  | set once; counter self-runs while bit0 = 1             |
| +0x08  | MAC_CYCLE     | 64    | dff (counter)   | free-running 125 MHz cycle count; += 1 per powered tick |
| +0x10  | MAC_EDGE      | 1     | dff (strobe)    | MAC sample edge: 1 every powered tick (NIC samples on it) |
| +0x18  | MAC_RUN_UNTIL | 64    | config          | configured self-run stop count (set once by starter)   |

Window: 0x1D00000 – 0x1D00020 (4 registers, 32 bytes).

## Operation (READ → COMPUTE → WRITE)

1. **READ:** `MAC_POWER` (bit0), `MAC_CYCLE`.
2. **COMPUTE:** `step = gate(1, power)`; `cycle_next = cell_addsub(cycle, step, 0)`; `edge_next = power`.
3. **WRITE:** latch `MAC_CYCLE`, `MAC_EDGE`.

Structural arithmetic only (cell_addsub) — no native `+`.

## Clock Domain

- **MAC domain** owns all registers. It is the NIC sample rate and a **separate oscillator** from
  `taisoc`/`tai` (TAI timebase) and from `internal` (pipeline metronome).
- The TAI value reaches this domain only via `tai_cdc` (gray-code 2-FF), never by raw cross-domain read.

## Single-Writer Contract

- **Writer:** `mac_tick()` (generated) — sole writer of CYCLE and EDGE.
- **Readers:** the NIC (samples on `MAC_EDGE`); `tai_cdc` sync FFs latch on this domain's edge;
  external probe/display (read-only).
- `MAC_POWER` / `MAC_RUN_UNTIL` are input lanes (set once by the starter).

## Self-Running

`while ((MAC_POWER & 1) && cmp_lt(MAC_CYCLE, MAC_RUN_UNTIL)) mac_tick(r);` — self-runs from the power
bit, bounded by configuration; nothing external steps it.

## Open Decisions (for the founder)

- None. The MAC clock is a straightforward free-running counter; the NIC consumes `MAC_EDGE`.
