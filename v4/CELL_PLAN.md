# V4 UNISIM Cell Transcription Plan

**Total cells:** 249  
**Status:** 2/249 complete (glbl.c, VCC.c)  
**Workflow:** /Users/bbrn/fpga-rtl/v4/BUILD.sh validates each cell  
**Enforcement:** Pre-commit hook blocks commits if validation fails

---

## Tier 1: Foundational Logic (24 cells)

**Priority:** CRITICAL — needed by all designs  
**Complexity:** LOW → MEDIUM  
**Estimated effort:** 2–3 days at 8 cells/day

### Flip-Flops (4 cells)
- [ ] **FDRE** — D flip-flop with reset (most common)
- [ ] **FDSE** — D flip-flop with set
- [ ] **FDCE** — D flip-flop with clear
- [ ] **FDPE** — D flip-flop with preset

### Lookup Tables (6 cells)
- [ ] **LUT1** — 1-input LUT (simplest)
- [ ] **LUT2** — 2-input LUT
- [ ] **LUT3** — 3-input LUT
- [ ] **LUT4** — 4-input LUT
- [ ] **LUT5** — 5-input LUT
- [ ] **LUT6** — 6-input LUT (+ SRL variants SRL16E, SRLC16E, SRLC32E)

### Carry Chain (2 cells)
- [ ] **CARRY8** — 8-bit carry chain
- [ ] **CARRY4** — 4-bit carry chain (legacy)

### Multiplexers (3 cells)
- [ ] **MUXF7** — 2:1 mux on 7-LUT pair outputs
- [ ] **MUXF8** — 2:1 mux on MUXF7 outputs
- [ ] **MUXF9** — 2:1 mux on MUXF8 outputs

### Latch (2 cells)
- [ ] **LDCE** — latch with clear
- [ ] **LDPE** — latch with preset

### Logic Primitives (4 cells)
- [ ] **AND2B1L** — 2-input AND with one inverted input
- [ ] **OR2L** — 2-input OR with both inputs inverted
- [ ] **INV** — inverter (may be trivial)
- [ ] **MUXCY** — carry multiplexer (part of carry chain)

### Gate Primitives (3 cells from existing)
- [ ] **GND** — constant low (reference: test framework)
- [x] **VCC** — constant high (existing)
- [ ] **PULLUP** — weak pull-up resistor (reference: verilog.h)

---

## Tier 2: Storage & Block RAM (8 cells)

**Priority:** HIGH — needed for design data storage  
**Complexity:** MEDIUM → HIGH  
**Estimated effort:** 3–4 days at 2 cells/day

### Block RAM Variants (4 cells)
- [ ] **RAMB36E2** — 36-Kb block RAM (dual-port)
- [ ] **RAMB18E2** — 18-Kb block RAM (dual-port)
- [ ] **FIFO36E2** — FIFO using 36-Kb RAM
- [ ] **FIFO18E2** — FIFO using 18-Kb RAM

### Distributed RAM (4 cells)
- [ ] **RAMD32** — 32×1 dual-port distributed RAM
- [ ] **RAMS32** — 32×1 single-port distributed RAM
- [ ] **RAM64X1D** — 64×1 distributed RAM
- [ ] **RAM128X1D** — 128×1 distributed RAM

---

## Tier 3: Clock & Clocking (18 cells)

**Priority:** HIGH — fundamental to all synchronous logic  
**Complexity:** HIGH  
**Estimated effort:** 5–7 days at 2–3 cells/day

### Clock Distribution (8 cells)
- [ ] **BUFG** — global clock buffer
- [ ] **BUFGCE** — clock buffer with clock enable
- [ ] **BUFGCE_DIV** — clock buffer with clock enable + divide
- [ ] **BUFR** — regional clock buffer
- [ ] **BUFIO** — I/O clock buffer
- [ ] **BUFH** — horizontal clock distribution
- [ ] **BUFMR** — multi-region clock buffer
- [ ] **BUFMRCE** — multi-region buffer with clock enable

### Transceiver Clock (2 cells)
- [ ] **BUFG_GT** — GTY clock buffer
- [ ] **BUFG_GT_SYNC** — GTY synchronized clock buffer

### Clock Sources (8 cells)
- [ ] **PLLE4_BASE** — Phase-Locked Loop (base config)
- [ ] **PLLE4_ADV** — Phase-Locked Loop (advanced config)
- [ ] **MMCME4_BASE** — Mixed-Mode Clock Manager (base)
- [ ] **MMCME4_ADV** — Mixed-Mode Clock Manager (advanced)
- [ ] **PLLE2_BASE, PLLE2_ADV** — PLL (7-series compatible)
- [ ] **MMCME2_BASE, MMCME2_ADV** — MMCM (7-series compatible)

