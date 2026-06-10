# FPGA Design: NIC

**Generated:** `gen_fpga_specialization.py`
**Date:** Auto-generated from module list
**Architecture:** C-as-RTL FPGA module assembly

---

## Device Summary

| Property | Value |
|----------|-------|
| **FPGA Name** | `nic` |
| **Primary Clock** | 125 MHz MAC clock (external_phy) |
| **Total Cells** | 8,625 |
| **Total BRAM** | 64 (36-bit words) |
| **Address Space** | 0x00000000 – 0x10000000 (256 MB) |
| **CDC Reserved** | 0x0ff00000 – 0x10000000 (1 MB) |
| **Module Count** | 8 |

---

## Modules Assigned

| Module | Clock Domain | Cells | BRAM | Address Window | Size |
|--------|--------------|-------|------|----------------|------|
| `adapter` | `mac` | 208 | 0 | 0x00000000 | 4 KB |
| `wire` | `none` | 0 | 0 | 0x00001000 | 4 KB |
| `mac` | `mac` | 5 | 0 | 0x00002000 | 4 KB |
| `taiosc` | `taiosc` | 5 | 0 | 0x00003000 | 4 KB |
| `tai` | `taiosc` | 4 | 0 | 0x00004000 | 4 KB |
| `tai_cdc` | `mac_to_internal_crossing` | 12 | 0 | 0x00005000 | 4 KB |
| `nic` | `mac` | 180 | 0 | 0x00006000 | 4 KB |
| `fifo_rx` | `mac_to_internal_crossing` | 8,211 | 64 | 0x00007000 | 144 KB |

**Total Allocated:** 0x0002b000 bytes
**Available for expansion:** 0x0fed5000 bytes

---

## Address Map

```
0x00000000  ┌─────────────────────────────────────┐
            │   Module Address Windows            │
            │                                     │
0x00000000  ├─ adapter              (0x001000) ┤
            │                                     │
0x00001000  ├─ wire                 (0x001000) ┤
            │                                     │
0x00002000  ├─ mac                  (0x001000) ┤
            │                                     │
0x00003000  ├─ taiosc               (0x001000) ┤
            │                                     │
0x00004000  ├─ tai                  (0x001000) ┤
            │                                     │
0x00005000  ├─ tai_cdc              (0x001000) ┤
            │                                     │
0x00006000  ├─ nic                  (0x001000) ┤
            │                                     │
0x00007000  ├─ fifo_rx              (0x024000) ┤
0x0ff00000  ├─────────────────────────────────────┤
            │  CDC Region (Cross-Device Crossing)  │
            │  1 MB Reserved                    │
0x10000000  └─────────────────────────────────────┘
```

---

## Clock Domains

- **mac** (125 MHz, source: external_phy)
- **mac_to_internal_crossing** (frequency: TBD)
- **none** (frequency: TBD)
- **taiosc** (1 MHz, source: oscillator)

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
