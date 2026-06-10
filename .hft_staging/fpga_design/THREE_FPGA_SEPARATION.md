# Three-FPGA Separation of Concerns (Architectural Philosophy)

**Philosophy:** Independent FPGA devices optimize for clock domain isolation, module localization, and operational resilience.

**Scope:** This document explains the architectural rationale. Implementation details (which modules go where, address allocation, wiring) belong in specialized FPGA directories (fpga_nic/, fpga_pipeline/, fpga_control/).

---

## Why Three FPGAs?

### Problem: Single-Device Constraints

A single FPGA running all modules with multiple independent clock domains faces:

1. **Clock distribution complexity**
   - Two+ independent oscillators on same die
   - CDC overhead for every cross-domain signal
   - Skew management across large device
   - PLL/MMCM contention

2. **Power/thermal localization**
   - High-speed I/O dissipates differently than logic
   - Ingress workload (continuous) vs. compute workload (bursty)
   - Single die cannot optimize per-region thermal profile
   - Hotspot risk in mixed-workload designs

3. **Upgrade/replacement isolation**
   - Single device failure = system failure
   - No independent scalability (cannot replace just one clock domain)
   - Field replacement requires full system shutdown
   - No redundancy option

4. **Redundancy and failover**
   - No option for dual-feed or backup ingress
   - No geographic spread (latency SLA across POPs)
   - Cannot isolate failures to one module set

### Solution: Three Specialized Devices

Separate into 3 independent FPGAs, each optimized for its role:

```
                        ┌─────────────────┐
                        │   Data Source   │
                        │   (Broker)      │
                        └────────┬────────┘
                                 │
                                 │ Ethernet (40G/100G)
                                 │
                        ┌────────▼────────┐
                        │   NIC FPGA      │
                        │ (Independent)   │ ← Transceiver-optimized
                        └────────┬────────┘
                                 │
                                 │ CDC bridge (gray-code sync)
                                 │ (minimal signal crossing)
                                 │
                        ┌────────▼────────┐
                        │ Pipeline FPGA   │
                        │ (Independent)   │ ← Logic/BRAM-optimized
                        └────────┬────────┘
                                 │
                                 │ AXI / Shared Memory
                                 │ (read-only for diagnostics)
                                 │
                        ┌────────▼────────┐
                        │  Control FPGA   │
                        │  (Optional)     │ ← Diagnostics/display
                        └────────┬────────┘
                                 │
                                 │ Ethernet / UART
                                 │
                        ┌────────▼────────┐
                        │  CPU / Display  │
                        │  (TUI output)   │
                        └─────────────────┘
```

---

## Three-Device Architecture

### Device 1: NIC FPGA

**Role:** Ingest high-speed data, apply timestamp, deduplicate.

**Clock domain:** Primary = independent 125 MHz MAC (or other ingress rate)

**Resource profile:**
- Transceiver-heavy (GTY lanes for 40G/100G network)
- BRAM for packet buffering
- Minimal logic (ingress pipeline only)

**Device choice:** Xilinx Virtex UltraScale+ (VU9P) recommended
- Rationale: Multi-gigabit transceiver count, suitable for 40G/100G backplane

**Deployment:** Near network interface, possibly on separate daughter card

---

### Device 2: Pipeline FPGA

**Role:** Real-time market analytics, indicators, derived metrics.

**Clock domain:** Primary = independent 250 MHz internal (or analysis rate)

**Resource profile:**
- Logic-heavy (combinational and sequential compute)
- BRAM-heavy (history rings, order books, state tables)
- Minimal transceivers (internal use only)

**Device choice:** Xilinx Virtex UltraScale+ (VU9P) recommended
- Rationale: Abundant BRAM (52.9 Mb), fast LUT capacity for 250 MHz closure

**Deployment:** Core module, main FPGA in the system

---

### Device 3: Control FPGA

**Role:** Admin interface, real-time diagnostics, display control.

**Clock domain:** CPU-synchronous (TBD, 100 MHz–1 GHz)

**Resource profile:**
- Minimal logic (<100 cells)
- Small BRAM (staging buffers)
- I/O-focused (display/network interface)

**Device choice:** Smaller FPGA or CPU-integrated option
- Lattice ECP5 (cost-effective, open-source toolchain)
- Xilinx Zynq (integrated CPU)
- Artix-7 (if I/O-optimized variant needed)

**Deployment:** Optional; diagnostics could be CPU-based instead

---

## CDC Connectivity Philosophy

**Two principles for cross-device communication:**

### 1. Minimal Signal Crossing
- **Only essential signals cross device boundary** — packet data and timestamp
- All other state remains local to each FPGA
- Reduces CDC overhead and complexity

### 2. Gray-Code Synchronization
- All cross-clock signals use gray-code synchronizers (2-FF minimum)
- Atomic clock domain crossings via phase-safe primitives
- Prevents metastability and ensures data integrity

**Generic structure (implementation-specific):**
```
NIC FPGA (domain A)  --[Gray-Code 2-FF]-->  Pipeline FPGA (domain B)
   (synchronized                                (receives stable
    pointer + data)                              synchronized value)
```

---

## Benefits of Three-Device Architecture

| Aspect | Single FPGA | Three FPGAs |
|--------|-------------|-------------|
| **Clock distribution** | Complex PLL/MMCM sharing | Independent local clocks |
| **CDC overhead** | Many signals cross domains | Only 2 signals cross (minimal) |
| **Thermal** | Uneven (I/O vs. logic hotspots) | Optimized per device |
| **Redundancy** | Device failure = system failure | Isolated failures, hot-swap possible |
| **Upgrade** | System-wide replacement | Swap one device, others stay online |
| **Scalability** | Difficult (monolithic) | Independent scaling per domain |
| **Latency** | Lowest (same die) | +2–3 CDC cycles (acceptable) |
| **Cost** | Lowest (1 device) | 3× cost, operational benefits |
| **Failure domain** | Single point of failure | Isolated, redundancy ready |

---

## Architectural Principles

1. **Independence:** Each FPGA is self-contained, operates autonomously
2. **Minimal coupling:** Only essential signals cross device boundaries
3. **Clock isolation:** Each FPGA has independent clock source
4. **CDC safety:** All cross-domain signals use synchronizers
5. **Modularity:** Devices can be upgraded/replaced independently
6. **Resilience:** Failure in one device doesn't cascade

---

## References

- **FOUNDER_VISION.md § 3** — System architecture (device separation)
- **FOUNDER_VISION.md § 5** — Clock hierarchy (independent domains)
- **FPGA_DEVICE_RESEARCH.md** — Device selection rationale
- **XILINX_VU9P_SPEC_EXTRACTION.md** — VU9P reference specs
- **FPGA_DESIGN.md** — Blank device template
- **IEEE 1149.1** — JTAG multi-device synchronization (future reference)

---

## Implementation Notes

Specific implementation details (which modules go in each FPGA, address allocation, wiring, emitter/generator tools) are documented in specialized FPGA directories:
- `fpga_nic/` — NIC FPGA specialization
- `fpga_pipeline/` — Pipeline FPGA specialization
- `fpga_control/` — Control FPGA specialization

This document provides only the architectural philosophy, not the implementation blueprint.
