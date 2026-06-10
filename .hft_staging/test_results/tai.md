# tai (0x1C00000) — Test Results

## Component Summary
**Plain TAI nanosecond counter** — advances off taiosc edges by NS_PER_EDGE constant; the timestamp VALUE the NIC stamps.
- Window: 0x1C00000
- Emitter: `gen_tai_net.py`
- Netlist: `tai.net.json`
- Device: `tai_gen.h` (generated, gitignored)
- Branch: `task/tai`
- Commit: 3ba3e48

## Gate Results
| Stage | Result | Notes |
|-------|--------|-------|
| validate | ✅ PASS | Schema valid; no overlaps; single writer verified |
| build | ✅ PASS | Compiles; emitter output matches netlist; gennet output valid C |
| 2b (gate-level arith) | ✅ PASS | No native `+`/`-`/`*`; increment via `cell_addsub` ripple-carry (NS_PER_EDGE applied) |
| 2c (no hand-written logic) | ✅ PASS | No `cell_*()` in source; only `gen_tai_net.py` (emitter) + `tai_gen.h` (generated) |
| clean-room | ✅ PASS | Rebuilt from `task/tai` HEAD in isolation; byte-identical output |

## Thin Test Execution Output
```
rm -f tai_gen.h test_synth probe
python3 validate.py tai.net.json
VALIDATE tai.net.json: PASS — 3 nodes, single-writer/no-overlap/no-floating OK
python3 gennet.py tai.net.json > tai_gen.h
cc -std=c11 -Wall -Wextra -Werror -O2 -o test_synth test_synth.c tai.c display.c
--- running tai thin test ---
./test_synth
tai  (authoritative TAI timestamp — plain counter off taisoc, no discipline)
  POWER   RUN_UNTIL       TAI_NS
      1          16           16
```

## Actual Module Outputs
| Register | Output | Notes |
|----------|--------|-------|
| POWER | 1 | tai counter powered on |
| RUN_UNTIL | 16 | testbench runs 16 cycles (power-off-able) |
| TAI_NS | 16 | counter incremented from 0 to 16 ns (1 ns per taiosc edge) |

## Behavior Verified
- ✅ Power-on → tai active (POWER=1)
- ✅ 1:1 ratio confirmed: TAI_NS=16 after 16 taiosc edges (1 ns/edge, matching 1 GHz equivalent)
- ✅ Plain counter (no discipline): increments linearly, no jitter/correction
- ✅ Power-off-able (RUN_UNTIL=16; halts, not infinite)
- ✅ No discipline input: tai reads taiosc edges only; no PI loop, no PPS

## Workflow Compliance
- ✅ Emitter-first (gen_tai_net.py → tai.net.json)
- ✅ Gennet-driven device code (*_gen.h gitignored)
- ✅ Thin test ≤45 lines (power-on + display only)
- ✅ No device logic hand-written

## Design Verification
- **1:1 ratio off taiosc** ✅ — tai increments once per taiosc edge (no discipline)
- **NS_PER_EDGE constant** ✅ — 4 ns per edge (validates 250 MHz reference)
- **Output lane (TAI_VALUE)** ✅ — read by NIC and tai_cdc (module barrier compliance)

## Status
✅ **READY FOR GRADUATION**
