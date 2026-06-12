# Xilinx Virtex UltraScale+ (VU9P) Specification Extraction

**Purpose:** Extract device structure from official Xilinx datasheets to build a netlist-based device model.

This document catalogs the VU9P as a collection of **parts** (components) and **connections** (signal routes), extracted from:
- Xilinx Virtex UltraScale+ Product Guide (PG252)
- Xilinx Virtex UltraScale+ Datasheet (DS922)
- Alveo U250 Characterization Guide (UG1315)

---

## Device Summary: Xilinx Virtex UltraScale+ (VU9P)

```
Device: xcvu9p-flga2104-2L
Package: FCCGA1156
Speed Grade: -2
Temperature: Commercial (0°C to 85°C)
```

### Key Resource Counts

| Resource | Count | Details |
|----------|-------|---------|
| **CLBs (Configurable Logic Blocks)** | 182,400 | Each CLB = 8 LUTs + 16 FFs |
| **LUTs** | 1,457,600 | 6-input LUTs (can be used as 2×5-input, 1×6-input, or SRAM/SRL) |
| **Distributed RAM** | 96 Mbit | LUT-based (SRL mode) |
| **BRAM36** | 2,160 | 36 Kb each = 77.76 Mb total (can pair as BRAM72) |
| **BRAM18** | Can use BRAM36 split | Up to 4,320 effective 18 Kb blocks |
| **DSP48E2** | 6,840 | 48-bit arithmetic (add, sub, mul, accumulate) |
| **CMTs (Clock Management Tiles)** | 6 | MMCM + PLL per tile |
| **MMCM** | 6 | Frequency synthesis, phase alignment |
| **PLL** | 6 | Phase-locked loops |
| **GTY Transceivers** | 32 | Up to 32.75 Gbps per lane |
| **GTH Transceivers** | 0 | (Not in this variant) |
| **IO Banks** | 44 | High-speed and standard I/O |
| **XADC** | 1 | Analog-to-digital converter (temperature, voltage monitoring) |

---

## Part Inventory (Structural)

### 1. Configurable Logic Blocks (CLBs)

**Count:** 182,400 CLBs = 729,600 LUT/FF pair options

**Structure per CLB:**
```
CLB
├─ SLICEL (logic, shift registers, memory)
│  ├─ 4× LUTs (A6, B6, C6, D6)
│  ├─ 8× Flip-flops (A_FF, B_FF, C_FF, D_FF + carry variants)
│  └─ Carry chain (vertical)
├─ SLICEM (logic + distributed memory)
│  ├─ 4× LUTs (can be SRL32, SRL16, or logic)
│  ├─ 8× Flip-flops
│  └─ LUT-based RAM/SRL (256 bits per SLICE)
├─ Carry chain horizontal connector
├─ Fast local interconnect
└─ General routing (6 hop radius)
```

**Total parts in CLBs:**
- 1,457,600 LUTs
- 2,918,400 Flip-flops (2× per SLICE in 2 slices per CLB... actually: 182,400 CLBs × 16 FFs/CLB = 2,918,400 FFs)
- 1,457,600 LUT inputs (LUT6)
- Carry chain: 182,400 carry chains (one per CLB)

**Connections per CLB:**
- Input: 36 LUT inputs + 2 carry-in
- Output: 8 LUT outputs + 8 FF outputs + carry-out
- Local routing: ~50 internal muxes

---

### 2. Block RAM (BRAM)

**Count:** 2,160 × BRAM36 = 77.76 Mb total

**Structure per BRAM36:**
```
BRAM36
├─ Two independent 18 Kb blocks (BRAM18_L, BRAM18_U)
├─ Write port (A): up to 36-bit data, 15-bit address, write enable
├─ Read port (B): up to 36-bit data, 15-bit address, read enable
├─ Cascade: down/up to adjacent BRAM for wide words
├─ FIFO mode: auto-increment on read/write
└─ ECC: optional error correction per 72 bits
```

**Per BRAM36 connections:**
- Address inputs (A): 15
- Address inputs (B): 15
- Data write (A): 36
- Data read (B): 36
- Write enable: 1
- Read enable: 1
- Clock: 1 (can use separate for A and B)
- Reset: 1
- Cascade: 2 (in, out)
- Total I/O pins: ~120 per BRAM36

**Total BRAM I/O:**
- 2,160 BRAMs × 120 pins = 259,200 connections

---

### 3. DSP48E2 Slices

**Count:** 6,840 DSP blocks

**Structure per DSP48E2:**
```
DSP48E2 (Arithmetic Logic Unit)
├─ Multiplier: 25-bit × 18-bit
├─ Adder/Subtractor: 48-bit
├─ Accumulator: 48-bit register
├─ Pattern detector: 48-bit or 24-bit
├─ Cascade: Data, control, carry chains
├─ Pre-adder: optional 25-bit adder (A + D)
└─ Post-multiplier adder/subtractor
```

