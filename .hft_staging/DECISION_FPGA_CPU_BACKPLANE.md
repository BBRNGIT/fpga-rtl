# Decision: FPGA, CPU, Backplane Abstractions — Necessary or Optional?

## Current State

We have:
- **15 graduated hardware modules** (valid, tested, cells > 0)
- **Independent clocks** (5 oscillators, truly separate)
- **CDC synchronizers** (2-FF gray-code at domain boundaries)
- **Contract schema** (auto-extracted, canonical wiring spec)
- **Address-based register wiring** (modules read/write via backplane addresses)
- **Display lanes** (every module outputs to TUI)

We do NOT have:
- **FPGA device container** (NIC FPGA, Pipeline FPGA as explicit abstractions)
- **CPU device container** (host control, boot, admin)
- **Backplane device** (top-level device map, hierarchical structure)

**Question:** Are these abstractions necessary for the design, or are they optional refinements we can defer?

---

## Case FOR: FPGA/CPU/Backplane Structure

### 1. Hardware Fidelity (Critical)

**Real hardware fact:** The founder specifies a **three-chip Xilinx XCVU13P layout** (§3, §5a):
```
NIC FPGA (125 MHz MAC domain)
Pipeline FPGA (250 MHz INTERNAL domain)
CPU (host, independent clock)
[GPU optional, display device]
```

**Physical constraints:**
- Each FPGA is synthesized separately (vendor tool per device)
- Each FPGA has its own clock PLLs, power budget, I/O banks
- SLR (SuperLogic Region) seams are *physical* boundaries with registered crossing
- Clock domains validate independence: "can we build this on real silicon?"

**Simulator fidelity gap:**
- Current flat 15-module view doesn't model physical device boundaries
- Simulator says "2-FF sync at domain boundary" but doesn't enforce *which* boundary
- When we build real hardware, we'll discover cross-device paths we thought were CDC'd but aren't
- Cost of fidelity gap: late hardware debugging, possible redesign

**Example failure mode:**
```
Simulator (no device boundary):
  dom (internal clock) reads fifo_rx_wr_gray (MAC domain)
  latency_cycles=1 in contract
  ✓ Passes simulator (CDC'd)

Real hardware (with SLR boundary):
  fifo_rx is on SLR0 (NIC side)
  dom is on SLR1 (Pipeline side)
  SLR crossing already adds 2 register stages
  Adding CDC on top = wrong (triple sync, extra latency)
  ✗ Fails place-and-route or behaves wrong

Device structure would have caught this:
  "SLR0→SLR1 is a registered crossing (2 cycles)"
  "dom cannot read fifo_rx_wr_gray directly"
  "must read through SLR seam registers (clock_edge_slr_seam)"
```

### 2. Design Robustness & Order-Free Execution

**Founder's architecture (§4):**
> "All cross-module communication is **registered** (one clock per hop). Every block reads the previous cycle's frozen state → **evaluation order is irrelevant** → run the blocks in any order each tick, identical result."

**How device structure enforces this:**
```
Same-device (NIC FPGA):
  adapter reads
  adapter computes (combinational)
  adapter outputs (registered on rising edge)
  wire reads adapter output
  ✓ OK: adapter → wire is 1-cycle registered hop

Cross-device (MAC → INTERNAL via SLR seam):
  nic (MAC domain) writes to fifo_rx
  nic outputs registered (MAC rising edge)
  fifo_rx CDC 2-FF sync (2 internal cycles)
  dom (INTERNAL domain) reads fifo_rx
  ✓ OK: nic → dom is 2-cycle registered hop (guaranteed)

Without device structure:
  contract says latency_cycles=1 or latency_cycles=2
  but there's no hard rule about where latency comes from
  Next engineer adds a "shortcut" read thinking it's local
  Turns into combinational cross-device path
  ✗ Order-dependent, order-sensitive, fails on real hardware
```

**Device structure = enforcement:** You cannot read across device boundaries without going through designated seam registers. Impossible to accidentally create fast paths.

### 3. CDC Validation (Critical for Correctness)

**CDC is subtle.** Gray-code synchronizers, metastability, clock ratios — easy to mess up.

**Device structure enables automated validation:**
```
Pre-commit hook can check:
  if (read_module.device != write_module.device) AND (latency_cycles < 2):
    FAIL: cross-device read without proper CDC
  
  if (read_module.clock_domain != write_module.clock_domain) AND (latency_cycles < 2):
    FAIL: cross-domain read without proper sync

  if (write_address is in SLR seam window AND latency_cycles < 2):
    FAIL: SLR crossing without registered delay
```