---

## Tier 4: I/O Buffers (26 cells)

**Priority:** MEDIUM → HIGH — needed for I/O banks  
**Complexity:** MEDIUM  
**Estimated effort:** 5–7 days at 4 cells/day

### Single-Ended I/O (10 cells)
- [ ] **IBUF** — input buffer (single-ended)
- [ ] **OBUF** — output buffer (single-ended)
- [ ] **IOBUF** — bidirectional buffer
- [ ] **OBUFT** — tri-state output buffer
- [ ] **IBUFCTRL** — input buffer with control
- [ ] **IBUFE3** — input buffer (UltraScale)
- [ ] **IOBUFE3** — I/O buffer (UltraScale)
- [ ] **IBUF_IBUFDISABLE** — input buffer with disable
- [ ] **IOBUF_DCIEN** — I/O buffer with DCIEN
- [ ] **OBUFT_DCIEN** — tri-state output with DCIEN

### Differential I/O (8 cells)
- [ ] **IBUFDS** — differential input buffer
- [ ] **OBUFDS** — differential output buffer
- [ ] **IOBUFDS** — differential I/O buffer
- [ ] **OBUFTDS** — differential tri-state output
- [ ] **IBUFDSE3** — differential input (UltraScale)
- [ ] **IOBUFDSE3** — differential I/O (UltraScale)
- [ ] **IBUFDS_IBUFDISABLE** — differential with disable
- [ ] **IBUFDS_DIFF_OUT** — differential input with diff output

### I/O Control (8 cells)
- [ ] **IDDR** — input DDR register
- [ ] **ODDRE1** — output DDR register (UltraScale)
- [ ] **IDDRE1** — input DDR (UltraScale)
- [ ] **IDELAYE3** — input delay element
- [ ] **ODELAYE3** — output delay element
- [ ] **IDELAYCTRL** — delay control block
- [ ] **KEEPER** — keeper / repeater
- [ ] **PULLDOWN** — weak pull-down resistor

---

## Tier 5: Transceiver (GTY/GTX/etc.) (36 cells)

**Priority:** MEDIUM — complex, optional for many designs  
**Complexity:** VERY HIGH  
**Estimated effort:** 14–21 days at 2 cells/day  
**Note:** GTY transceivers are XCZU19EG-specific; skip GTX/GTHE variants

### GTY Transceiver (6 cells)
- [ ] **GTYE4_CHANNEL** — GTY transceiver channel
- [ ] **GTYE4_COMMON** — GTY transceiver common block
- [ ] **GTYE3_CHANNEL** — GTY (3-series variant)
- [ ] **GTYE3_COMMON** — GTY common (3-series)
- [ ] **IBUFDS_GTE4** — GTY input buffer
- [ ] **OBUFDS_GTE4** — GTY output buffer

### Other Transceiver Variants (legacy, lower priority)
- GTX (7-series): GTXE2_CHANNEL, GTXE2_COMMON
- GTHE3: GTHE3_CHANNEL, GTHE3_COMMON
- GTHE2: GTHE2_CHANNEL, GTHE2_COMMON
- GTPE2: GTPE2_CHANNEL, GTPE2_COMMON

---

## Tier 6: DSP (Digital Signal Processing) (5 cells)

**Priority:** MEDIUM — optional, project-specific  
**Complexity:** VERY HIGH  
**Estimated effort:** 7–10 days at 1 cell/day

### DSP48E2 (main)
- [ ] **DSP48E2** — 48-bit DSP slice (combined)
- [ ] **DSP_ALU** — ALU subcell
- [ ] **DSP_MULTIPLIER** — multiplier subcell
- [ ] **DSP_PREADD** — pre-adder subcell
- [ ] **DSP_OUTPUT** — output register subcell

---

## Tier 7: Configuration (14 cells)

**Priority:** LOW → MEDIUM — design & test infrastructure  
**Complexity:** LOW → MEDIUM  
**Estimated effort:** 3–4 days at 3 cells/day

### JTAG & Configuration (6 cells)
- [ ] **BSCANE2** — boundary scan cell
- [ ] **ICAPE3** — configuration port (UltraScale)
- [ ] **STARTUPE3** — startup sequence (UltraScale)
- [ ] **DNA_PORTE2** — device DNA access
- [ ] **MASTER_JTAG** — JTAG master
- [ ] **JTAG_SIME2** — JTAG simulator (sim-only)

### Frame ECC (2 cells)
- [ ] **FRAME_ECCE4** — frame ECC (UltraScale)
- [ ] **FRAME_ECCE3** — frame ECC (3-series)

