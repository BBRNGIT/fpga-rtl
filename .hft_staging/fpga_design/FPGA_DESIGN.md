# FPGA Design Module

**Status:** Blank template for 3-way device separation.

**Purpose:** High-level specification of the FPGA backplane — device hierarchy, address allocation, module placement, and clock domain boundaries.

This module will be **cloned and specialized into 3 separate FPGA device specifications**:

1. **NIC FPGA** (`fpga_nic/`) — 125 MHz, ingress chain (adapter → wire → NIC → CDC FIFO)
2. **Pipeline FPGA** (`fpga_pipeline/`) — 250 MHz, core analytics (DOM → indicators → strategies)
3. **Control FPGA** (future) — Admin/diagnostics/display control plane

---

## Design Phases (Blank → Specialized)

### Phase 0: Blank Template (This File)
- Device-agnostic placeholders
- Register fabric structure outline
- Clock domain boundaries defined
- Module assignment placeholders

### Phase 1: NIC FPGA Specialization (fpga_nic/)
- **Target device:** Xilinx Virtex UltraScale+ (VU9P) — reference
- **Clock:** 125 MHz MAC (primary) + 250 MHz internal (CDC target)
- **Modules:** adapter, wire, taiosc, tai, mac, tai_cdc, nic, fifo_rx
- **Transceivers:** 32× GTY @ 32.75 Gbps (for 40G/100G NIC backplane)
- **BRAM:** Shared register fabric, wire bus, NIC packet buffer
- **Output seam:** fifo_rx packets → CDC FIFO to Pipeline FPGA

### Phase 2: Pipeline FPGA Specialization (fpga_pipeline/)
- **Target device:** Xilinx Virtex UltraScale+ (VU9P) — reference
- **Clock:** 250 MHz internal (primary) + 125 MHz for CDC input from NIC
- **Modules:** dom, candle, footprint, tpo, timeframe, fractal, cbr
- **Transceivers:** (optional, for future outbound orders)
- **BRAM:** Historical rings (candle × 256 bars, footprint history, TPO grids)
- **Input seam:** CDC FIFO from NIC FPGA
- **Output seam:** Strategy decisions, order signals (future)

### Phase 3: Control FPGA Specialization (fpga_control/, future)
- **Clock:** CPU-synchronous (TBD)
- **Purpose:** Admin interface, display control, real-time diagnostics
- **Transceivers:** (optional, for control plane uplink)
- **Interface:** Reads published registers from both NIC and Pipeline FPGAs via AXI/shared memory

---

## Register Fabric Architecture (Blank)

### Address Map (Conceptual)

```
Backplane Address Space (word_t = 64-bit)

0x0000_0000 — 0x0000_FFFF  Reserved / Boot / Config
0x0001_0000 — 0x0001_FFFF  Shared Clock Domain (taiosc, tai, mac, internal)
0x0002_0000 — 0x0002_FFFF  NIC Ingress Chain
  0x0002_0000 — adapter regs
  0x0002_1000 — wire bus (passive)
  0x0002_2000 — nic regs
  0x0002_3000 — fifo_rx seam
0x0003_0000 — 0x0003_FFFF  CDC Seams (NIC ↔ Pipeline)
  0x0003_0000 — fifo_rx_read side (Pipeline reads)
  0x0003_1000 — tai_cdc (tai into Pipeline domain)
0x0004_0000 — 0x000F_FFFF  Pipeline Analytics Registers
  0x0004_0000 — dom regs + tables
  0x0005_0000 — candle regs + history ring
  0x0006_0000 — footprint regs + history
  0x0007_0000 — tpo regs + accumulator
  0x0008_0000 — timeframe regs
  0x0009_0000 — fractal regs
  0x000A_0000 — cbr regs
0x0010_0000 — 0x00FF_FFFF  Expansion / Future Modules

Total addressable: 256 MWords × 64 bits = 2 GB
(Actual used: ~10 MB for 15 modules + fabric overhead)
```

---

## Clock Domains

### Domain 1: Reference (Shared)
- **Source:** 156.25 MHz DIFF pair (10G Ethernet standard, external oscillator)
- **Use:** Input to MMCM/PLL (all devices)
- **Modules:** taiosc, tai (disciplined off this reference)

### Domain 2: MAC (NIC FPGA primary)
- **Frequency:** 125 MHz
- **Source:** MMCM/PLL from reference (÷1.25)
- **Modules:** mac, nic, adapter, wire (input side)
- **Properties:** Free-running, no external sync
- **CDC crossing:** tai → tai_cdc → Pipeline

### Domain 3: Internal (Pipeline FPGA primary)
- **Frequency:** 250 MHz
- **Source:** MMCM/PLL from reference (×1.6)
- **Modules:** dom, candle, footprint, tpo, timeframe, fractal, cbr
- **Properties:** Free-running, independent of MAC domain
- **CDC input:** fifo_rx (from MAC), tai_cdc (from MAC)

---

## Module Placement (Blank → Specialized)

### NIC FPGA Placement (fpga_nic/)
```
┌─────────────────────────────────────┐
│     NIC FPGA (Virtex UltraScale+)   │
├─────────────────────────────────────┤
│  BLOCK RAM (MAC domain)             │
│  ├─ wire bus (passive, R/W)         │
│  ├─ adapter input buffer            │
│  ├─ nic packet buffer               │
│  └─ fifo_rx dual-clock FIFO         │
├─────────────────────────────────────┤
│  Logic (MAC @ 125 MHz)              │
│  ├─ adapter (208 cells)             │
│  ├─ nic (180 cells)                 │
│  ├─ fifo_rx CDC (gray code 2-FF)    │
│  └─ shared clocks (taiosc, tai)     │
├─────────────────────────────────────┤
│  Transceivers (32× GTY @ 32.75G)    │
│  ├─ NIC PHY (40G/100G backplane)    │
│  └─ CDC bridge to Pipeline FPGA     │
└─────────────────────────────────────┘

Output seam to Pipeline:
  - fifo_rx packets (512-bit wide)
  - tai_cdc (TAI timestamp in Pipeline clock domain)
```

