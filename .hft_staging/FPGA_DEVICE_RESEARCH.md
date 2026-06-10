# FPGA Device Selection Research

**Purpose:** Reference real FPGA devices for the fpga-rtl backplane specification.

This document catalogs candidate FPGA devices suitable for the C-as-RTL HFT pipeline, with emphasis on:
- Multi-gigabit transceivers (NIC PHY)
- Dual-clock-domain architecture (MAC @ 125 MHz, Pipeline @ 250 MHz)
- Sufficient LUT/BRAM for ~9,600 cell logic + register fabric
- Industry-standard toolchains (we model C accurately; synthesize to any vendor)

---

## 1. Xilinx Virtex UltraScale+

**Relevant for:** High-end HFT deployments; datacenter integration.

### Key Specs
- **Series:** Xilinx Virtex UltraScale+ (VU+)
- **Exemplar:** VU9P (Xilinx Alveo U250 or custom)
- **LUTs:** Up to 1.16M per device
- **BRAM:** Up to 52.9 Mb per device
- **DSP:** Up to 6,840 DSP48E2 (for arithmetic, if needed)
- **Transceivers:** Up to 32× 32.75 Gbps GTY (for 40G/100G NIC)
- **Clock:** Supports independent clock domains via MMCM/PLL
- **Toolchain:** Vivado (HDL synthesis, P&R)

### Relevant for Our Model
- Dual-clock support: MAC domain (125 MHz) + Pipeline domain (250 MHz)
- 32.75 Gbps transceivers can handle 10G/25G NIC backplane at MAC rates
- BRAM abundant for register fabric + history rings (candle, footprint)
- LUT count easily covers ~10K cells logic

### References
- Xilinx Virtex UltraScale+ Product Guide (PG252)
- Alveo U250 Characterization (UG1315)

---

## 2. Intel (Altera) Stratix 10

**Relevant for:** Alternative vendor ecosystem; dual-supply strategy.

### Key Specs
- **Series:** Intel Stratix 10 (S10)
- **Exemplar:** S10-GX (datacenter SKU)
- **Adaptive Logic Modules (ALMs):** Up to 5.9M per device (≈2× LUT equivalence vs. Xilinx)
- **M20K BRAM:** Up to 2,713 (20 Kb each, 54.3 Mb total)
- **DSP:** Up to 5,888 DSP blocks (for arithmetic)
- **Transceivers:** Up to 48× 28.3 Gbps (GX) or 32× 32 Gbps (GXL)
- **Clock:** Supports independent clock networks (PLL per domain)
- **Toolchain:** Quartus Prime (HDL synthesis, P&R)

### Relevant for Our Model
- Similar multi-clock capability to Xilinx
- 28.3 Gbps transceivers suitable for 10G/25G NIC
- Abundant BRAM for register fabric
- ALM ≈ LUT, so ~10M ALM easily covers ~10K cells

### References
- Intel Stratix 10 Device Datasheet (sg-01045)
- Stratix 10 GX/SX Device Architecture Handbook (hb_s10)

---

## 3. Lattice ECP5

**Relevant for:** Cost-conscious, open-source toolchain path.

### Key Specs
- **Series:** Lattice ECP5 / ECP5-5G
- **Exemplar:** LFE5UM5G-85F (flagship, 85K LUTs)
- **LUTs:** Up to 84,480 per device
- **DPRAM:** Up to 1.6 Mb per device
- **Multipliers:** Up to 100 DSP blocks
- **Transceivers (5G model):** Up to 12× 5 Gbps (5G model)
- **Clock:** Multiple PLLs, supports independent clock domains
- **Toolchain:** Open-source (Project Trellis, nextpnr) or Lattice ispLEVER
- **Cost:** ~$500–$1,500 per part (1K volume)

### Relevant for Our Model
- LUT count sufficient for ~10K cells (well under 85K)
- Limited transceivers (5G model is 5 Gbps, not 25G), so less suitable for 25G NIC
- DPRAM smaller, but register fabric can use distributed logic if needed
- **Best for:** Prototype, simulation-in-hardware, or 1Gbps NIC only

