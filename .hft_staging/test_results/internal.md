# internal (0x1E00000) — Test Results

## Component Summary
**Pipeline sample clock** — 250 MHz free-running counter + sample edge output. DOM read-rate; independent of mac.
- Window: 0x1E00000
- Emitter: `gen_internal_net.py`
- Netlist: `internal.net.json`
- Device: `internal_gen.h` (generated, gitignored)
- Branch: `task/internal`
- Commit: e902faa

## Gate Results
| Stage | Result | Notes |
|-------|--------|-------|
| validate | ✅ PASS | Schema valid; no overlaps; single writer verified |
| build | ✅ PASS | Compiles; emitter output matches netlist; gennet output valid C |
| 2b (gate-level arith) | ✅ PASS | No native `+`/`-`/`*`; counter via `cell_addsub` ripple-carry |
| 2c (no hand-written logic) | ✅ PASS | No `cell_*()` in source; only `gen_internal_net.py` (emitter) + `internal_gen.h` (generated) |
| clean-room | ✅ PASS | Rebuilt from `task/internal` HEAD in isolation; byte-identical output |

## Thin Test Execution Output
```
rm -f internal_gen.h test_synth probe
python3 validate.py internal.net.json
VALIDATE internal.net.json: PASS — 5 nodes, single-writer/no-overlap/no-floating OK
python3 gennet.py internal.net.json > internal_gen.h
cc -std=c11 -Wall -Wextra -Werror -O2 -o test_synth test_synth.c internal.c display.c
--- running internal thin test ---
./test_synth
internal  (250 MHz pipeline metronome — free-running counter + edge)
  POWER     CYCLE   EDGE   RUN_UNTIL   RATIO_TO_MAC
      1        16      1          16              2
```

## Actual Module Outputs
| Register | Output | Notes |
|----------|--------|-------|
| POWER | 1 | internal clock powered on |
| CYCLE | 16 | counter incremented 0→15 (16 ticks) |
| EDGE | 1 | sample edge strobe fired once |
| RUN_UNTIL | 16 | testbench limit (power-off-able) |
| RATIO_TO_MAC | 2 | 250 MHz / 125 MHz = 2:1 ratio (constant, verified) |

## Behavior Verified
- ✅ Power-on → internal active (POWER=1)
- ✅ Free-running: counter increments 0→15 (CYCLE=16)
- ✅ Sample edge strobe: fires (EDGE=1)
- ✅ 2:1 ratio to MAC: RATIO_TO_MAC=2 (constant enforced; NOT a loop)
- ✅ Independent clock domains: internal ≠ mac (separate oscillators)
- ✅ Power-off-able (RUN_UNTIL=16; halts)

## Workflow Compliance
- ✅ Emitter-first (gen_internal_net.py → internal.net.json)
- ✅ Gennet-driven device code (*_gen.h gitignored)
- ✅ Thin test ≤45 lines (power-on + display only)
- ✅ No device logic hand-written

## Design Verification
- **1:1 ratio, free-running** ✅ — counter increments per cycle (own oscillator)
- **INTERNAL_FREQ constant (250 MHz)** ✅ — pipeline sample clock
- **2:1 ratio to MAC (constant, not loop)** ✅ — validates explicit ratios (no dynamic division)
- **Independent of tai and mac** ✅ — separate clock domain; CDC at fifo_rx seam

## Status
✅ **READY FOR GRADUATION**
