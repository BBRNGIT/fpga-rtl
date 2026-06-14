# ps-realization.py — P4 PS Interface Realization

## Overview
**ps-realization.py** extracts PS-domain (Zynq UltraScale+) interface primitives from UG1085 and board pin assignments, building three outputs:

1. **ps_ports_logic.yaml** — PS interface block definitions
2. **ps_axi_seam.yaml** — PS-PL AXI interface mapping with connectivity gates
3. **catalog.json (merged)** — Existing PL primitives + new PS blocks (155 total)

## Pattern & Design

### Alignment with catalog.py
- Reads structured cached documentation (UG1085.jsonl)
- Extracts Port Descriptions tables (uniform across all PS blocks)
- Normalizes signal names: strips bus notation `[N:0]`, `<>`, whitespace
- Models each PS block as ConfigurableElement (group="PS", source="ug1085")
- Emits Verilog instantiation templates (synth-ready)

### PS Interface Coverage
Built 6 core PS interface blocks:
- **PS_CONTROL_SIGNALS** — POR, mode pins, JTAG chain, init/status (17 signals)
- **PS_DDR_CTRL** — DDR4 memory: address, data, strobe, control (17 signals)
- **PS_DP_CTRL** — DisplayPort: video/audio I/O (19 signals)
- **PS_GEM_MAC** — Gigabit Ethernet: EMIO, DMA handshake (11 signals)
- **PS_AXI_MASTER** — PS->PL master port (14 signals)
- **PS_POWER** — All supply rails: GND, VCC_* (22 signals)

**Total PS signals:** ~104 (mapped to ~378 board pins from board_net.json)

### PS-PL AXI Seam
Maps all PS-PL connectivity:
- **10 slave ports** — PL->PS access (HP0-3, HPC0-1, ACE, ACP, HPM0_LPD, LPD)
- **4 master ports** — PS->PL access (HPM0, HPM0_FPD, HPM0_LPD, HPM1_FPD)
- **Domain separation:** FPD (full-power) vs LPD (low-power) with clock-domain gates
- **Coherency rules:** ACE-Lite/ACE/ACP require snoop support; netc validates

### Connectivity Gates (for netc)
1. **width_alignment** — 32/64/128-bit port matching
2. **clock_domain_separation** — no cross-domain AXI without CDC
3. **axi_protocol_version** — HP/HPC/ACE use AXI4; LPD uses AXI4/AXI3
4. **coherency_capability** — coherent ports need snoop channels

## Usage

```bash
cd /Users/bbrn/FPGA-RTL/v3_staging/tools

# Run (auto-discovers ps_ports.json, board_net.json, catalog.json)
python3 ps-realization.py

# Outputs:
# - ps_ports_logic.yaml       (PS block inventory)
# - ps_axi_seam.yaml          (AXI interface mapping + gates)
# - catalog.json              (updated with 6 PS primitives)
```

### Optional Arguments
```bash
python3 ps-realization.py \
  --cachedir cache \
  --board board_net.json \
  --out library.json
```

## Independence & Parallelization
**ps-realization.py is independent of route.py** and can run in parallel:
- **route.py** — P3 router, routes PL nets through INT_TILE grid
- **ps-realization.py** — P4 realizer, extracts PS primitives & AXI mapping
- Both feed into **netc** (gate checker) and **integrate** (HDL backend)

## Output Files

### ps_ports_logic.yaml
```yaml
ps_blocks:
  PS_DDR_CTRL:
    ports: 17 signals
    group: PS
    source: ug1085
  # ... (6 blocks total)
```

### ps_axi_seam.yaml
```yaml
slave_ports: 10
  - name: S_AXI_HP0_FPD
    domain: FPD
    throughput: 8 GB/s
master_ports: 4
  - name: M_AXI_HPM0
    domain: FPD
    throughput: 8 GB/s
connectivity_gates: 4
  - width_alignment: ...
  - clock_domain_separation: ...
  # ... (gates for netc validation)
```

### catalog.json (updated)
```json
{
  "AND2B1L": { ... },      // existing PL primitives (149)
  "OR2L": { ... },
  "PS_DDR_CTRL": {         // new PS primitives (6)
    "name": "PS_DDR_CTRL",
    "ports": [ {...} ],
    "template": "// PS DDR Memory Controller: ...",
    "source": "ug1085",
    "group": "PS"
  },
  // ...
}
```

## Dependencies
- **ps_ports.json** — Pre-extracted PS port tables (from UG1085 parser)
- **board_net.json** — Board pin assignments to PS signals
- **catalog.json** — Existing PL primitives (merged in-place)
- **Python 3.6+** — Standard library only (json, re, sys, os, argparse)

## Standards
- Follows catalog.py port-parsing logic (tested on 149 PL primitives)
- Verilog templates match Xilinx HDL Language Template style
- Port directions: `in`, `out`, `inout`
- Signal widths inferred from UG1085 port descriptions (e.g., `PS_DDR_DQS_P[8:0]` → width 9)

## Future Extensions
1. **MIO multiplexing** — dynamic MIO pin assignment (50 pins, up to 3 peripherals/pin)
2. **PS-GTR transceivers** — PS GTH/GTY configuration (4 quads, reference clocks)
3. **USB/SATA controllers** — full port listings (not yet in ps_ports.json)
4. **PMU clock/reset routing** — PS clock domains and resets to PL (clkfab integration)

## Testing
Run with default args; outputs should match UG1085 Ch.2 (Signals/Interfaces), Ch.17 (DDR), Ch.35 (AXI):
```
  loaded 803 board connections
  built 6 PS interface blocks
  defined PS-PL AXI seam with 10 slave + 4 master ports
  loaded catalog.json (149 PL primitives)
  updated catalog.json: 6 PS primitives added (149 PL -> 155 total)
```

## See Also
- `catalog.py` — PL primitive extraction (same pattern)
- `route.py` — P3 router (parallel pipeline stage)
- UG1085 Ch.2, 17, 35 — PS architecture, DDR, AXI interfaces
- UG572 — clock architecture (future clkfab integration)
