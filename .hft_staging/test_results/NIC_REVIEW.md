# NIC Build — Review & Graduation Readiness

## Summary
Wire→FIFO gateway rebuilt fresh against graduated clock set. Emitter-first, gate-passing. E2E verified. Held pre-graduation for approval.

## Context
- **Rebuilt reason:** NIC was deleted as wrong-design (pre-taiosc, depended on pps_mac discipline)
- **New design:** uses graduated clock set (tai_cdc provides MAC-domain TAI_MAC_SYNC2)
- **Window:** 0x1A00000 (between wire 0x1800000 and mac 0x1D00000)

## Component Spec

| Aspect | Detail |
|--------|--------|
| **What it does** | Samples wire at mac rate · dedup by seq (ring, depth 16) · re-stamps with TAI_MAC from tai_cdc · 1-cycle write strobe to seam |
| **Inputs** | WIRE_* lanes (wire bus); TAI_MAC from tai_cdc (CDC output, MAC-domain stable) |
| **Outputs** | SEAM_* lanes (nic→fifo seam): re-stamped packet (bid/ask/symbol/pip/commission + time/seq + dedup_mark + strobe) |
| **Constraint** | Module barrier: reads bus (wire), does NOT raw-read another module's registers (tai_cdc output is in-domain MAC, safe to read) |
| **Rate** | MAC cadence (125 MHz); 1-cycle strobe per unique packet |

## Build Artifacts

**Emitter-first workflow:**
- `gen_nic_net.py` (emitter script) ✅
- `nic.net.json` (netlist, committed) ✅
- `gennet.py` → `nic_gen.h` (device code, gitignored) ✅
- `nic.c` / `nic.h` / `display.c` (thin host glue, 31 lines) ✅
- `test_synth.c` (thin test, 31 lines ≤45) ✅
- `Makefile` (regenerates wire_gen.h + tai_cdc_gen.h sibling sources) ✅
- `validate.py` (adds module-barrier check) ✅

## Gate Results

✅ **validate** — 46 nodes; single-writer/no-overlap/no-floating; **module-barrier OK**

✅ **build** — Regenerates siblings (wire, tai_cdc); compiles nic_gen.h; zero errors

✅ **2b (gate-level arith)** — No native `+`/`-`/`*`; dedup via bitwise `cell_eqmask` + `cell_mux`; comparators are carry-chain

✅ **2c (no hand-written logic)** — Only emitter + generated code; no `cell_*()` in source

✅ **clean-room** — 3 independent rebuilds from committed HEAD; byte-identical

## Test Coverage — Real Execution Output

### Scenario 1: Duplicate Packet (same seq)
```
SEAM_VALID=0  SEAM_STROBE=0  SEAM_DEDUP_MARK=1
SEAM_SEQ=42  SEAM_TIME(TAI)=48358647703819896  SEAM_SRC_TIME=7777
```
**Verified:** Dedup ring detects same seq, blocks strobe (STROBE=0), marks duplicate (DEDUP_MARK=1) ✅

### Scenario 2: Unique Packet (different seq)
```
SEAM_VALID=1  SEAM_STROBE=1  SEAM_DEDUP_MARK=0
SEAM_SEQ=43  SEAM_TIME(TAI)=48358647703819896  SEAM_SRC_TIME=7777
SEAM_BID_PX=19500  SEAM_ASK_PX=19510  SEAM_SYMBOL=1  SEAM_PIP=100  SEAM_COMMISSION=0
```
**Verified:** Dedup ring passes unique seq, fires strobe (STROBE=1), updates ring, preserves price-only payload + TAI stamp ✅

## Architectural Compliance

✅ **Module barrier law:**
- Reads wire bus (WIRE_* lanes) — correct module-to-module boundary
- Reads TAI_MAC (from tai_cdc, MAC-domain stable output) — NOT raw-read of tai
- Writes seam lanes (SEAM_*) — sole writer to seam

✅ **Two-clock model:**
- MAC clock: sample rate (when NIC reads wire + stamps)
- TAI clock: timestamp value (read from tai_cdc's MAC-domain copy)

✅ **No discipline:**
- NIC does not discipline any clock
- Uses graduated tai_cdc (gray-code CDC) for cross-domain TAI transfer

✅ **Branchless data path:**
- Dedup via bitwise ops (no loops, no branches in data path)
- TAI re-stamp via mux + dff
- Gate-level arithmetic only

## Known Issues

### Two gate.sh bugs (not in NIC, in main infrastructure)
1. **False PASS on build failure** — `set -e` doesn't apply to `&&` chains
2. **Clean-room path math** — assumes `.hft_staging/<component>/` but worktrees add level

**Workaround applied:** NIC tested independently; clean-room verified by hand (3 manual rebuilds).

### E2E Verification Status
✅ **Adapter → Wire → NIC → Seam verified with real data**
- Packet entry to exit confirmed
- TAI stamping correct
- Dedup functional
- Strobe fires for unique packets

## Readiness Checklist
- ✅ All gates pass
- ✅ Emitter-first workflow enforced
- ✅ Thin test (31 lines, scenarios cover dedup + stamp)
- ✅ Zero hand-written device logic
- ✅ CLAUDE.md laws verified (no floats, no malloc, branchless, gate-level arith)
- ✅ Module barrier compliance verified
- ✅ E2E verification with real data
- ✅ Committed on task/nic

## Status
✅ **READY FOR GRADUATION to .hft/ vault**

**Graduation command:**
```bash
.hft_staging/graduate.sh nic
```

**Confirm to proceed, or request changes.**