### References
- Lattice ECP5 and ECP5-5G Family Datasheet (TN1122)
- Project Trellis (open-source bitstream documentation)

---

## 4. Xilinx Zynq UltraScale+

**Relevant for:** Mixed CPU + FPGA (control plane on ARM, data plane on FPGA).

### Key Specs
- **Series:** Xilinx Zynq UltraScale+ (ZU+)
- **Exemplar:** ZU3 (with 2× ARM Cortex-A53 cores)
- **PL (FPGA):** 150K–600K LUTs depending on SKU
- **BRAM:** 16–26.4 Mb depending on SKU
- **Transceivers:** Depends on variant (ZU19, ZU17 have GTs)
- **Integrated ARM:** Dual Cortex-A53 @ 1.2 GHz (for control-plane tasks)
- **Toolchain:** Vivado (shared with Virtex)

### Relevant for Our Model
- **Pro:** Integrated CPU (Cortex-A53) can run control-plane logic (display, config)
- **Con:** Additional complexity; C-as-RTL is already self-running (no external CPU needed)
- **Use case:** If we need an admin control plane or runtime diagnostics CPU

### References
- Xilinx Zynq UltraScale+ Datasheet (DS891)

---

## Recommended Target for Spec

### Primary: Xilinx Virtex UltraScale+ (VU9P)

**Rationale:**
1. **Industry standard** in HFT (used by trading firms, latency-sensitive workloads)
2. **Clock domains:** Dual independent clocks (MAC @ 125 MHz, Pipeline @ 250 MHz)
3. **Transceiver bandwidth:** 32.75 Gbps × 32 = sufficient for 40G/100G backplane
4. **Logic capacity:** 1.16M LUTs >> ~10K cells
5. **Memory:** 52.9 Mb BRAM >> register fabric + history rings
6. **Ecosystem:** Mature toolchain (Vivado), reference designs, tutorials

### Specification Template
This device will serve as the **reference FPGA** for the `fpga_design` module spec:
- **Device:** Xilinx Virtex UltraScale+ (VU9P or similar)
- **Package:** FCCGA1156 (standard for HBM variants)
- **Clock reference:** 156.25 MHz (10G Ethernet standard; we derive 125 MHz and 250 MHz via PLL)
- **Transceiver:** GTY (up to 32)
- **Address space:** Backplane = 64-bit word addressable (word_t = 64 bits)
- **Memory model:** 
  - BRAM: Register fabric + history rings
  - Distributed RAM: Staging buffers if needed
  - LUTs: Combinational logic (cells)

---

## Device-to-C Mapping

**Our C-as-RTL model abstracts away FPGA internals:**
- LUT ↔ Combinational cell call (`cell_and`, `cell_mux`, etc.)
- BRAM ↔ Register/memory declaration (`word_t *r`)
- Transceiver ↔ NIC PHY boundary (MAC clock domain)
- Clock domain ↔ Independent oscillator (TAI, MAC, Pipeline clocks)

**The FPGA spec document will reference VU9P specs** (LUT count, BRAM, frequency) to justify capacity, but the C model remains device-agnostic. Synthesis to Stratix 10, ECP5, or future devices is straightforward (netlist is technology-neutral).

---

## References

- **Xilinx Virtex UltraScale+ Product Guide (PG252)** — https://docs.xilinx.com/r/en-US/ug1045-ultrascale-architecture-manual
- **Intel Stratix 10 Datasheet (sg-01045)** — https://www.intel.com/content/www/us/en/programmable/publications/pdf/intel-stratix-10-device-datasheet.pdf
- **Lattice ECP5 Datasheet (TN1122)** — https://www.latticesemi.com/Products/FPGAandCPLD/ECP5
- **IEEE Std 1149.1 (JTAG)** — Industry standard for FPGA configuration
- **10G Ethernet (IEEE 802.3)** — 156.25 MHz reference clock standard