**Without device structure:**
- Can't distinguish "local register read" from "cross-device read"
- Contract says `source_address=0x2000000` but doesn't say "this crosses an SLR boundary"
- CDC validation becomes heuristic and error-prone
- Late-stage bugs in real hardware

### 4. Backplane Hierarchy (Design Intent, §3)

**Founder's stated target (§3):**
> "Hierarchy (intended end-state): only the **devices** explicitly live on the backplane; each device's **modules wire *into* the device** (registers nested inside the device's reserved region)... The backplane is a **device map, not a module map**."

**Current status:**
- 14 `backplane_*.h` sub-headers (fragmentation, known corruption)
- 15 flat modules on one backplane
- No device hierarchy

**Why it matters:**
- Founder considers current flat layout a "disease" (§11.5)
- Device hierarchy = cleaner mental model (architect → devices → modules)
- Prevents future sprawl (if we add 50 modules, flat backplane becomes unmaintainable)
- Aligns simulator with design intent

### 5. Separate Device Builds (Real Hardware Path)

**When we build FPGA:**
```
Step 1: Synthesize NIC FPGA
  ├─ adapter, wire, mac, tai, taiosc, tai_cdc, nic (MAC domain)
  ├─ fifo_rx writer side (MAC clock)
  ├─ Clock generation for MAC (125 MHz PLL)
  └─ Vendor tool → bitstream for NIC chip

Step 2: Synthesize Pipeline FPGA
  ├─ dom, candle, footprint, tpo, timeframe, fractal, cbr, pip_resolver, strategy, risk, OMS, SOR, outbound (INTERNAL domain)
  ├─ fifo_rx reader side (INTERNAL clock)
  ├─ Clock generation for INTERNAL (250 MHz PLL)
  └─ Vendor tool → bitstream for Pipeline chip

Step 3: CPU build
  ├─ Boot loader, clock distribution, power management
  ├─ Instrumentation (display, admin)
  └─ Host binary
```

