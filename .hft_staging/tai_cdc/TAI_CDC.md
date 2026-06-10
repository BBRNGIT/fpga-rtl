# TAI_CDC — TAI Clock-Domain Crossing (gray-code 2-FF synchronizer)

`tai_cdc` brings the **TAI counter VALUE** from the `taisoc`/`tai` domain into the **MAC domain**,
metastability-safe (Cummings gray-code 2-FF synchronizer). The NIC samples on the MAC edge and stamps
packets with the MAC-domain output `TAI_MAC` — **never** a raw cross-domain read of `tai` (a multi-bit
counter raw-read across a domain boundary tears). There is **no discipline** anywhere in the clock set:
`taisoc` is the authoritative reference by definition.

```
  taisoc/tai domain                         MAC domain (clocked by mac edge)
  ─────────────────                         ────────────────────────────────
  TAI_IN  (sampled tai value, input lane)
     │  gray encode:  g = in ^ (in >> 1)            (combinational, XOR/shift)
     ▼
   gray  ──(async cross)──►  TAI_SYNC1_GRAY  (gated dff, MAC edge — stage 1)
                                  │
                                  ▼            TAI_SYNC2_GRAY  (gated dff, MAC edge — stage 2)
                                  gray decode (XOR fold) │
                                                         ▼
                                                      TAI_MAC  (MAC-domain value; NIC reads)
```

## Register Window (base 0x1F00000)

| Offset | Name              | Width | Type            | Purpose                                                  |
|--------|-------------------|-------|-----------------|----------------------------------------------------------|
| +0x00  | TAI_CDC_POWER     | 1     | config (power)  | enable: sync runs on the MAC edge while bit0 = 1         |
| +0x08  | TAI_CDC_RUN_UNTIL | 64    | config          | configured self-run tick budget (set once by starter)    |
| +0x10  | TAI_IN            | 64    | config (input)  | sampled tai value presented on tai_cdc's input lane      |
| +0x18  | TAI_CDC_TICKS     | 64    | dff (counter)   | self-run tick counter (bounds the self-run)              |
| +0x20  | TAI_SYNC1_GRAY    | 64    | dff             | stage-1 sync FF (gray-coded; catches metastability)      |
| +0x28  | TAI_SYNC2_GRAY    | 64    | dff             | stage-2 sync FF (gray-coded; stable, metastability-safe) |
| +0x30  | TAI_MAC           | 64    | comb (output)   | gray-decoded stage-2 value: the MAC-domain TAI value     |

Window: 0x1F00000 – 0x1F00038 (7 registers, 56 bytes).

## Behavior (one MAC clock edge — READ → COMPUTE → WRITE)

1. **READ:** `TAI_CDC_POWER`, `TAI_IN`, `TAI_SYNC1_GRAY`, `TAI_SYNC2_GRAY`.
2. **COMPUTE:**
   - gray encode: `g = TAI_IN ^ (TAI_IN >> 1)` (XOR/shift only).
   - stage 1: `SYNC1 <= g` (gated dff on MAC edge).
   - stage 2: `SYNC2 <= SYNC1` (gated dff on MAC edge).
   - gray decode: `TAI_MAC = fold_xor(SYNC2)` (parallel-prefix XOR fold; XOR/shift only).
3. **WRITE:** commit `TAI_SYNC1_GRAY`, `TAI_SYNC2_GRAY`, `TAI_MAC`.

Gray encode/decode are **bitwise** (XOR/shift) — NOT arithmetic, so gate stage 2b (no native `+/-/*`)
passes. The two FFs give the 2-cycle metastability settling window; the gray code guarantees at most
one bit changes per source increment, so a mid-flight sample is never a corrupt multi-bit value.

## Clock Domain

- **Destination = MAC domain.** The sync FFs latch on the MAC edge (tai_cdc is clocked by `mac`).
- **Source = taisoc/tai domain.** `TAI_IN` is the source-domain sample presented on tai_cdc's own
  input lane — tai_cdc does NOT reach into `tai`'s registers (module-barrier law). At integration the
  `tai` value is presented here; the synchronizer carries it safely across.

## Single-Writer Contract

- **Writer:** `tai_cdc_tick()` (generated) — sole writer of SYNC1, SYNC2, TAI_MAC; the run loop owns
  TAI_CDC_TICKS.
- **Reader:** the NIC (reads `TAI_MAC` in-domain to stamp packets); external probe/display.
- `TAI_CDC_POWER` / `TAI_CDC_RUN_UNTIL` / `TAI_IN` are input lanes (set once by the starter).

## Self-Running

`while ((TAI_CDC_POWER & 1) && cmp_lt(TAI_CDC_TICKS, TAI_CDC_RUN_UNTIL)) tai_cdc_tick(r);` — runs on
the MAC edge while powered, bounded by a configured tick budget (config, not external stepping).

## Open Decisions (for the founder)

- **TAI_IN presentation at integration.** Standalone, the starter sets `TAI_IN` to a fixed sample to
  demonstrate the encode→2FF→decode round-trip (`TAI_MAC == TAI_IN` after 2 settling edges). At
  integration, the live `tai` value is presented on this lane each MAC edge (it then tracks `tai`,
  2 MAC edges behind). Confirm the presentation seam (how `tai`'s value reaches `TAI_IN`) when the
  NIC/backplane wiring is built — same shape as the adapter→wire deposit seam.
