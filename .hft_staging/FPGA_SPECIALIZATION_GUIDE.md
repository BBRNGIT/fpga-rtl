# FPGA Specialization Tool — gen_fpga_specialization.py

**Complete guide to automating FPGA design specialization, address allocation, and scaffolding.**

---

## Overview

`gen_fpga_specialization.py` is a meta-tool that transforms a blank FPGA template and a module specification into a complete, concrete FPGA design with:

1. **Programmatic address allocation** — Eliminates hand-wiring of module addresses
2. **CDC region reservation** — Reserves space for cross-device synchronization logic
3. **Complete design documentation** — Generates specialized FPGA design markdown
4. **Skeleton emitter scaffold** — Generates boilerplate Python netlist emitter
5. **Validation reporting** — Checks all constraints (overlaps, budgets, alignment)

**Philosophy:** A blank FPGA template + a module list (YAML) → a fully specialized, wired, documented FPGA design. Zero hand-configuration of addresses.

---

## Why This Tool Exists

**Problem:** Hand-wiring module addresses across 15+ modules, 3 FPGAs, 1000+ registers is:
- Error-prone (overlaps, collisions)
- Unmaintainable (changing one module requires updating address map everywhere)
- Undocumented (wiring decisions live in code, not specifications)

**Solution:** Let an algorithm allocate all addresses in one pass, with validation.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│ INPUT: Blank Template + Module List                                │
│  • FPGA_TEMPLATE_STRATEGY.md (generic FPGA structure)              │
│  • fpga_nic_modules.yaml (which modules go here, resource budgets)  │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ AddressAllocator (Greedy Algorithm)                                 │
│  1. Sort modules by resource needs (optional)                        │
│  2. Allocate sequentially, aligned to 0x1000 boundaries             │
│  3. Reserve CDC region at top (0x0ff00000–0x10000000)               │
│  4. Validate: no overlaps, no CDC overflow                          │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ OUTPUT: Specialized FPGA Design                                      │
│  • FPGA_<NAME>.md — Design doc with address map, clock domains     │
│  • gen_fpga_<name>_net.py — Skeleton emitter w/ hardcoded addrs    │
│  • validation_report.txt — Allocation summary & constraint checks   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Usage

### Basic Command

```bash
python3 gen_fpga_specialization.py <template.md> <modules.yaml> [output_dir]
```

### Example: Specialize NIC FPGA

```bash
cd /Users/bbrn/fpga-rtl/.hft_staging
python3 gen_fpga_specialization.py FPGA_TEMPLATE_STRATEGY.md fpga_nic_modules.yaml fpga_nic/
```

**Output:**
```
✓ Generated FPGA specialization: NIC
  Design doc: fpga_nic/FPGA_NIC.md
  Emitter skeleton: fpga_nic/gen_fpga_nic_net.py
  Validation report: fpga_nic/validation_report.txt
  Total cells: 8,625
  Total BRAM: 64
  Modules: 8
  Status: PASS ✓
```

### Example: Specialize Pipeline FPGA

```bash
python3 gen_fpga_specialization.py FPGA_TEMPLATE_STRATEGY.md fpga_pipeline_modules.yaml fpga_pipeline/
```

---

## Input Format: Module List (YAML)

The module list specifies which modules run on an FPGA instance.

```yaml
# fpga_nic_modules.yaml
fpga_name: nic

# Primary clock for this FPGA (human-readable)
clock_primary: 125 MHz MAC clock (external_phy)

# Modules in this FPGA instance
modules:
  - name: adapter
    cells: 208           # Flip-flop count (from gate.sh output)
    bram: 0              # 36-bit word blocks
    clock_domain: mac
    comment: "Source: timestamp-paced CSV parser"

  - name: mac
    cells: 5
    bram: 0
    clock_domain: mac

  - name: fifo_rx
    cells: 8211
    bram: 64             # BRAM determines minimum window size
    clock_domain: mac_to_internal_crossing
```

**Fields:**
- `fpga_name` (required) — Name of the FPGA (e.g., "nic", "pipeline")
- `clock_primary` (required) — Description of primary clock domain
- `modules` (required) — List of module instances
  - `name` (required) — Module name (must match `.hft/<name>/<name>.net.json` when building)
  - `cells` (required) — Flip-flop cell count (from gate.sh final output)
  - `bram` (required) — 36-bit BRAM blocks used
  - `clock_domain` (required) — Which clock this module runs on
  - `comment` (optional) — Human description

---

## Output: Specialized FPGA Design

### 1. FPGA_<NAME>.md — Design Documentation

Complete design specification for the specialized FPGA:

