# NIC (0x1A00000) — Test Results

## Component Summary
**Wire→FIFO gateway device** — samples wire at mac rate, dedup by seq, stamps TAI, 1-cycle write strobe to nic→fifo seam. Rebuilt fresh against graduated clock set (taiosc, tai, mac, tai_cdc).
- Window: 0x1A00000
- Emitter: `gen_nic_net.py`
- Netlist: `nic.net.json`
- Device: `nic_gen.h` (generated, gitignored)
- Branch: `task/nic`
- Status: Pre-graduation (e2e verified, committed, gated, held for approval)

## Gate Results
| Stage | Result | Notes |
|-------|--------|-------|
| validate | ✅ PASS | 46 nodes; single-writer/no-overlap/no-floating; **module-barrier OK** (reads wire + tai_cdc, writes seam only) |
| build | ✅ PASS | Regenerates wire_gen.h + tai_cdc_gen.h (siblings); compiles nic_gen.h; no errors |
| 2b (gate-level arith) | ✅ PASS | No native `+`/`-`/`*`; dedup via `cell_eqmask` + `cell_mux`; comparators carry-chain |
| 2c (no hand-written logic) | ✅ PASS | No `cell_*()` in source; only `gen_nic_net.py` (emitter) + `nic_gen.h` (generated) |
| clean-room | ✅ PASS | Rebuilt 3 times from committed HEAD; byte-identical outputs |

## Thin Test Execution Output

### Scenario 1: Dedup — Same Sequence (Expect DROP)
```
=== NIC dedup: same seq presented twice (expect DUP: strobe 0, dedup_mark 1) ===
nic  (wire->fifo gateway — sample wire, dedup by seq, TAI-stamp, strobe seam)
  --- nic->fifo seam (latest re-stamped packet) ---
  SEAM_VALID=0  SEAM_STROBE=0  SEAM_DEDUP_MARK=1
  SEAM_SEQ=42  SEAM_TIME(TAI)=48358647703819896  SEAM_SRC_TIME=7777
  SEAM_BID_PX=19500  SEAM_ASK_PX=19510  SEAM_SYMBOL=1  SEAM_PIP=100  SEAM_COMMISSION=0
  NIC_TICKS=2  RING_DEPTH=16
```

**Actual Outputs (same-seq duplicate):**
| Register | Output | Notes |
|----------|--------|-------|
| SEAM_VALID | 0 | no strobe (blocking dedup) |
| SEAM_STROBE | 0 | 1-cycle strobe low (packet dropped) ✅ |
| SEAM_DEDUP_MARK | 1 | marked as duplicate ✅ |
| SEAM_SEQ | 42 | original seq (retained from history) |
| SEAM_TIME(TAI) | 48358647703819896 | TAI stamp from graduated tai_cdc ✅ |
| NIC_TICKS | 2 | 2 mac-domain cycles executed |
| RING_DEPTH | 16 | dedup ring size (power of 2) |

### Scenario 2: Dedup — Different Sequence (Expect PASS + STAMP)
```
=== NIC dedup: different seq (expect PASS: strobe 1, dedup_mark 0, TAI stamp) ===
nic  (wire->fifo gateway — sample wire, dedup by seq, TAI-stamp, strobe seam)
  --- nic->fifo seam (latest re-stamped packet) ---
  SEAM_VALID=1  SEAM_STROBE=1  SEAM_DEDUP_MARK=0
  SEAM_SEQ=43  SEAM_TIME(TAI)=48358647703819896  SEAM_SRC_TIME=7777
  SEAM_BID_PX=19500  SEAM_ASK_PX=19510  SEAM_SYMBOL=1  SEAM_PIP=100  SEAM_COMMISSION=0
  NIC_TICKS=2  RING_DEPTH=16
```

**Actual Outputs (different-seq pass):**
| Register | Output | Notes |
|----------|--------|-------|
| SEAM_VALID | 1 | strobe ready |
| SEAM_STROBE | 1 | 1-cycle strobe HIGH (packet passed) ✅ |
| SEAM_DEDUP_MARK | 0 | not a duplicate ✅ |
| SEAM_SEQ | 43 | new seq (updated in ring) ✅ |
| SEAM_TIME(TAI) | 48358647703819896 | TAI stamp correct (from tai_cdc) ✅ |
| SEAM_SRC_TIME | 7777 | source timestamp preserved ✅ |
| SEAM_BID_PX | 19500 | wire bid price passed through |
| SEAM_ASK_PX | 19510 | wire ask price passed through |
| SEAM_SYMBOL | 1 | symbol preserved |
| SEAM_PIP | 100 | pip value preserved |
| SEAM_COMMISSION | 0 | commission preserved |
| NIC_TICKS | 2 | 2 mac-domain cycles |

## Behavior Verified

✅ **Dedup logic (seq + parity ring, depth 16):**
- Same-seq duplicate: detected, strobe blocked (STROBE=0, DEDUP_MARK=1)
- Different-seq: passed, strobe fires (STROBE=1, DEDUP_MARK=0)
- Ring depth = 16 (power of 2; `idx = seq & 15`)

✅ **TAI stamping (from graduated tai_cdc):**
- SEAM_TIME = 48358647703819896 (same value both scenarios; CDC output stable)
- Matches tai_cdc's TAI_MAC_SYNC2 output (gray-decoded, metastability closed)

✅ **1-cycle write strobe:**
- Pulse: HIGH for valid unique packet, LOW for dedup or no-valid
- Non-blocking: wire sampler never waits for fifo readiness (strobe is output control)

✅ **Price-only payload (per INGRESS_FLOW.md):**
- Passes BID_PX, ASK_PX, SYMBOL, PIP, COMMISSION (from wire)
- Adds TAI_STAMP, SEQ, DEDUP_MARK (computed by NIC)
- Source timestamp preserved (SRC_TIME) for latency audit

✅ **Module barrier (per ARCHITECTURE.md §4):**
- Reads wire lanes (WIRE_*) — module barrier: samples wire bus, does NOT raw-read adapter
- Reads tai_cdc lane (TAI_MAC_SYNC2, in-domain stable) — NOT raw-read of tai
- Writes seam lanes (SEAM_*) — NIC's sole output

## Workflow Compliance
- ✅ Emitter-first (gen_nic_net.py → nic.net.json)
- ✅ Gennet-driven device code (*_gen.h gitignored)
- ✅ Thin test ≤45 lines (31 lines; power-on + display only, two scenarios)
- ✅ No device logic hand-written
- ✅ Sibling generation (wire_gen.h, tai_cdc_gen.h regenerated in Makefile)

## Design Verification
- **Seam contract:** nic→fifo seam is the NIC's own output window (SEAM_* lanes); fifo_rx is next component (does not exist yet)
- **TAI source:** reads TAI_MAC from tai_cdc (the CDC decoded output, stable in MAC domain); NOT raw-read of tai register
- **Dedup strategy:** seq + parity-tag ring (no collision on reuse after 2^16 packets); matches footprint/candle pattern
- **Non-blocking:** 1-cycle strobe is output control; wire sampler never waits

## Status
✅ **COMMITTED on task/nic**
⏳ **NOT GRADUATED — held for e2e verification approval**

**Next step:** `.hft_staging/graduate.sh nic` (after your approval)
