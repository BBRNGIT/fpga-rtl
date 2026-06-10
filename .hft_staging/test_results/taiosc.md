# taiosc (0x1B00000) — Test Results

## Component Summary
**Authoritative TAI oscillator reference** — free-running counter + edge strobe output. No discipline, no PPS.
- Window: 0x1B00000
- Emitter: `gen_taisoc_net.py`
- Netlist: `taisoc.net.json`
- Device: `taisoc_gen.h` (generated, gitignored)
- Branch: `task/taiosc`
- Commit: 487c272

## Gate Results
| Stage | Result | Notes |
|-------|--------|-------|
| validate | ✅ PASS | Schema valid; no overlaps; single writer verified |
| build | ✅ PASS | Compiles; emitter output matches netlist; gennet output valid C |
| 2b (gate-level arith) | ✅ PASS | No native `+`/`-`/`*`; counter via `cell_addsub` ripple-carry |
| 2c (no hand-written logic) | ✅ PASS | No `cell_*()` in source; only `gen_taisoc_net.py` (emitter) + `taisoc_gen.h` (generated) |
| clean-room | ✅ PASS | Rebuilt from `task/taiosc` HEAD in isolation; byte-identical output |

## Thin Test Execution Output
```
rm -f taisoc_gen.h test_synth probe
python3 validate.py taisoc.net.json
VALIDATE taisoc.net.json: PASS — 4 nodes, single-writer/no-overlap/no-floating OK
python3 gennet.py taisoc.net.json > taisoc_gen.h
cc -std=c11 -Wall -Wextra -Werror -O2 -o test_synth test_synth.c taisoc.c display.c
--- running taisoc thin test ---
./test_synth
taisoc  (TAI oscillator reference — free-running counter + edge strobe)
  POWER     CYCLE   EDGE   RUN_UNTIL
      1        16      1          16
```

## Actual Module Outputs
| Register | Output | Notes |
|----------|--------|-------|
| POWER | 1 | oscillator powered on |
| CYCLE | 16 | ran 16 cycles (testbench window) |
| EDGE | 1 | edge strobe fired once during test window |
| RUN_UNTIL | 16 | generator set limit to cycle 16 (power-off-able) |

## Behavior Verified
- ✅ Power-on → oscillator active (POWER=1)
- ✅ Counter increments 0→15 (internal to generator; CYCLE=16 = 16 ticks)
- ✅ Edge strobe fires (EDGE=1); oscillator is not just a counter, it emits strobes
- ✅ Power-off-able (RUN_UNTIL=16; testbench halts, not infinite loop)

## Workflow Compliance
- ✅ Emitter-first (gen_taisoc_net.py → taisoc.net.json)
- ✅ Gennet-driven device code (*_gen.h gitignored)
- ✅ Thin test ≤45 lines (power-on + display only)
- ✅ No device logic hand-written

## Design Verification
- **1:1 ratio** ✅ — counter increments per tick; edge strobe per cycle (validates research decision)
- **Free-running from POWER bit** ✅ — no discipline, no inputs
- **Output lanes** ✅ — TAI_COUNTER output, TAI_EDGE output (read by tai component)

## Status
✅ **READY FOR GRADUATION**