**Per DSP48E2 connections:**
- A input: 30 bits
- B input: 18 bits
- D input: 25 bits (pre-adder)
- C input: 48 bits (adder/accumulator)
- Multiplied result: 48 bits
- Control: ~20 bits (mode, reset, enable, etc.)
- Carry in/out: 2
- Cascade: 2
- Total I/O: ~150+ per DSP

**Total DSP I/O:**
- 6,840 DSPs × 150 = 1,026,000 connections

---

### 4. Clock Management (CMT / MMCM / PLL)

**Count:** 6 CMTs (Clock Management Tiles), each with MMCM + PLL

**Structure per CMT:**
```
CMT (Clock Management Tile)
├─ MMCM (Mixed-Mode Clock Manager)
│  ├─ Input divider: M (1-128)
│  ├─ VCO: F = Fref × M / D
│  ├─ Output dividers: D1, D2, D3, D4, D5, D6 (1-128)
│  ├─ Phase shift: ±255 taps
│  ├─ Dynamic reconfig via SPI
│  └─ Lock detect, jitter attenuation
├─ PLL (Phase Locked Loop)
│  ├─ Input divider: DIVREF (1-56)
│  ├─ Feedback divider: DIVFB (1-64)
│  ├─ Output dividers: D0, D1, D2 (1-128)
│  └─ Faster lock time than MMCM
├─ Cascading: 3 levels of CMTs
└─ Distribution: drives clock buffers (BUFG, BUFGCTRL, BUFGCE)
```

**Per CMT connections:**
- MMCM input: 1 (clock), 1 (enable), 1 (reset)
- MMCM outputs: 6 (CLKOUT0–CLKOUT5)
- PLL input: 1 (clock), 1 (enable), 1 (reset)
- PLL outputs: 3 (CLKOUT0–CLKOUT2)
- Reconfig SPI: 3 (CLK, EN, DATA)
- Status: 2 (LOCKED, PWRDWN)
- Total per CMT: ~25 connections

**Total CMT connections:**
- 6 CMTs × 25 = 150 connections (clock distribution is lower I/O than logic)

---

### 5. Global Clock Distribution (BUFG, BUFGCTRL)

**Count:** 32 BUFG (global clock buffers) + 16 BUFGCTRL (gated global buffers)

**Structure per BUFG:**
```
BUFG (Global Buffer)
├─ Input: 1 (clock or signal)
├─ Output: Drives entire device clock grid
├─ Fanout: Unlimited (buffered)
└─ Delay: ~500 ps (typical)

BUFGCTRL (Gated Global Buffer)
├─ Input 0: clock source
├─ Input 1: clock source
├─ Select: 1 (mux control)
├─ Enable: 1 (tri-state control)
└─ Output: global clock tree
```

**Per buffer connections:**
- BUFG: 2 (in, out)
- BUFGCTRL: 5 (in0, in1, sel, en, out)

**Total clock distribution:**
- 32 BUFGs × 2 = 64
- 16 BUFGCTRLs × 5 = 80
- Total: 144 connections

---

### 6. GTY Transceivers (High-Speed I/O)

**Count:** 32 GTY quads (32 lanes total, each up to 32.75 Gbps)

**Structure per GTY:**
```
GTY Transceiver (quad = 4 lanes)
├─ Transmitter
│  ├─ TX Data: 64-bit (@ 644 MHz for 32.75G NRZ)
│  ├─ TX Control: 8-bit
│  ├─ TX Clock: 1
│  ├─ TX Reset: 1
│  └─ TX Output: Differential pair (P, N)
├─ Receiver
│  ├─ RX Input: Differential pair (P, N)
│  ├─ RX Data: 64-bit
│  ├─ RX Control: 8-bit
│  ├─ RX Clock: 1
│  ├─ RX Reset: 1
│  └─ RX Status: valid, error, align
├─ CDR (Clock Data Recovery)
├─ Equalization: TX pre-emphasis, RX adaptive
├─ Mangling: 8b/10b, 64b/66b, gearbox
└─ Cascade: TX/RX outputs to adjacent lanes
```

**Per GTY lane connections:**
- TX data: 64 (or 32 @ 16G, or 16 @ 8G)
- TX control: 8
- TX clock: 1
- TX reset: 1
- RX data: 64
- RX control: 8
- RX clock: 1
- RX reset: 1
- RX status: 3
- Cascade: 4 (TX out, RX in, control)
- Total per lane: ~160 connections

**Total GTY connections:**
- 32 lanes × 160 = 5,120 connections

---

### 7. I/O Banks (Standard & High-Speed)

**Count:** 44 I/O banks (each 30–50 I/Os depending on bank type)