### Temperature & Monitoring (6 cells)
- [ ] **SYSMONE4** — system monitor (UltraScale)
- [ ] **SYSMONE1** — system monitor (7-series)
- [ ] **XADC** — analog-to-digital converter
- [ ] **HARD_SYNC** — synchronizer
- [ ] **EFUSE_USR** — user eFuse
- [ ] **USR_ACCESSE2** — user access port

---

## Tier 8: Miscellaneous (12 cells)

**Priority:** LOW — rarely used, edge cases  
**Complexity:** LOW → MEDIUM  
**Estimated effort:** 2–3 days at 4 cells/day

- [ ] **BUF** — buffer (may be no-op)
- [ ] **AND2B1L, OR2L** — (if not in Tier 1)
- [ ] **XORCY** — XOR carry (part of arithmetic)
- [ ] **CFGLUT5** — configuration LUT
- [ ] **SIM_CONFIGE3** — simulation config (sim-only)
- [ ] **CAPTUREE2** — capture block
- [ ] **RIU_OR** — RIU OR gate
- [ ] **ZHOLD_DELAY** — hold delay
- [ ] **DIFFINBUF, DPHY_DIFFINBUF** — differential input
- [ ] **HPIO_VREF** — I/O reference voltage
- [ ] **IN_FIFO, OUT_FIFO** — FIFO buffers

---

## Tier 9: Advanced / Out-of-Scope (60+ cells)

**Priority:** VERY LOW — context-specific, deferred  
**Complexity:** VERY HIGH  
**Note:** These are PS (Processing System) or specialized domain blocks

### Processing System (PS)
- PS7, PS8 — ARM processor complex (UG1085, beyond RTL scope)

### High-Bandwidth Memory (HBM)
- HBM_ONE_STACK_INTF, HBM_TWO_STACK_INTF, etc. — memory interface (XCZU series only)

### High-Speed ADC/DAC
- HSADC, HSDAC, RFADC, RFDAC — analog interfaces (specialized)

### Serializers/Deserializers (SERDES)
- ISERDESE3, OSERDESE3 — high-speed serial (transceiver-related)

### PCI Express
- PCIE40E4, PCIE4CE4 — PCIe endpoint (very complex)

### Other Specialized
- CMAC, CMACE4 — Coherent MAC (100G Ethernet)
- VCU — H.264/H.265 codec engine
- ILKN, ILKNE4 — Interlaken interface
- URA

M288, URAM288_BASE — UltraRAM (memory type)

---

## Build Strategy

### Daily Workflow
1. Pick next cell from prioritized list (Tier 1 first)
2. Create `/v4/clib/unisims/CELLNAME.c` from `/unisim_src/verilog/src/unisims/CELLNAME.v`
3. Use verilog.h macros and components.h types
4. Run `v4/BUILD.sh` — validates compilation + component tests
5. If all pass: `git add v4/clib/unisims/CELLNAME.c && git commit`
6. Repeat

### Parallelization (Optional)
At scale (50+ cells), spawn multiple agents to transcribe cells in parallel:
- Agent 1: Tier 1 cells (Tier 1a + Tier 1b + ...)
- Agent 2: Tier 2 cells
- Agent 3: Tier 3 cells
- ...
- Each agent runs `BUILD.sh` to validate before returning
- Main loop: `git add` all validated cells and commit once per tier

### Quality Metrics
- **Compilation rate:** 100% (all cells must compile)
- **Type safety:** 100% (no type errors in C)
- **Semantic fidelity:** 100% (C transcription matches Verilog spec exactly)
- **Test coverage:** VCC test always passes (pre-commit gate)

---

## Milestones

| Milestone | Cells | Timeline | Status |
|-----------|-------|----------|--------|
| Tier 1 complete | 24 | 2–3 days | — |
| Tier 1 + 2 | 32 | 5–7 days | — |
| Tier 1–4 | 58 | 10–14 days | — |
| All Tiers 1–8 | 176 | 25–35 days | — |
| Full 249 cells | 249 | 40–50 days | — |

---

## Notes

- **Tier 5+ can be parallelized** (GTY, DSP, Config cells are mostly independent)
- **Gate primitives** (AND2B1L, OR2L, INV, etc.) may decompose to NAND in components.c
- **Simulation-only cells** (SIM_CONFIGE3, JTAG_SIME2) use `var` type for storage
- **PS/HBM/SERDES** (Tier 9) deferred until scope clarifies (not required for basic RTL)
- **Pre-commit hook** enforces quality; no commits bypass it

---

**Next action:** Start with Tier 1, cell FDRE (D flip-flop with reset).  
**Rationale:** Most fundamental; used in every synchronous design.

