# FPGA Design Module (Blank Template)

**Status:** Blank reference specification for Xilinx VU9P device.

**Purpose:** Provide device-level reference information only. This is NOT an implementation document.

**Important:** Module placement, specific address allocation, and wiring belong in specialized implementations (e.g., `fpga_nic/`, `fpga_pipeline/`, `fpga_control/`), NOT here.

---

## Device Reference

### Target Device

**Xilinx Virtex UltraScale+ (VU9P)**
- **Part number:** xcvu9p-flga2104-2L
- **Package:** FCCGA1156
- **Speed grade:** -2
- **Architecture:** UltraScale+

### Key Specifications

| Resource | Count | Details |
|----------|-------|---------|
| CLBs | 182,400 | Configurable Logic Blocks |
| LUTs | 1,457,600 | 6-input look-up tables |
| Flip-flops | 2,918,400 | Total FFs (182.4K CLBs × 16 FFs/CLB) |
| BRAM36 | 2,160 | 36 Kb blocks (77.76 Mb total) |
| DSP48E2 | 6,840 | 48-bit arithmetic blocks |
| CMTs | 6 | Clock Management Tiles (MMCM + PLL) |
| GTY Transceivers | 32 | Up to 32.75 Gbps per lane |
| I/O Banks | 44 | Standard and high-speed |

**Total addressable connections:** ~99.2 million (from XILINX_VU9P_SPEC_EXTRACTION.md)

---

## Address Map Template (Blank)

This is a generic outline. Specialization fills in actual allocations.

```
Backplane Address Space (word_t = 64-bit)

0x0000_0000 — 0x0000_FFFF  Reserved / Boot / Config
0x0001_0000 — 0x0001_FFFF  [Clock domain region]
0x0002_0000 — 0x0002_FFFF  [Device-specific region A]
0x0003_0000 — 0x0003_FFFF  [Device-specific region B]
0x0004_0000 — 0x000F_FFFF  [Device-specific region C]
0x0010_0000 — 0x00FF_FFFF  [Expansion / Future]

Total addressable: 256 MWords × 64 bits = 2 GB
Typical utilization: ~10 MB for logic + BRAM allocation
```

---

## Clock Domains (Template)

Generic template for independent clock sources:

### Primary Clock Domain
- **Purpose:** [to be defined by implementation]
- **Frequency:** [to be defined]
- **Source:** MMCM/PLL from reference (configuration TBD)
- **Properties:** Free-running, independent of other domains

### Secondary Clock Domain (if needed)
- **Purpose:** [to be defined by implementation]
- **Frequency:** [to be defined]
- **Source:** MMCM/PLL from reference (configuration TBD)
- **Properties:** Free-running, independent of primary domain

### Clock Distribution
- **Source:** Reference clock input (156.25 MHz typical)
- **Distribution:** Via global clock buffers (BUFG, BUFGCTRL)
- **CDC:** Any cross-domain signals use gray-code synchronizers

---

## Module Placement (Template, NOT IMPLEMENTATION)

**This section is a placeholder structure only. Actual module assignment belongs in specialized FPGA implementations.**

Generic placement structure:
```
┌─────────────────────────────────────┐
│     FPGA Device (Xilinx VU9P)       │
├─────────────────────────────────────┤
│  Block RAM (register fabric)        │
│  - Address allocation: [TBD]        │
│  - Modules: [TBD by implementation] │
├─────────────────────────────────────┤
│  Logic (combinational + sequential) │
│  - Cell allocation: [TBD]           │
│  - Modules: [TBD by implementation] │
├─────────────────────────────────────┤
│  Transceivers (GTY, high-speed I/O) │
│  - Allocation: [TBD by impl]        │
│  - Purpose: [TBD by implementation] │
└─────────────────────────────────────┘
```

---

## Resource Budget (VU9P Reference)

| Resource | Total | Typical Usage | Available |
|----------|-------|---------------|-----------|
| LUTs | 1,457,600 | ~10,000 cells | 1,447,600 |
| BRAM36 | 2,160 | ~50–100 | 2,060–2,110 |
| DSP48E2 | 6,840 | 0 (current design) | 6,840 |
| GTY transceivers | 32 | ~8 (depends on impl) | ~24 |
| I/O banks | 44 | ~10 (depends on impl) | ~34 |

**Conclusion:** VU9P has abundant headroom for diverse implementations.

---

## Design Flow (Generic)

1. **Reference selection** → Xilinx Virtex UltraScale+ (VU9P)
2. **Clock source** → 156.25 MHz external oscillator
3. **MMCM/PLL configuration** → Derive primary + secondary domains [per implementation]
4. **Address allocation** → Assign register windows [per implementation]
5. **Module instantiation** → Include [per implementation]
6. **Wiring** → Connect module outputs to inputs [per implementation]
7. **CDC specification** → If cross-domain, gray-code synchronizers [per implementation]
8. **Synthesis** → Vivado flow (technology-specific)
9. **Validation** → Gate stage validates netlist and resource constraints
10. **Graduation** → Immutable vault copy

---

## References

- **XILINX_VU9P_SPEC_EXTRACTION.md** — Complete device specification (parts, connections, ~99.2M total)
- **FPGA_DEVICE_RESEARCH.md** — Device selection rationale (VU9P, alternatives)
- **THREE_FPGA_SEPARATION.md** — Architecture philosophy (why 3 separate devices)
- **CLAUDE.md** — Build methodology (emitter-first pipeline applies to FPGA implementations)
- **FOUNDER_VISION.md § 3, 5, 14** — System architecture and FPGA role

---

## Next Steps (Specialization)

This blank template will be **cloned and specialized** into concrete FPGA implementations:

1. **fpga_nic/** — Specialize for NIC FPGA (MAC domain, transceiver-heavy)
2. **fpga_pipeline/** — Specialize for Pipeline FPGA (internal domain, logic-heavy)
3. **fpga_control/** — Specialize for Control FPGA (future, diagnostics)

Each specialization will document:
- Specific module list
- Address allocation and wiring
- Clock domain configuration
- CDC specifications (if any)
- Emitter/generator/validator tools
- Gate and graduation steps

**Specialization docs are separate** from this blank template. Do not mix device specs with implementation details.