**Without device abstraction:**
- How do we know which modules go to which chip?
- Do we synthesize all 15 together (monolithic, wrong)?
- Do we manually split them (error-prone, doesn't scale)?
- Tool can't auto-generate per-device builds

**With device abstraction:**
- Each device explicitly lists its modules
- Build tool knows: "synth NIC (adapter, wire, mac, tai, ...), synth Pipeline (dom, candle, ...)"
- Scales to 100 modules: auto-partition by device
- Real hardware teams depend on this

---

## Case AGAINST: "Not Yet Necessary"

### 1. Simulator Works Without It

**Current state:**
- All 15 modules work, contracts validate, circuits pass gate 2d
- CDC is implicitly enforced (latency_cycles in contracts)
- Address-based wiring is correct
- Tests pass

**Argument:**
- Device abstraction is optional structure; it's not required for correctness
- Contracts already capture everything needed (source_address, latency_cycles, clock_domain)
- Can validate CDC purely from contracts (no device boundary needed)
- Defer to later when we have real hardware targets

### 2. Adds Complexity & Indirection

**Cost of device abstraction:**
```
Before:
  backplane[0x2100000] → dom register

After:
  backplane → device[Pipeline FPGA] → module[dom] → register[0x2100000]
```

More layers = more indirection, more code, more to explain.

**Boilerplate:**
- Device init functions (clock setup per device, reset sequencing)
- Device dispatcher (clock_edge_pipeline_all, clock_edge_nic_all)
- Device validation rules
- Updated contracts with `device_assignment` field

### 3. Timing Doesn't Demand It

**Can enforce "no fast paths" via contract validation:**
```python
# Contract validator can check:
for module in all_modules:
  for input in module.inputs:
    if input.clock_domain != module.clock_domain:
      if input.latency_cycles < 2:
        ERROR("cross-domain read without proper sync")
```

**Don't need physical device boundaries to catch violations** — the contract rules are sufficient.

### 4. Can Be Added Later

**Advantages of deferral:**
- Modules are self-contained; no refactoring needed
- Contracts are stable (what we need to add device structure is already there)
- Add device mapping layer when hardware is imminent
- No risk of wrong abstraction if we design it later with real hardware in hand

### 5. Isn't Blocking Current Work

**15 modules + contracts are sufficient for:**
- Designing connection modes (sync, CDC, relay, display)
- Defining module contracts formally
- Auto-generating wiring diagrams
- Running full simulator on current stack

**Device structure doesn't unblock any of this.**

---

## Breaking the Case (Reality Check)

### Against "Not Yet Necessary"

**Founder stated device hierarchy is the target (§3).**
- Current flat layout is the **known disease** (§11.5: "Backplane fragmentation")
- He considers it a corruption to be fixed, not optional
- "Intended end-state: only devices on backplane, modules nested inside"
- Building a second flat-module system = repeating the corruption

**Hardware fidelity matters.**
- Simulator is faithful only if it models physical reality
- If we don't model device boundaries, we're testing wrong thing
- We'll hit SLR crossing bugs when we synthesize, late in the cycle
- Cost of late discovery: 2–4 weeks of hardware debugging

**Scalability hit.**
- 15 modules OK in flat layout
- 50 modules = unmaintainable, address collisions, no locality
- We'll have to add device structure anyway
- Doing it now = lower cost (small module count, fresh contracts)
- Doing it at 50 modules = refactoring nightmare

**Pre-commit validation fails without it.**
- Can't distinguish "this read is local" from "this crosses SLR"
- Pre-commit hook can't enforce CDC rules (too many false positives/negatives)
- Contract validator has no device context
- Late-stage bugs slip through

---

## Decision Matrix

| Factor | Blocking? | Cost to Do Now | Cost to Defer | Verdict |
|---|---|---|---|---|
| **Hardware fidelity** | No (simulator works) | Low (15 modules, fresh) | High (rebuild later) | Do now |
| **Founder's design intent** | No (not enforced) | Low (lightweight) | Medium (design drift) | Do now |
| **SLR CDC validation** | No (contracts sufficient) | Medium (new validation rules) | High (bugs in hardware) | Do now |
| **Device-specific builds** | No (not needed yet) | High (full tool chain) | Medium (when hardware comes) | **Defer** |
| **Backplane hierarchy** | No (flat works) | Low (mapping layer) | Low (refactor when needed) | Do now |
| **Module refactoring** | No (none needed) | None (modules unchanged) | None (still self-contained) | Defer |

---

## My Verdict: Necessary for Design Robustness, Lightweight Implementation NOW

### Recommendation

**Build device abstraction now, but keep it lightweight:**

1. **Define 3–4 devices** (small, stable)
   ```
   NIC FPGA (clock domain: mac @ 125 MHz)
     ├─ adapter, wire, mac, tai, taiosc, tai_cdc, nic
     └─ fifo_rx (writer side)
   
   Pipeline FPGA (clock domain: internal @ 250 MHz)
     ├─ dom, candle, footprint, tpo, timeframe, fractal, cbr, pip_resolver
     ├─ strategy, risk, OMS, SOR, outbound
     └─ fifo_rx (reader side)
   
   CPU (clock domain: cpu, independent)
     └─ [instrumentation, boot, admin]
   
   GPU (clock domain: gpu, independent, optional)
     └─ [display TUI rendering, separate binary]
   ```

2. **Add `device_assignment` to contract schema**
   ```json
   "device": "NIC FPGA",
   "clock_domain": "mac",
   "in_device_address_range": "0x1700000–0x1FFFFFF"
   ```

3. **Update contract extraction** (contract-extractor.py)
   ```python
   device_map = {
     "adapter": "NIC FPGA",
     "wire": "NIC FPGA",
     "mac": "NIC FPGA",
     ...
     "dom": "Pipeline FPGA",
     ...
   }
   for module, contract in contracts:
     contract["device"] = device_map[module]
   ```

4. **Add pre-commit CDC validation**
   ```bash
   # Pre-commit hook
   for each module:
     for each cross-device input:
       if latency_cycles < 2:
         FAIL "cross-device read without proper sync"
   ```

5. **Update integration harness** (generate per-device dispatch, optional)

### Cost & Payoff

**Cost to implement:**
- Design device map: 30 min
- Update contract schema + extractor: 1 hr
- Add pre-commit validation: 1 hr
- Test & verify: 30 min
- **Total: ~3 hours**

**Payoff:**
- ✓ Hardware-faithful architecture (models real FPGA layout)
- ✓ CDC rules enforceable pre-commit (catch bugs early)
- ✓ Founder's design intent (device hierarchy, no flat corruption)
- ✓ Scalable (ready for 50+ modules)
- ✓ SLR boundary modeling (real silicon ready)
- ✓ Future-proof (no refactoring when hardware comes)

### Alternative: Defer & Risk

**If we defer:**
- Simulator continues to work (no immediate pain)
- Contract validation is incomplete (missing device context)
- When hardware team arrives, they ask "which modules are on which chip?"
- Answer: "um, we have to figure that out" (design work, late discovery)
- Possible: hardware incompatible with simulator assumptions
- Result: refactor simulator + contracts + modules = 1–2 weeks lost

---

## Conclusion

**Device abstraction is necessary for design robustness and hardware fidelity.**

Not immediately blocking (simulator works without it), but **cost of deferral exceeds cost of doing it now.**

Lightweight implementation (device map + contract update + validation) is ~3 hours, compared to 1–2 weeks of hardware discovery and refactoring later.

**Recommendation: Build it now, before adding more modules.**
