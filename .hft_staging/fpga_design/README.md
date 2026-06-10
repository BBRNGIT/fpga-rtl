# FPGA Design Module

**Status:** Blank template for three-FPGA separation of concerns.

**Purpose:** Specify the FPGA backplane — device hierarchy, register allocation, module placement, and clock domains — prior to synthesis.

---

## Files

| File | Purpose |
|------|---------|
| **FPGA_DESIGN.md** | Blank FPGA spec template (will be cloned into 3 devices) |
| **THREE_FPGA_SEPARATION.md** | Architecture: why 3 FPGAs, what each does, how they connect |
| **README.md** | This file |

---

## Three FPGA Devices

This module will be **specialized into 3 separate FPGA designs:**

### 1. NIC FPGA (`fpga_nic/`)
- **Clock:** 125 MHz (MAC ingress rate)
- **Modules:** adapter, wire, taiosc, tai, mac, tai_cdc, nic, fifo_rx
- **Purpose:** Ingest market data, timestamp, deduplicate
- **Device:** Xilinx Virtex UltraScale+ (VU9P) — transceiver-optimized

### 2. Pipeline FPGA (`fpga_pipeline/`)
- **Clock:** 250 MHz (internal analytics rate)
- **Modules:** dom, candle, footprint, tpo, timeframe, fractal, cbr
- **Purpose:** Real-time market analytics, indicators, strategy prep
- **Device:** Xilinx Virtex UltraScale+ (VU9P) — BRAM-optimized

### 3. Control FPGA (`fpga_control/`, future)
- **Clock:** CPU-synchronous (TBD)
- **Purpose:** Admin interface, display control, diagnostics
- **Device:** Smaller FPGA or embedded (Lattice ECP5, Zynq)

---

## Separation of Concerns

**Why three?**

1. **Clock isolation:** MAC (125 MHz) and Internal (250 MHz) are independent oscillators on separate devices
2. **CDC simplification:** Only 2 signals cross device boundary (packet FIFO + TAI timestamp)
3. **Module localization:** Ingress logic stays near NIC; analytics stay in core
4. **Thermal/power:** Each device optimized for its role (I/O vs. compute vs. diagnostics)
5. **Redundancy:** NIC can be duplicated for dual-feed; others can be swapped independently

See **THREE_FPGA_SEPARATION.md** for detailed architecture.

---

## Device Research

**FPGA_DEVICE_RESEARCH.md** catalogs candidate FPGAs:

- **Xilinx Virtex UltraScale+** (VU9P) — Industry standard, recommended
- **Intel Stratix 10** — Alternative vendor, similar capabilities
- **Lattice ECP5** — Lower cost, open-source toolchain
- **Xilinx Zynq UltraScale+** — Integrated CPU (future control plane)

See **FPGA_DEVICE_RESEARCH.md** for device specs and selection rationale.

---

## Blank → Specialized Workflow

**Phase 0 (current):** Blank template (this directory)
- Placeholder register map
- Outline CDC connectivity
- Module assignment skeleton

**Phase 1:** NIC FPGA specialization (`fpga_nic/`)
- Write `gen_fpga_nic_net.py` (emitter)
- Generate `fpga_nic.net.json` (netlist)
- Write `gennet_fpga_nic.py` (generator)
- Create `fpga_nic_gen.h` (backplane C)
- Run gate.sh and graduate

**Phase 2:** Pipeline FPGA specialization (`fpga_pipeline/`)
- Same workflow as Phase 1
- Mirror NIC FPGA structure

**Phase 3:** Control FPGA specialization (`fpga_control/`, optional)
- Same workflow
- Smaller scope (diagnostics only)

---

## Emitter-First Pipeline

Each FPGA module follows the same build sequence:

```
1. Design spec → FPGA_DESIGN.md specialization
2. Emitter → gen_fpga_*.py (register allocator, module placement)
3. Netlist → fpga_*.net.json (address map, CDC specs)
4. Validator → validate_fpga.py (address overlap, clock domains)
5. Generator → gennet_fpga_*.py (backplane C code)
6. Generated → fpga_*_gen.h (committed to git)
7. Gate → .hft_staging/gate.sh (validation + clean-room build)
8. Graduate → .hft/fpga_*/  (immutable vault)
```

Same as module components (adapter, candle, etc.) — consistency across system.

---

## Quick Reference

**Device comparison:**

| Aspect | NIC FPGA | Pipeline FPGA | Control FPGA |
|--------|----------|---------------|--------------|
| **Device** | VU9P | VU9P | ECP5 (future) |
| **Clock** | 125 MHz | 250 MHz | 100 MHz–1 GHz |
| **Modules** | 8 (ingress) | 7 (analytics) | (diagnostics) |
| **Cells** | ~8,425 | ~477 | <100 |
| **Transceivers** | 32× GTY | 0–4 | 0–2 |
| **BRAM** | Packet buffer | 16K+ (tables) | Minimal |
| **Purpose** | I/O + buffering | Compute | Admin |

**CDC connection:**

```
NIC FPGA (125 MHz)  →  [gray_code 2-FF]  →  Pipeline FPGA (250 MHz)
  fifo_rx packets       (dual pointers)       fifo_rx read
  tai timestamp         (counter)             tai_value
```

---

## References

- **FOUNDER_VISION.md §3** — Devices & The Backplane
- **FOUNDER_VISION.md §5** — Clock Hierarchy (multiple independent domains)
- **FOUNDER_VISION.md §14** — Next Steps (FPGA fabric design)
- **CLAUDE.md** — Emitter-first pipeline methodology
- **FPGA_DESIGN.md** — Blank template (to be specialized)
- **THREE_FPGA_SEPARATION.md** — Architecture and justification
- **FPGA_DEVICE_RESEARCH.md** — Device specs and selection
