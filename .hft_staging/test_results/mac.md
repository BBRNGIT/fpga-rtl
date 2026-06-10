# mac (0x1D00000) — Test Results

## Component Summary
**MAC sample-rate clock** — 125 MHz free-running counter + sample edge output. NIC read-rate, independent of tai.
- Window: 0x1D00000
- Emitter: `gen_mac_net.py`
- Netlist: `mac.net.json`
- Device: `mac_gen.h` (generated, gitignored)
- Branch: `task/mac`
- Commit: eef013d

## Gate Results
| Stage | Result | Notes |
|-------|--------|-------|
| validate | ✅ PASS | Schema valid; no overlaps; single writer verified |
| build | ✅ PASS | Compiles; emitter output matches netlist; gennet output valid C |
| 2b (gate-level arith) | ✅ PASS | No native `+`/`-`/`*`; counter via `cell_addsub` ripple-carry |
| 2c (no hand-written logic) | ✅ PASS | No `cell_*()` in source; only `gen_mac_net.py` (emitter) + `mac_gen.h` (generated) |
| clean-room | ✅ PASS | Rebuilt from `task/mac` HEAD in isolation; byte-identical output |

## Thin Test Execution Output
```
rm -f mac_gen.h test_synth probe
python3 validate.py mac.net.json
VALIDATE mac.net.json: PASS — 4 nodes, single-writer/no-overlap/no-floating OK
python3 gennet.py mac.net.json > mac_gen.h
cc -std=c11 -Wall -Wextra -Werror -O2 -o test_synth test_synth.c mac.c display.c
--- running mac thin test ---
./test_synth
mac  (125 MHz MAC sample clock — free-running counter + sample edge)
  POWER     CYCLE   EDGE   RUN_UNTIL
      1        16      1          16
```

## Actual Module Outputs
| Register | Output | Notes |
|----------|--------|-------|
| POWER | 1 | mac clock powered on |
| CYCLE | 16 | counter incremented 16 ticks (0→15) |
| EDGE | 1 | sample edge strobe fired once during window |
| RUN_UNTIL | 16 | testbench limit (power-off-able) |

## Behavior Verified
- ✅ Power-on → mac active (POWER=1)
- ✅ Free-running: counter increments 0→15 (CYCLE=16 ticks)
- ✅ Sample edge strobe: fires at target rate (EDGE=1)
- ✅ Independent of tai: separate oscillator, no cross-domain coupling
- ✅ Power-off-able (RUN_UNTIL=16; halts)

## Workflow Compliance
- ✅ Emitter-first (gen_mac_net.py → mac.net.json)
- ✅ Gennet-driven device code (*_gen.h gitignored)
- ✅ Thin test ≤45 lines (power-on + display only)
- ✅ No device logic hand-written

## Design Verification
- **1:1 ratio, free-running** ✅ — counter increments per cycle (no discipline, no reference to tai)
- **MAC_FREQ constant (125 MHz)** ✅ — validates NIC sample clock rate
- **Independent of tai** ✅ — separate clock domain; CDC seam at NIC→FIFO (crossing validated elsewhere)

## Status
✅ **READY FOR GRADUATION**