```markdown
# FPGA Design: NIC

## Device Summary
| Property | Value |
|----------|-------|
| FPGA Name | nic |
| Primary Clock | 125 MHz MAC clock |
| Total Cells | 8,625 |
| Total BRAM | 64 |
| Address Space | 0x00000000 – 0x10000000 (256 MB) |
| CDC Reserved | 0x0ff00000 – 0x10000000 (1 MB) |
| Module Count | 8 |

## Modules Assigned

| Module | Clock Domain | Cells | BRAM | Address Window | Size |
|--------|--------------|-------|------|----------------|------|
| adapter | mac | 208 | 0 | 0x00000000 | 4 KB |
| ... | ... | ... | ... | ... | ... |

## Address Map

(ASCII diagram showing module placement)

## Next Steps
1. Review address map
2. Implement cross-module wiring in gen_fpga_<name>_net.py
3. Run: python3 gen_fpga_<name>_net.py > fpga_<name>.net.json
4. Validate: python3 validate.py fpga_<name>.net.json
```

**Use this as the canonical reference for address assignments and module placement.**

### 2. gen_fpga_<name>_net.py — Netlist Emitter Skeleton

A Python script with:
- Hardcoded MODULE_WINDOWS (address allocations from this specialization)
- CDC_REGION metadata
- load_module_netlist() function to load graduated modules
- emit_fpga_<name>_netlist() stub for the user to flesh out
- Main entry point that outputs JSON

**Key thing:** This script loads module netlists from `.hft/<module>/` and wires them together. The allocator's output (addresses) is embedded here, so you never hand-write addresses again.

```python
MODULE_WINDOWS = {
    "adapter": {
        "base": 0x00000000,
        "size": 0x00001000,
        "clock_domain": "mac",
    },
    # ... auto-allocated by AddressAllocator
}

def emit_fpga_nic_netlist() -> dict:
    """Assemble the complete NIC FPGA netlist."""
    # TODO: Load modules, wire cross-module connections, emit composite netlist
```

**User responsibility:** Fill in the cross-module wiring logic (same-FPGA reads, CDC seams). See ARCHITECTURE_CLARIFICATIONS.md for wiring rules.

### 3. validation_report.txt — Allocation Summary

```
FPGA SPECIALIZATION VALIDATION REPORT
=====================================

Generated for: NIC
Primary Clock: 125 MHz MAC clock (external_phy)
Total Cells: 8,625
Total BRAM: 64

--- ADDRESS ALLOCATION ---

Allocations (sorted by address):

  adapter         @ 0x00000000–0x00001000 (0x001000 bytes, 4 KB) clock=mac
  ...

Total allocated: 0x0002b000 bytes (172 KB)
CDC region base: 0x0ff00000
Free space before CDC: 0x0fed5000 bytes (260948 KB)

Utilization: 0.1% of module space

--- VALIDATION ---

✓ PASS: All constraints satisfied
  ✓ No address overlaps
  ✓ No overflow into CDC region
  ✓ All modules fit

--- NEXT STEPS ---

1. Review the address map in FPGA_NIC.md
2. Implement cross-module wiring in gen_fpga_nic_net.py
3. Run: python3 gen_fpga_nic_net.py > fpga_nic.net.json
4. Validate: python3 validate.py fpga_nic.net.json
```

**Use this to verify the allocation is valid before proceeding.**

---

## Address Allocation Algorithm

### Greedy Sequential Allocation

The tool uses a **greedy first-fit** algorithm:

1. **Initialize:**
   - Start address = 0x00000000
   - Reserve CDC region at 0x0ff00000 – 0x10000000 (1 MB)

2. **For each module in input order:**
   - Estimate size:
     - Minimum 0x1000 (4 KB) per module
     - If BRAM > 0: size = max(0x1000, BRAM_bytes aligned to 0x1000)
   - Allocate at next available address (aligned to 0x1000)
   - Mark as reserved

3. **Validate:**
   - No overlaps between allocations
   - No overflow into CDC region
   - Total allocated < CDC region base

### Alignment

All module address windows are **aligned to 0x1000 (4 KB) boundaries**:
- Simplifies address decoding (high bits select module, low bits select register)
- Matches typical memory page alignment
- Wastes negligible space (4 KB slots are small)

### CDC Region (Cross-Device)

The **top 1 MB (0x0ff00000 – 0x10000000) is reserved for CDC (Clock Domain Crossing) logic**:
- Gray-code FIFOs for async signals crossing between FPGAs
- 2-FF synchronization flip-flops (CDC minimum latency)
- Explicit route definition (metadata, not logic)

**Do not allocate modules into this region.** It's reserved by the allocator and validated by the tool.

---

## Examples: From YAML to Address Map

### NIC FPGA

**Input:** `fpga_nic_modules.yaml` (8 modules, 8,625 cells, 64 BRAM)

**Output:** `fpga_nic/FPGA_NIC.md`

