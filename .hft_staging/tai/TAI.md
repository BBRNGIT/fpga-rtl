# TAI — Authoritative Time Counter (PLAIN counter off taisoc; NO discipline)

`tai` is the authoritative internal timestamp: a 64-bit counter **clocked by the `taisoc`
oscillator**. One `taisoc` edge = one `tai` tick = `TAI_NS += 1`. There is **NO discipline anywhere
— no PPS, no PI loop, no offset** (settled law, CLAUDE.md): `taisoc` is the authoritative reference
*by definition* (our GNSS-equivalent truth), the model is one deterministic time base, and there is
nothing to discipline against. `tai` just counts `taisoc` at full rate.

```
  taisoc edge (tai's clock) ──► TAI_NS [64-bit free-running counter] ──► TAI_NS output
                                                                            │
                                                                            ▼  (sampled by tai_cdc
                                                                               into the MAC domain →
                                                                               TAI_MAC, read by NIC)
```

Because `tai` is **clocked by** `taisoc`, in the flip-flop model it is structurally a free-running
counter whose tick *is* a `taisoc` edge: it advances by 1 each tick while powered. `tai` does NOT
reach into `taisoc`'s registers (module-barrier law) — it runs on the `taisoc` clock; the two are
wired at integration time (the `taisoc` edge is `tai`'s clock input). This mirrors how the NIC
samples on the MAC edge without reading the MAC counter's internals.

## Register Window (base 0x1C00000)

| Offset | Name          | Width | Type            | Purpose                                              |
|--------|---------------|-------|-----------------|------------------------------------------------------|
| +0x00  | TAI_POWER     | 1     | config (power)  | set once; counter runs on the taisoc clock while bit0 = 1 |
| +0x08  | TAI_RUN_UNTIL | 64    | config          | configured self-run stop count (set once by starter) |
| +0x10  | TAI_NS        | 64    | dff (counter)   | authoritative 64-bit timestamp; += 1 per taisoc edge |

Window: 0x1C00000 – 0x1C00018 (3 registers, 24 bytes).

## Operation (READ → COMPUTE → WRITE)

1. **READ:** `TAI_POWER` (bit0), `TAI_NS`.
2. **COMPUTE:** `step = gate(1, power)`; `ns_next = cell_addsub(TAI_NS, step, 0)`.
3. **WRITE:** latch `TAI_NS`.

Structural arithmetic only (cell_addsub) — no native `+`. No edge strobe output (the consumer is
`tai_cdc`, which samples the counter VALUE, not an edge).

## Clock Domain

- **TAI / taisoc domain** owns `TAI_NS`. It is the authoritative timestamp VALUE — a SEPARATE clock
  from MAC (the sample RATE) and from internal (the pipeline metronome). CLAUDE.md two-clock model.
- **Consumer:** `tai_cdc` regenerates `TAI_NS` in the MAC domain via a gray-code 2-FF synchronizer
  (producing `TAI_MAC`). The NIC stamps with `TAI_MAC`, **never** raw `TAI_NS` across the domain.

## Single-Writer Contract

- **Writer:** `tai_tick()` (generated) — sole writer of `TAI_NS`.
- **Readers:** `tai_cdc` (samples `TAI_NS` through its gray-code synchronizer); external probe/display.
- `TAI_POWER` / `TAI_RUN_UNTIL` are input lanes (set once by the starter).

## Self-Running

`while ((TAI_POWER & 1) && cmp_lt(TAI_NS, TAI_RUN_UNTIL)) tai_tick(r);` — one tick per taisoc edge,
bounded by configuration (not external stepping).

## Settled Laws (per CLAUDE.md, no longer open)

- **No discipline.** `tai` is a plain counter; there is no PPS/PI loop anywhere in the clock set. The
  retired `pps_mac` (a PPS-disciplined MAC PHC) was a pre-`taiosc` framing error — deleted, not patched.
- **`tai` is clocked by `taisoc`.** The standalone thin test self-runs `tai` on its own power bit
  (one tick == one taisoc edge) to demonstrate counting without injecting data into a register
  (test-harness law). At integration the `taisoc` edge is `tai`'s clock.
