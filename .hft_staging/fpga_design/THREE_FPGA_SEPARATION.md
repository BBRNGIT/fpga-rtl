# Three-FPGA Separation of Concerns

**Philosophy:** The C-as-RTL model is single-threaded and deterministic. But hardware deployment requires physical separation across independent devices for **clock domain isolation**, **module localization**, and **operational resilience**.

---

## Why Three FPGAs?

### Problem: Single-Device Constraints

A single FPGA running all 15 modules + 2 independent clock domains (MAC @ 125 MHz, Pipeline @ 250 MHz) faces:

1. **Clock distribution complexity**
   - Two independent oscillators physically distant
   - CDC overhead for every cross-domain signal
   - Skew management across large die

2. **Power/thermal localization**
   - NIC PHY (high-speed I/O) dissipates differently than logic
   - Ingress chain (continuous sampling) vs. Pipeline (bursty compute)
   - Single device can't optimize per-region thermals

3. **Upgrade/replacement isolation**
   - If NIC module fails, entire system fails
   - No independent scalability (can't replace just the MAC side)
   - Field replacement requires system shutdown

4. **Redundancy/failover**
   - No option for dual-NIC configuration (backup feed)
   - No geographic spread (latency SLA across POPs)

### Solution: Three Specialized Devices

Separate into 3 FPGAs, each optimized for its role:

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
                        │   (125 MHz)     │ ← Ingress chain
                        │   (Transceiver) │   (adapter → CDC FIFO)
                        └────────┬────────┘
                                 │
                                 │ CDC bridge (dual gray-code sync)
                                 │ (packet + timestamp)
                                 │
                        ┌────────▼────────┐
                        │ Pipeline FPGA   │
                        │ (250 MHz)       │ ← Analytics
                        │                 │   (DOM → indicators)
                        └────────┬────────┘
                                 │
                                 │ Shared backplane / AXI
                                 │ (read-only for control)
                                 │
                        ┌────────▼────────┐
                        │  Control FPGA   │
                        │  (Admin/Display)│ ← Diagnostics
                        │                 │   (read published regs)
                        └────────┬────────┘
                                 │
                                 │ Ethernet / UART
                                 │
                        ┌────────▼────────┐
                        │  CPU/Display    │
                        │  (TUI output)   │
                        └─────────────────┘
```

---

## Three FPGA Specializations

### 1. NIC FPGA (`fpga_nic/`)

**Role:** Ingest market data, timestamp, deduplicate.

**Clock domain:** 125 MHz MAC (primary)

**Modules included:**
- adapter (208 cells)
- wire (0 cells, passive bus)
- taiosc (5 cells)
- tai (4 cells)
- mac (5 cells)
- tai_cdc (12 cells)
- nic (180 cells)
- fifo_rx (8211 cells)

**Interfaces:**
- **Input:** Ethernet from broker (40G/100G PHY)
- **Output:** CDC FIFO packets + TAI timestamp → Pipeline FPGA

**Resource profile:**
- Transceiver-heavy (32× GTY @ 32.75 Gbps)
- BRAM for packet buffering
- Logic minimal (~410 cells logic, rest is FIFO)

**Device:** Xilinx Virtex UltraScale+ (VU9P recommended)
- Reason: Multi-gigabit transceiver count, MAC-domain optimization

**Deployment:**
- Placed near network interface / FMC connector
- Possibly on separate card (e.g., FMC daughter board with SFP+ cages)

---

### 2. Pipeline FPGA (`fpga_pipeline/`)

**Role:** Real-time market analytics, indicators, strategy prep.

**Clock domain:** 250 MHz internal (primary)

**Modules included:**
- dom (212 cells)
- candle (64 cells)
- footprint (88 cells)
- tpo (72 cells)
- timeframe (8 cells)
- fractal (15 cells)
- cbr (18 cells)

**Interfaces:**
- **Input:** CDC FIFO from NIC FPGA (packets + timestamps)
- **Output:** Published analytics registers (read by Control or external systems)

**Resource profile:**
- Logic-heavy (477 cells)
- BRAM-heavy (16K DOM table entries, 256-bar candle history, etc.)
- Compute-focused (bar accumulation, pivot detection)

**Device:** Xilinx Virtex UltraScale+ (VU9P recommended)
- Reason: Abundant BRAM (52.9 Mb), 250 MHz closure easy on this platform

**Deployment:**
- Core module, main FPGA in the system
- Hosted on carrier board (e.g., Alveo or custom)

---

### 3. Control FPGA (`fpga_control/`, future)

**Role:** Admin interface, diagnostics, display control.

**Clock domain:** CPU-synchronous (TBD, likely 100 MHz–1 GHz)

**Modules included:**
- (Read-only access to published registers from NIC + Pipeline FPGAs)
- Display driver (TUI rendering)
- Diagnostic sampler (waveform capture)
- Configuration / mode switching (future)

**Interfaces:**
- **Input:** AXI/shared-memory read from NIC + Pipeline FPGAs
- **Output:** Display signals (HDMI/DVI) or Ethernet to CPU

**Resource profile:**
- Minimal logic (<100 cells)
- Small BRAM (staging buffers only)
- I/O-focused (transceiver for display link or Ethernet)

**Device:** Could be smaller FPGA (Lattice ECP5, Artix-7) or even CPU-integrated (Zynq, embedded GPU)
- Reason: No real-time requirements, can tolerate latency

**Deployment:**
- Optional; could be omitted if diagnostics are CPU-based

---

## CDC Connectivity (NIC ↔ Pipeline)

**Two signals cross the device boundary:**

### 1. Packet FIFO (`fifo_rx`)
- **Source:** NIC FPGA (MAC domain, 125 MHz)
- **Destination:** Pipeline FPGA (Internal domain, 250 MHz)
- **Signal:** 512-bit packet (from `fifo_rx` output)
- **Synchronization:** Dual gray-code 2-FF (read and write pointers)
- **Latency:** 2–3 cycles (CDC pipeline delay)

**In NIC FPGA:**
```
write_ptr (MAC) → gray_encode → write_ptr_gray
                → FF1 → FF2 → write_ptr_gray_synced (in Internal domain)
```

**In Pipeline FPGA:**
```
read_ptr (Internal) → gray_encode → read_ptr_gray
                   → FF1 → FF2 → read_ptr_gray_synced (in MAC domain)
```

### 2. TAI Timestamp (`tai_cdc`)
- **Source:** NIC FPGA (TAI, free-running 125 MHz reference)
- **Destination:** Pipeline FPGA (read this into Internal domain)
- **Signal:** 64-bit TAI counter
- **Synchronization:** Gray-code 2-FF (on the counter, not the domain)
- **Latency:** 2 cycles

**In NIC FPGA:**
```
tai (MAC) → gray_encode → tai_gray
         → FF1 → FF2 → tai_gray_synced (in Internal domain)
         → gray_decode → tai_value (Internal domain)
```

**In Pipeline FPGA:**
```
reads tai_value from CDC register (already synchronized)
uses as timestamp for analytics
```

---

## Wiring Constraints (Blank → Specialized)

### Address Map Split

**NIC FPGA (0x0002_0000 — 0x0003_FFFF):**
```
0x0002_0000  adapter.IN / adapter.OUT
0x0002_1000  wire.* (passive)
0x0002_2000  nic.* (NIC state)
0x0002_3000  fifo_rx.WRITE_PTR, WRITE_DATA (NIC writes here)
0x0003_0000  fifo_rx.READ_PTR (synced from Pipeline, gray-coded)
0x0003_1000  tai_gray_ff1, tai_gray_ff2 (synced TAI for CDC)
```

**Pipeline FPGA (0x0004_0000 — 0x000A_FFFF):**
```
0x0003_0000  fifo_rx.READ_PTR, READ_DATA (Pipeline reads here)
0x0003_1000  tai_value (decoded TAI, ready to use)
0x0004_0000  dom.* (order book)
0x0005_0000  candle.* (bars + history)
0x0006_0000  footprint.*
0x0007_0000  tpo.*
0x0008_0000  timeframe.*
0x0009_0000  fractal.*
0x000A_0000  cbr.*
```

**Control FPGA (read-only):**
```
Mirrors NIC + Pipeline address spaces (via AXI read bus)
Publishes aggregated diagnostics registers
```

---

## Graduation & Testing

Each FPGA module follows the same emitter-first pipeline:

1. **NIC FPGA emitter** → `gen_fpga_nic_net.py` → `fpga_nic.net.json`
2. **NIC FPGA generator** → `gennet_fpga_nic.py` → `fpga_nic_gen.h` (backplane C)
3. **Validate** → `validate_fpga.py` (address overlap, clock domains, CDC specs)
4. **Gate** → `.hft_staging/gate.sh` (same 3-stage gate as module components)
5. **Graduate** → `.hft/fpga_nic/` (immutable vault copy)

Same for `fpga_pipeline/` and `fpga_control/`.

---

## Testing Strategy

### Phase 1: NIC FPGA (standalone)
- Thin test: power-on, sample prepped data, display packet counts
- Verify: fifo_rx fills correctly, gray-coded pointers, CDC timing

### Phase 2: Pipeline FPGA (with NIC FIFO mock)
- Thin test: read packets from mocked fifo_rx, execute DOM + indicators
- Verify: analytics produce expected OHLC, history rings fill

### Phase 3: Integration (both FPGAs + CDC)
- Thin test: NIC FPGA produces packets, Pipeline FPGA consumes
- Verify: End-to-end order-free execution, deterministic waveforms

### Phase 4: Control FPGA (future)
- Thin test: read analytics from Pipeline FPGA, display refresh
- Verify: Diagnostics accuracy, display latency < 100 ms

---

## Benefits of Three-FPGA Architecture

| Aspect | Single FPGA | Three FPGAs |
|--------|-------------|-------------|
| **Clock distribution** | Complex PLL, shared die | Independent, local clocks |
| **CDC overhead** | Many signals cross | Only 2 signals cross (FIFO + TAI) |
| **Thermal** | Uneven (I/O vs. logic) | Localized per device |
| **Redundancy** | Fail = system down | Fail = module down, others survive |
| **Upgrade** | Entire system | Swap one device, others online |
| **Dual-feed** | Impossible | NIC FPGA can be duplicated |
| **Latency** | Lowest (same die) | +2–3 cycles (CDC), acceptable |
| **Cost** | Lowest (1 device) | 3× cost, but operational gain |

---

## Specification Blank → Filled

This document is a **blank template** for FPGA design. As we progress through the emitter-first pipeline, we'll populate:

1. **Address allocation** → Specific register offsets for each module
2. **Clock specifications** → MMCM/PLL dividers, phase relationships
3. **CDC specifications** → Gray-code widths, sync stages, timing margins
4. **Module placement** → Floorplan constraints, I/O placement
5. **Wiring diagrams** → Bus topology, arbitration (if any)
6. **Verification checklist** → Pre-synthesis validation steps

---

## References

- **FOUNDER_VISION.md §3** — Devices & The Backplane (multi-device architecture)
- **FOUNDER_VISION.md §5** — Clock Hierarchy (independent domains)
- **FPGA_DEVICE_RESEARCH.md** — Device specifications and selection rationale
- **CLAUDE.md** — Emitter-first build pipeline (applies to FPGA too)
- **IEEE 1149.1 (JTAG)** — Multi-device synchronization via JTAG boundary scan (future)
