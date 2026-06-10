# FPGA Design: PIPELINE

**Generated:** `gen_fpga_specialization.py`
**Date:** Auto-generated from module list
**Architecture:** C-as-RTL FPGA module assembly

---

## Device Summary

| Property | Value |
|----------|-------|
| **FPGA Name** | `pipeline` |
| **Primary Clock** | 250 MHz internal clock (pll_2x) |
| **Total Cells** | 1,022 |
| **Total BRAM** | 52 (36-bit words) |
| **Address Space** | 0x00000000 – 0x10000000 (256 MB) |
| **CDC Reserved** | 0x0ff00000 – 0x10000000 (1 MB) |
| **Module Count** | 14 |

---

## Modules Assigned

| Module | Clock Domain | Cells | BRAM | Address Window | Size |
|--------|--------------|-------|------|----------------|------|
| `internal` | `internal` | 5 | 0 | 0x00000000 | 4 KB |
| `timeframe` | `internal` | 8 | 0 | 0x00001000 | 4 KB |
| `dom` | `internal` | 212 | 16 | 0x00002000 | 36 KB |
| `candle` | `internal` | 64 | 4 | 0x0000b000 | 12 KB |
| `footprint` | `internal` | 88 | 4 | 0x0000e000 | 12 KB |
| `tpo` | `internal` | 72 | 4 | 0x00011000 | 12 KB |
| `fractal` | `internal` | 15 | 0 | 0x00014000 | 4 KB |
| `cbr` | `internal` | 18 | 0 | 0x00015000 | 4 KB |
| `pip_resolver` | `internal` | 20 | 0 | 0x00016000 | 4 KB |
| `strategy` | `internal` | 150 | 8 | 0x00017000 | 20 KB |
| `risk` | `internal` | 100 | 4 | 0x0001c000 | 12 KB |
| `oms` | `internal` | 120 | 8 | 0x0001f000 | 20 KB |
| `sor` | `internal` | 90 | 4 | 0x00024000 | 12 KB |
| `outbound` | `internal` | 60 | 0 | 0x00027000 | 4 KB |

**Total Allocated:** 0x00028000 bytes
**Available for expansion:** 0x0fed8000 bytes

---

## Address Map

```
0x00000000  ┌─────────────────────────────────────┐
            │   Module Address Windows            │
            │                                     │
0x00000000  ├─ internal             (0x001000) ┤
            │                                     │
0x00001000  ├─ timeframe            (0x001000) ┤
            │                                     │
0x00002000  ├─ dom                  (0x009000) ┤
            │                                     │
0x0000b000  ├─ candle               (0x003000) ┤
            │                                     │
0x0000e000  ├─ footprint            (0x003000) ┤
            │                                     │
0x00011000  ├─ tpo                  (0x003000) ┤
            │                                     │
0x00014000  ├─ fractal              (0x001000) ┤
            │                                     │
0x00015000  ├─ cbr                  (0x001000) ┤
            │                                     │
0x00016000  ├─ pip_resolver         (0x001000) ┤
            │                                     │
0x00017000  ├─ strategy             (0x005000) ┤
            │                                     │
0x0001c000  ├─ risk                 (0x003000) ┤
            │                                     │
0x0001f000  ├─ oms                  (0x005000) ┤
            │                                     │
0x00024000  ├─ sor                  (0x003000) ┤
            │                                     │
0x00027000  ├─ outbound             (0x001000) ┤
0x0ff00000  ├─────────────────────────────────────┤
            │  CDC Region (Cross-Device Crossing)  │
            │  1 MB Reserved                    │
0x10000000  └─────────────────────────────────────┘
```

---

## Clock Domains

- **internal** (250 MHz, source: pll_2x)

---

## Cross-Device CDC Connections

**Reserved region:** 0x0ff00000 – 0x10000000 (1 MB)

This region holds:
- Gray-code CDC FIFOs for cross-device signals
- Synchronization flip-flops (2-FF minimum latency per crossing)
- Explicit route definition (no implicit wiring)

---

## Design Constraints & Validation

- **Single-Writer Law:** Each register written by exactly one module
- **Gate-Level Logic:** All data-path arithmetic via structural cells (`cell_addsub`, `cell_mux`, etc.)
- **Branchless Device:** No `if`/`switch`/`?:` in generated tick
- **Immutability:** Once graduated to `.hft/`, module sources are write-once
- **Address Alignment:** All module windows aligned to 0x1000 boundaries

---

## Next Steps

1. **Review address map** — Confirm no collisions, adequate space per module
2. **Define cross-device routes** — Which signals cross CDC regions?
3. **Implement module emitters** — Generate `gen_<module>_net.py` per module
4. **Generate netlists** — Run `python3 gen_<module>_net.py > <module>.net.json`
5. **Validate netlists** — Run `python3 validate.py <module>.net.json`
6. **Generate device C** — Run `python3 gennet.py <module>.net.json > <module>_gen.h`
7. **Build & test** — Compile and verify each module
8. **Graduate** — Run `graduate.sh <module>` to move to `.hft/`

---

## References

- **FOUNDER_VISION.md** — Canonical architecture reference
- **CLAUDE.md** — Project instructions and common commands
- **Module netlists** — See each module's `<module>.net.json` for exact register/cell layout