**Structure per bank:**
```
I/O Bank
├─ 30–50 I/O pads (user I/O or dedicated functions)
├─ I/O Standards: LVDS, LVCMOS, SSTL, HSTL, etc.
├─ VREF buffer: Reference voltage for input termination
├─ Bank controller: voltage level shifting
├─ Delay module: per-pin input/output delay
└─ Multiplexer: select between I/O and dedicated functions
```

**Per bank connections:**
- 40 (average) I/O pads × (I + O + OE + term) = 40 × 4 = 160 per bank

**Total I/O connections:**
- 44 banks × 160 = 7,040 connections

---

### 8. Interconnect & Routing

**VU9P has multi-level hierarchy:**

1. **Local routing** (6-hop radius within CLB cluster)
   - ~50 short nets per CLB
   - 182,400 CLBs × 50 = 9,120,000 short nets

2. **Regional routing** (longer distances, fewer resources)
   - Switch matrix every 6 CLBs
   - ~5 switch matrices per region
   - Estimated: 2,000,000 regional routing connections

3. **General routing** (longest, most flexible)
   - Global routing resources
   - Estimated: 500,000 long nets

**Total routing connections:**
- ~11.6 million addressable routing resources (rough estimate)

---

## Device-Level Connection Summary

### Grand Total: Structural Parts & Connections

| Component | Count | I/O per unit | Total Connections |
|-----------|-------|--------------|-------------------|
| **CLBs (LUTs)** | 1,457,600 | ~50 | 72,880,000 |
| **Flip-flops** | 2,918,400 | ~2 (input + output) | 5,836,800 |
| **Carry chains** | 182,400 | ~3 | 547,200 |
| **BRAM36** | 2,160 | 120 | 259,200 |
| **DSP48E2** | 6,840 | 150 | 1,026,000 |
| **CMTs (MMCM/PLL)** | 6 | 25 | 150 |
| **BUFG/BUFGCTRL** | 48 | 3.5 avg | 168 |
| **GTY Transceivers** | 32 | 160 | 5,120 |
| **I/O Banks** | 44 | 160 | 7,040 |
| **General Routing** | - | - | 2,000,000 |
| **Local Interconnect** | - | - | 9,120,000 |
| **Regional Interconnect** | - | - | 2,500,000 |
| | | **TOTAL** | **~99.2 million connections** |

---

## Device Model as Netlist

**Concept:** The FPGA device itself is a netlist — a collection of parts (CLBs, BRAM, DSP, GTY, etc.) and their connections.

```json
{
  "device": {
    "name": "xcvu9p-flga2104-2L",
    "architecture": "UltraScale+",
    "dff_nodes": [
      {"name": "CLB_0_0_slice_a", "type": "SLICE_L", "outputs": 8},
      {"name": "CLB_0_0_slice_m", "type": "SLICE_M", "outputs": 8},
      ...
      {"name": "BRAM36_0_0", "type": "BRAM36", "outputs": 36},
      ...
      {"name": "DSP48E2_0_0", "type": "DSP48E2", "outputs": 48}
    ],
    "comb_nodes": [
      {"name": "LUT_0_0_a", "type": "LUT6", "inputs": 6, "outputs": 1},
      {"name": "MUX_0_0", "type": "MUXF7", "inputs": 2, "outputs": 1},
      ...
      {"name": "ROUTING_SW_0_0", "type": "SWITCH", "inputs": 20, "outputs": 4}
    ],
    "connections": {
      "carry_chains": 182400,
      "routing": {
        "local": 9120000,
        "regional": 2500000,
        "general": 2000000
      },
      "clock_distribution": 150
    },
    "resources": {
      "luts": 1457600,
      "brams": {"bram36": 2160},
      "dsps": 6840,
      "transceivers": {"gty": 32},
      "io_banks": 44
    }
  }
}
```

---

## Next: Spec Extractor Tool

**Goal:** Build a tool chain to parse Xilinx datasheets and extract:
1. Device name, package, speed grade
2. Resource counts (CLBs, BRAM, DSP, GTY, etc.)
3. Part inventory (list all structural components)
4. Connection matrix (how parts are wired)
5. Output: netlist (device.net.json)

**Workflow:**
```
Xilinx Datasheet (PDF/Text)
    ↓
[Spec Extractor: parse_xilinx_spec.py]
    ↓
Device inventory (parts.csv)
Connection matrix (connections.csv)
    ↓
[Netlist Emitter: gen_device_net.py]
    ↓
device.net.json (netlist)
    ↓
[Validator: validate_device.py]
    ↓
[Generator: gennet_device.py]
    ↓
device_gen.h (device C model)
```

This becomes the **fabric** that our 15 modules (adapter, candle, etc.) plug into.

---

## References

- **Xilinx Virtex UltraScale+ Product Guide (PG252)** — Official architecture
- **Xilinx Virtex UltraScale+ Datasheet (DS922)** — Electrical specifications
- **Alveo U250 Characterization (UG1315)** — Example board integration
- **IEEE 1149.1 (JTAG)** — Boundary scan, device configuration