### Pipeline FPGA Placement (fpga_pipeline/)
```
┌─────────────────────────────────────┐
│  Pipeline FPGA (Virtex UltraScale+) │
├─────────────────────────────────────┤
│  Block RAM (Internal domain)        │
│  ├─ dom tables (16K entries)        │
│  ├─ candle history (256 bars)       │
│  ├─ footprint history               │
│  ├─ tpo accumulator grid            │
│  └─ fractal/cbr state               │
├─────────────────────────────────────┤
│  Logic (Internal @ 250 MHz)         │
│  ├─ dom (212 cells)                 │
│  ├─ candle (64 cells)               │
│  ├─ footprint (88 cells)            │
│  ├─ tpo (72 cells)                  │
│  ├─ timeframe (8 cells)             │
│  ├─ fractal (15 cells)              │
│  ├─ cbr (18 cells)                  │
│  └─ fifo_rx reader (CDC read side)  │
├─────────────────────────────────────┤
│  Input seams (from NIC FPGA)        │
│  ├─ fifo_rx packets (via CDC FIFO)  │
│  └─ tai_cdc (timestamp, CDC'd)      │
└─────────────────────────────────────┘

Output seams:
  - Strategy decisions (future)
  - Order signals (future)
```

---

## Wiring (Blank, to be filled in Phase 1/2)

### NIC → Pipeline Cross-Device CDC
- **Packet path:** fifo_rx (NIC domain) → async FIFO → fifo_rx read (Pipeline domain)
- **Timestamp path:** tai (MAC domain) → gray-code 2-FF → tai_cdc (Pipeline domain)
- **Handshake:** write_ptr_gray, read_ptr_gray (both gray-coded pointers)

### Pipeline Internal Wiring (to be detailed in fpga_pipeline/)
- DOM publishes BID/ASK/QTY registers
- Candle reads DOM; writes OHLC + history ring
- Footprint reads DOM; writes profile + history
- Etc. (order-free execution, no timing dependencies)

---

## Resource Budget (Blank Template)

### Xilinx Virtex UltraScale+ (VU9P, target)

| Resource | Total | Used | Available | Notes |
|----------|-------|------|-----------|-------|
| LUTs | 1,161,600 | ~10,000 (cells) | 1,151,600 | Abundant |
| BRAM36 | 2,160 | ~50–100 | 2,060–2,110 | Register fabric + rings |
| BRAM18 | 4,320 | ~0–50 | 4,270–4,320 | Staging buffers (if needed) |
| DSP48E2 | 6,840 | 0 | 6,840 | Not used (no arithmetic) |
| GT (GTY) | 32 | ~8 | 24 | NIC PHY + CDC bridge |
| MMCM | 6 | ~2–3 | 3–4 | Reference, MAC, Internal |

**Conclusion:** VU9P has abundant headroom for 15 modules + register fabric + future expansion.

---

## Design Flow (Template)

1. **Device selection** → Reference Xilinx Virtex UltraScale+ (VU9P)
2. **Clock generation** → Specify MMCM/PLL for MAC (125 MHz) + Internal (250 MHz)
3. **Address allocation** → Assign register addresses to each module (Phase 1/2)
4. **Module instantiation** → Include 15 graduated modules + shared infra
5. **Wiring** → Connect module outputs to inputs (single-writer law)
6. **CDC specification** → Explicit gray-code synchronizers + async FIFO
7. **Synthesis** → Run Vivado flow (tech-specific, not in C model)
8. **Place & Route** → Xilinx PAR, floorplan clock domains
9. **Bitstream generation** → Program FPGA devices
10. **Verification** → Gate stage validates C model before synthesis

---

## Files to Generate (Specialization Phase)

### Phase 1: NIC FPGA (fpga_nic/)
- `fpga_nic.md` — Device spec, address map, module list
- `gen_fpga_nic_net.py` — Emitter (register allocator, module placement)
- `fpga_nic.net.json` — Netlist (Vivado will consume this for cross-check)
- `validate.py` — FPGA-specific validator (address overlap, clock domain integrity)
- `gennet.py` — FPGA backplane generator (fabric_nic_gen.h)

### Phase 2: Pipeline FPGA (fpga_pipeline/)
- `fpga_pipeline.md` — Device spec, address map, module list
- `gen_fpga_pipeline_net.py` — Emitter
- `fpga_pipeline.net.json` — Netlist
- `validate.py` — FPGA-specific validator
- `gennet.py` — Backplane generator

### Phase 3: Control FPGA (fpga_control/, future)
- (Similar structure)

---

## References

- **FOUNDER_VISION.md §3** — Devices & The Backplane
- **FOUNDER_VISION.md §14** — Next Steps (FPGA fabric design)
- **FPGA_DEVICE_RESEARCH.md** — FPGA device specs and rationale
- **CLAUDE.md** — Build methodology (emitter-first pipeline applies to FPGA too)
- **.hft_staging/FABRIC_ARCHITECTURE.md** — High-level fabric design (reference)