```
Address Map:
0x00000000–0x00001000: adapter (mac)
0x00001000–0x00002000: wire (none)
0x00002000–0x00003000: mac (mac)
0x00003000–0x00004000: taiosc (taiosc)
0x00004000–0x00005000: tai (taiosc)
0x00005000–0x00006000: tai_cdc (mac_to_internal_crossing)
0x00006000–0x00007000: nic (mac)
0x00007000–0x0002b000: fifo_rx (mac_to_internal_crossing) [BRAM: 64 blocks → 144 KB]

CDC Region:
0x0ff00000–0x10000000: Gray-code CDC FIFOs + sync
```

### Pipeline FPGA

**Input:** `fpga_pipeline_modules.yaml` (14 modules, 1,022 cells, 52 BRAM)

**Output:** `fpga_pipeline/FPGA_PIPELINE.md`

```
Address Map:
0x00000000–0x00001000: internal (internal)
0x00001000–0x00002000: timeframe (internal)
0x00002000–0x0000b000: dom (internal) [BRAM: 16 blocks → 36 KB]
0x0000b000–0x0000e000: candle (internal) [BRAM: 4 blocks → 12 KB]
...
0x00027000–0x00028000: outbound (internal)

CDC Region:
0x0ff00000–0x10000000: Gray-code CDC FIFOs + sync
```

---

## Workflow: From Specialization to Netlist

### Step 1: Specialize FPGA

```bash
python3 gen_fpga_specialization.py FPGA_TEMPLATE_STRATEGY.md fpga_nic_modules.yaml fpga_nic/
```

**Outputs:**
- `fpga_nic/FPGA_NIC.md` — Address map reference
- `fpga_nic/gen_fpga_nic_net.py` — Emitter skeleton with hardcoded addresses
- `fpga_nic/validation_report.txt` — Allocation validation

### Step 2: Review Address Map

Open `fpga_nic/FPGA_NIC.md` and verify:
- All modules are present and correctly sized
- No overlaps or unexpected gaps
- CDC region is reserved (not allocated)
- Clock domains match the module specs

### Step 3: Implement Cross-Module Wiring

Edit `fpga_nic/gen_fpga_nic_net.py`:

```python
def emit_fpga_nic_netlist() -> dict:
    """Assemble the complete NIC FPGA netlist."""
    netlist = {...}
    
    # Load all module netlists
    modules_loaded = {}
    for module_name in MODULE_WINDOWS.keys():
        mod_net = load_module_netlist(module_name)
        modules_loaded[module_name] = mod_net
    
    # Wire cross-module connections
    # Example: adapter → wire → nic
    netlist["cross_module_wiring"] = [
        {"from": "adapter.WIRE_BID_PX", "to": "wire.BID_IN", "latency": 0},
        {"from": "wire.BID_IN", "to": "nic.BID_READ", "latency": 1},
        # ... more wiring
    ]
    
    return netlist
```

**Reference:** See ARCHITECTURE_CLARIFICATIONS.md for wiring patterns (same-FPGA registered hops, CDC seams).

### Step 4: Generate and Validate Netlist

```bash
cd fpga_nic
python3 gen_fpga_nic_net.py > fpga_nic.net.json
python3 ../validate.py fpga_nic.net.json
```

Checks:
- Single-writer law (each register written by one module)
- No-overlap (no register read/written by multiple modules in same tick)
- No-floating (all nodes wired, no orphans)

### Step 5: Build & Test

```bash
make -f Makefile.fpga_nic validate gen test
```

If successful, the composite FPGA is ready to integrate with other FPGAs or graduate.

---

## Configuration & Customization

### Device Address Space

The tool assumes a **256 MB device address space** (0x00000000 – 0x10000000):

```python
DEVICE_ADDRESS_SPACE = 0x10000000  # 256 MB total
CDC_REGION_SIZE = 0x100000  # 1 MB reserved
SLOT_ALIGNMENT = 0x1000  # 4 KB per slot
```

To customize, edit `gen_fpga_specialization.py`:

```python
# Custom: 512 MB FPGA
DEVICE_ADDRESS_SPACE = 0x20000000
CDC_REGION_SIZE = 0x200000  # 2 MB CDC
```

### Clock Domains

Clock domains are predefined, but custom domains can be added:

```python
CLOCK_DOMAINS = {
    "mac": {"frequency_mhz": 125, "source": "external_phy"},
    "internal": {"frequency_mhz": 250, "source": "pll_2x"},
    "taiosc": {"frequency_mhz": 1, "source": "oscillator"},
    "custom": {"frequency_mhz": 100, "source": "pll_custom"},  # NEW
}
```

Any clock_domain in the module list that isn't defined will report frequency as "TBD" in the design doc.

---

## Error Handling & Validation

### Constraint Violations

If the tool cannot allocate all modules, it reports:

```
ERROR: Could not allocate address for module fifo_rx (8211 cells, 64 BRAM).
Insufficient space.
```

