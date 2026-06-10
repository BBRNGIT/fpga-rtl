# Corrections: My Diagrams vs. Founder Spec (ARCHITECTURE.md)

## Critical Discrepancies & Assumption Fixes

### 1. ❌ MAJOR: Clock Sequencing Model (CLK_DEP_TABLE)

**My diagrams show:** Explicit sequence-ordered dispatch (seq 0–11) with module-specific execution times.

**Founder's intent (§4, §11.9):** 
> "Order-independence is what deletes the manual wiring... all cross-module communication is **registered** (one clock per hop, like a real pipeline). Every block reads the previous cycle's frozen state → **evaluation order is irrelevant** → run the blocks in any order each tick, identical result."

**Correction:** The CLK_DEP_TABLE is a **known disease** (§11.9: "Manual wiring — `CLK_DEP_TABLE` + hardcoded 26-call dispatch"). In the **corrected target**, all modules:
- Read from **registered outputs** (prior cycle's WRITE phase)
- Compute combinationally
- Write their outputs (registered on this cycle's rising edge)

**No sequence table should exist.** Modules can execute in **any order** each tick and produce identical results because all inputs are frozen (one cycle behind).

**Impact on my diagrams:**
- ❌ Seq 0–11 dispatch is a temporary workaround, not the target
- ✓ The data flow (who reads from whom) is correct
- ✓ The 4 ns per-cycle is correct
- ❌ The sequencing **adds hidden latency** — in the corrected model, most modules run in **parallel** with 1-cycle registered latency between producer and consumer

**Fix:** Reframe operational flow as **order-free, fully pipelined** — not sequence-ordered. Example:
```
Tick N:
  All modules READ (prior tick's outputs)      [parallel]
  All modules COMPUTE (combinational)          [parallel]
  All modules WRITE (latch results)            [parallel]
  
Result: Every module → next module sees output 1 cycle later (registered hop).
All modules execute in parallel; order doesn't matter.
```

---

### 2. ❌ MAJOR: TAI Clock Model (Independent References vs. Synchronized)

**My diagrams show:** TAI and MAC as independent free-running oscillators, both incrementing, later synchronized via CDC.

**Founder's intent (§5a, §11.2):**
> "Independent references drift; synchronizers protect that... multiple clock domains — NIC/MAC (125 MHz), pipeline/FPGA (250 MHz), CPU, GPU — each derived from a stable reference, crossing via CDC."

> "Our deterministic model: Derive every domain's clock from one simulation time base (so the sim is reproducible) **while explicitly modeling the CDC** between domains."

**Correction:** 
- ✓ Independent clock domains (MAC, pipeline, CPU, GPU) is correct
- ✓ CDC 2-FF synchronizers at boundaries is correct
- ❌ **BUT:** In the simulator (not real hardware), we use **one deterministic time base** that all clocks derive from, to keep runs reproducible
- ✓ **Real hardware:** TAI and MAC are truly independent oscillators with ppm drift; CDC exists because they can tear

**In simulation:**
- One master simulation clock drives all three domains
- TAI oscillator = deterministic counter (no drift modeling)
- MAC clock = deterministic counter (no drift modeling)
- CDC still exists (explicitly modeled) but synchronizes bit-exact copies, never metastability

**In real hardware (eventual FPGA build):**
- TAI = GNSS PLL output (external reference, stable, high precision)
- MAC = NIC PHY clock (external, from broker, possibly drifting)
- CDC handles the independent references and metastability

**Impact:** My diagram's "free-running independent oscillators" is correct for **FPGA deployment**, but in simulation we should add a note that one deterministic master drives all for reproducibility.

---

### 3. ❌ MAJOR: Backplane Architecture (Flat Modules vs. Device Hierarchy)

**My diagram shows:** 15 flat modules on backplane, indexed by address.

**Founder's intent (§3, §11.5):**
> "Hierarchy (intended end-state): only the **devices** explicitly live on the backplane; each device's **modules wire *into* the device** (registers nested inside the device's reserved region)... The backplane is a **device map, not a module map**."

> "The known corruption: a prior AI did the *inverse* — it exploded the backplane into a **mini-backplane file per module** (the 14 `backplane_*.h` sub-headers), keeping every module flat on the backplane, just split across files. That is fragmentation, not structure."

**Correction:** The **target architecture** is:
```
┌─────────────────────────────────────────────┐
│ BACKPLANE (device map, 3–4 entries)         │
├─────────────────────────────────────────────┤
│ 0x1000000 — NIC FPGA                        │
│   ├─ adapter (0x1700000–0x17XXXXX)          │
│   ├─ wire (0x1700000 relay lanes)           │
│   ├─ mac (0x1D00000)                        │
│   ├─ tai (0x1C00000)                        │
│   ├─ taiosc (0x1B00000)                     │
│   ├─ tai_cdc (0x1F00000)                    │
│   └─ nic (0x1A00000)                        │
├─────────────────────────────────────────────┤
│ 0x2000000 — Pipeline FPGA                   │
│   ├─ dom (0x2100000)                        │
│   ├─ candle (0x2200000)                     │
│   ├─ footprint (0x2300000)                  │
│   ├─ tpo (0x2400000)                        │
│   ├─ fractal (0x2450000)                    │
│   ├─ cbr (0x2460000)                        │
│   ├─ timeframe (0x1E80000)                  │
│   ├─ pip_resolver (0x2480000)               │
│   ├─ strategy (TBD)                         │
│   ├─ risk (TBD)                             │
│   ├─ OMS (TBD)                              │
│   ├─ SOR (TBD)                              │
│   └─ outbound (TBD)                         │
├─────────────────────────────────────────────┤
│ 0x3000000 — CPU (host control)              │
├─────────────────────────────────────────────┤
│ 0x4000000 — GPU (display device, TUI host)  │
└─────────────────────────────────────────────┘
```

**Impact:** Current code is fragmented (14 subheaders). The corrected target is a **3–4 device entry table**, with modules nested inside. This is a **refactor-scope decision** (delete-and-redesign vs. incremental).

---

### 4. ⚠️ MAJOR: Adapter-Wire-NIC Chain (Not Direct Pipe)

**My diagram shows:** Adapter → wire relay → NIC.

**Founder's intent (§6):**
> "The chain is: **data provider → adapter → wire → port pins → NIC PHY → NIC/MAC**... The adapter sits BEFORE the wire, between the data provider and the wire. Its job: take provider data and **put it on the wire** (serialize into the PHY frame) and drive the port."

> "*(The recurring AI error is a 'straight pipe to the NIC' that skips the adapter, the wire, and the port. That has caused hell.)*"

**Correction:** ✓ My diagram is **correct here**. The flow is:
1. Adapter reads external data (CSV, broker stream)
2. Adapter formats into proprietary PHY frame (bid/ask/qty/side/framing)
3. Adapter writes to wire relay lanes
4. NIC reads wire (sampled input pins)
5. NIC processes (dedup, CDC, timestamp)
6. NIC outputs to FIFO_RX

**No direct pipe.** Wire is a **passive relay**, not active forwarding.

---

### 5. ⚠️ DATA LAW: Bid/Ask Explicitly, No Combined Metrics

**My operational flow example shows:** DOM updating bid/ask separately, candle reading bid/ask prices. ✓

**Founder's intent (§7):**
> "There is no 'price.' There is bid price and ask price, always, explicitly labeled... No combined metrics as decision inputs. No mid price as a decision basis... Every price-bearing field, register, and decision states **bid or ask explicitly**."

**Correction:** ✓ My diagrams respect this. But need to **flag violations in current code**:
- ❌ Candle currently reads DOM's blended "last-trade price" (should tap bid/ask stream directly) — §11.7
- ❌ Strategy may use mid price (§7: allowed only as non-blocking convenience, never a decision gate)

---

### 6. ⚠️ MAJOR: Timeframe (Reference, Not Master; Per-Module Multiples)

**My operational flow shows:** Single shared timeframe, TF_BAR_CLOSED pulse, all indicators triggered by bar boundary.

**Founder's intent (§8, §11.8):**
> "Timeframe is a **reference** bar clock... But modules are NOT slaved to it. Each bar module carries **its own multiple** of the base timeframe (e.g. candle on 2×, footprint on 0.5×) in its **own period register**, and closes its own bars accordingly."

> "Current code disease: **Timeframe is a single shared bar clock; per-module multiples not yet supported** (§11.8)."

**Correction:** ❌ My operational flow wrongly shows **all indicators closing bars on the same TF_BAR_CLOSED pulse**.

**Corrected model:**
```
TIMEFRAME module:
  ├─ Base period (e.g. 1 second @ 250 MHz = 250M cycles)
  └─ Emits: TF_BASE_CLOSED (pulse every base period)

Each indicator carries its own multiplier:
  CANDLE:     period = BASE_PERIOD × 2  (2-second bars)
  FOOTPRINT:  period = BASE_PERIOD × 1  (1-second bars)
  TPO:        period = BASE_PERIOD × 4  (4-second bars)
  CBR:        period = BASE_PERIOD × 1  (1-second bars)

Each indicator independently tracks its own bar-counter:
  if (internal_clock % (BASE_PERIOD × multiplier)) == 0:
    close_bar()
```

**Impact:** My diagrams show **tight coupling to a single timeframe pulse**. Corrected model has **loose coupling** — each module independently decides its bar boundary.

---

### 7. ⚠️ Display Architecture (Non-Blocking, Async)

**My diagram shows:** Display lanes (raw register reads, non-blocking, asynchronous).

**Founder's intent (§10):**
> "The system exposes raw register data on a **'display out'**; rendering happens **outside**, on the **GPU device** (its own clock domain, no compute, the home of the TUIs). No host threads, no timing coupling. Display refresh must NOT be tied to the clock or to the market-data rate."

**Correction:** ✓ My display lanes model is **correct**. The GPU is:
- A separate device (own clock domain)
- Read-only (samples display_out registers)
- Asynchronous (no blocking, no feedback to pipeline)
- Hosts TUI rendering (no computation inside the HFT pipeline)

---

### 8. ⚠️ Current Code Diseases to Remediate (§11)

**My diagrams don't show these, but they exist in the codebase:**

1. **sim_feed_loop** — replay harness fused into device, orphaned crystal
   - *Correction:* Device boots from `clock_gen_run()` (free-running crystal), NOT sim_feed
   
2. **TAI fast-forward** from feed timestamps
   - *Correction:* TAI disciplined only off reference (GNSS/PPS PI loop in `time_source`)
   
3. **Ghost values** — `is_buy/is_sell/is_trade` inferred from price movement
   - *Correction:* Operate on actual `bid_qty/ask_qty` registers, never infer sides
   - *Status:* Partially fixed in `tick_adapter` and `footprint`, but may still exist elsewhere
   
4. **Replay concepts in device map** — `FEED_SOURCE_TYPE_REG`, `FEED_SYN_*`, `SIM_PACER_*`
   - *Correction:* Remove all replay/testbench registers from backplane
   
5. **Backplane fragmentation** — 14 per-module subheaders instead of device hierarchy
   - *Correction:* Restructure into 3–4 device-level entries
   
6. **Host-thread display** — SDL/libusb/pthread entangled with device
   - *Correction:* All rendering outside device (GPU device), no threads inside
   
7. **Candle reads DOM blended price**
   - *Correction:* Tap **bid/ask stream directly** from wire/adapter, not from DOM
   
8. **Timeframe single shared clock**
   - *Correction:* Per-module multipliers (each module decides its bar boundary)
   
9. **Manual wiring (CLK_DEP_TABLE)**
   - *Correction:* Order-free registered hops (all inputs frozen from prior cycle)

---

## Summary: What My Diagrams Got Right vs. Wrong

### ✓ Correct
- Three-chip layout (NIC FPGA 125 MHz, Pipeline FPGA 250 MHz, CPU, GPU)
- CDC 2-FF synchronizers at domain boundaries
- Async FIFO (FIFO_RX) for MAC→internal crossing
- Adapter-wire-NIC chain (not direct pipe)
- Bid/ask explicit separation (in principle, though code may violate)
- Display lanes (non-blocking, async, external rendering)
- Module I/O (inputs from seams/relays, outputs to registers)

### ❌ Wrong / Temporary Workaround
- **CLK_DEP_TABLE seq 0–11 dispatch** — target is order-free parallel execution
- **Single shared timeframe pulse** — target is per-module multipliers
- **Deterministic vs. independent oscillator modeling** — simulator uses one time base; real hardware has independent references

### ⚠️ Unclear / Not Shown
- Device hierarchy (backplane should be 3–4 devices, not flat modules)
- Per-module period multipliers (each indicator's own bar clock)
- Current code diseases (sim_feed_loop, TAI fast-forward, ghosts, replay registers)
- Candle input (should be bid/ask stream, not DOM)

---

## Next Step: Corrected Operational Flow

Redesign the operational flow to show:
1. **Order-free parallel execution** (not seq 0–11)
2. **Per-module timeframe multiples** (not single shared pulse)
3. **Device hierarchy backplane** (NIC device, Pipeline device, CPU, GPU)
4. **Registered 1-cycle latency** between producer and consumer (not explicit sequencing)
5. **Deterministic simulator time base** (all clocks derived for reproducibility)

This becomes the **true target specification** for the contract schema and harness generator.