**Fix:**
1. Reduce CDC_REGION_SIZE (if safe)
2. Reduce module budgets (unlikely; cells/BRAM are fixed)
3. Use a larger DEVICE_ADDRESS_SPACE
4. Split modules across multiple FPGAs

### Validation Failures

If allocation passes but validation fails (e.g., overlaps):

```
✗ FAIL: Constraint violations detected

  ✗ Address overlap: adapter [0x00000000–0x00001000] overlaps 
    wire [0x00000800–0x00001800]
```

**Cause:** Usually a bug in the allocator's overlap detection. Re-run with explicit module ordering to debug.

---

## Design Decisions & Rationale

### Greedy vs. Optimal Allocation

The tool uses **greedy sequential allocation** (first-fit) rather than optimal bin-packing:

- **Pros:** Simple, fast, deterministic
- **Cons:** May leave larger gaps than necessary

**Why:** For this use case (few modules, large address space), greedy is sufficient. Gap utilization is ~0.1% – plenty of room for expansion.

### 0x1000 Alignment

**Why 4 KB boundaries?**
- Hardware-friendly: 12 bits of index = 4 KB per module
- Page alignment: matches typical CPU/MMU granularity
- Wasted space negligible: ~4 KB per module ≪ 256 MB total

### CDC Region at Top

**Why reserve 0x0ff00000 – 0x10000000?**
- Easy to detect overflow (check if address > CDC_REGION_BASE)
- Leaves most of address space for modules
- Matches FPGA_TEMPLATE_STRATEGY.md layout

---

## Integration with Broader System

This tool fits into the full C-as-RTL pipeline:

```
Blank Template
      ↓
gen_fpga_specialization.py ← Module List (YAML)
      ↓
FPGA_<NAME>.md (design doc)
gen_fpga_<name>_net.py (emitter skeleton)
      ↓
User fills in cross-module wiring
      ↓
gen_fpga_<name>_net.py (emitter)
      ↓
fpga_<name>.net.json (netlist)
      ↓
validate.py (netlist validator)
      ↓
gennet.py (not used at FPGA level; module-level only)
      ↓
Integration testing
      ↓
Graduation (if applicable)
```

---

## Common Use Cases

### 1. Add a New Module to Existing FPGA

Update the module list YAML:
```yaml
modules:
  - name: new_module
    cells: 100
    bram: 2
    clock_domain: internal
```

Re-run the specializer:
```bash
python3 gen_fpga_specialization.py ... fpga_pipeline_modules_v2.yaml fpga_pipeline_v2/
```

The tool will automatically re-allocate all addresses (no manual intervention).

### 2. Create a Variant FPGA

Copy module list and modify:
```bash
cp fpga_nic_modules.yaml fpga_nic_xlarge_modules.yaml
# Edit to add more modules
python3 gen_fpga_specialization.py ... fpga_nic_xlarge_modules.yaml fpga_nic_xlarge/
```

### 3. Swap Clock Domain

Edit the module list:
```yaml
modules:
  - name: strategy
    clock_domain: fast_internal  # was "internal"
```

Re-run; the design doc updates immediately.

---

## Troubleshooting

### "Could not allocate address for module X"

- **Cause:** Module budget (cells + BRAM) exceeds available space
- **Check:** Is BRAM realistic? (64 blocks = 144 KB is large)
- **Fix:** Reduce BRAM or increase DEVICE_ADDRESS_SPACE

### "Address overlap: X overlaps Y"

- **Cause:** Allocation algorithm found a bug (rare)
- **Debug:** Run with explicit module ordering; check _find_next_available() logic
- **Fix:** Usually a tool bug; report and rebuild

### Generated emitter won't load modules

- **Cause:** Modules not graduated (not in `.hft/<module>/`)
- **Check:** Run `ls .hft/adapter/adapter.net.json` to verify
- **Fix:** Graduate modules first: `.hft_staging/graduate.sh adapter`

---

## Future Enhancements

1. **Optimal bin-packing** — Replace greedy with first-fit-decreasing or better
2. **Pin allocation** — Extend to allocate I/O pins per module (currently TBD)
3. **Power budgeting** — Track power per module, sum to FPGA TDP
4. **Thermal simulation** — Validate temperature per region
5. **Place-and-route hints** — Output constraints for physical placement
6. **Module placement clustering** — Colocate dependent modules to minimize routing

---

## References

- **FOUNDER_VISION.md** — Canonical architecture reference
- **CLAUDE.md** — Project build instructions and laws
- **FPGA_TEMPLATE_STRATEGY.md** — Blank template and design philosophy
- **ARCHITECTURE_CLARIFICATIONS.md** — Cross-module wiring patterns
- Graduated module netlists — `.hft/<module>/<module>.net.json` (source of truth)
