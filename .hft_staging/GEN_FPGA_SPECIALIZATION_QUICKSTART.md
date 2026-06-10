# gen_fpga_specialization.py — Quick Start

**Automate FPGA address allocation, documentation, and emitter scaffolding in one command.**

---

## Installation

The tool is already in `.hft_staging/`:

```bash
cd /Users/bbrn/fpga-rtl/.hft_staging
python3 gen_fpga_specialization.py --help
```

**Requirements:**
- Python 3.7+
- `pyyaml` (for parsing module lists)

Install yaml if needed:
```bash
pip3 install pyyaml
```

---

## Minimal Example: 30 Seconds

### 1. Create a module list (YAML)

```bash
cat > my_fpga_modules.yaml << 'EOF'
fpga_name: test
clock_primary: 250 MHz
modules:
  - name: adapter
    cells: 208
    bram: 0
    clock_domain: mac
  - name: nic
    cells: 180
    bram: 0
    clock_domain: mac
EOF
```

### 2. Run the specializer

```bash
python3 gen_fpga_specialization.py FPGA_TEMPLATE_STRATEGY.md my_fpga_modules.yaml my_fpga/
```

### 3. Check the output

```bash
cat my_fpga/FPGA_TEST.md          # Design doc with address map
cat my_fpga/validation_report.txt # Allocation summary
head -50 my_fpga/gen_fpga_test_net.py # Emitter skeleton
```

---

## Practical Example: NIC FPGA

### Input: Module Specification

**File: `fpga_nic_modules.yaml`**

```yaml
fpga_name: nic
clock_primary: 125 MHz MAC clock (external_phy)

modules:
  - name: adapter
    cells: 208
    bram: 0
    clock_domain: mac
    comment: "Price feed adapter"

  - name: wire
    cells: 0
    bram: 0
    clock_domain: none
    comment: "Passive wire bus"

  - name: mac
    cells: 5
    bram: 0
    clock_domain: mac

  - name: taiosc
    cells: 5
    bram: 0
    clock_domain: taiosc

  - name: tai
    cells: 4
    bram: 0
    clock_domain: taiosc

  - name: tai_cdc
    cells: 12
    bram: 0
    clock_domain: mac_to_internal_crossing

  - name: nic
    cells: 180
    bram: 0
    clock_domain: mac

  - name: fifo_rx
    cells: 8211
    bram: 64
    clock_domain: mac_to_internal_crossing
```

### Run Specializer

```bash
python3 gen_fpga_specialization.py FPGA_TEMPLATE_STRATEGY.md fpga_nic_modules.yaml fpga_nic/
```

### Output

Three files appear in `fpga_nic/`:

1. **FPGA_NIC.md** — Complete design documentation

```markdown
# FPGA Design: NIC

## Device Summary
| Property | Value |
|----------|-------|
| FPGA Name | nic |
| Primary Clock | 125 MHz MAC clock (external_phy) |
| Total Cells | 8,625 |
| Total BRAM | 64 |

## Modules Assigned
| Module | Clock Domain | Cells | BRAM | Address Window | Size |
|--------|--------------|-------|------|----------------|------|
| adapter | mac | 208 | 0 | 0x00000000 | 4 KB |
| wire | none | 0 | 0 | 0x00001000 | 4 KB |
| ...
| fifo_rx | mac_to_internal_crossing | 8211 | 64 | 0x00007000 | 144 KB |

## Address Map
0x00000000–0x00001000: adapter
0x00001000–0x00002000: wire
...
0x0ff00000–0x10000000: CDC Region (reserved)
```

**Use this as your canonical address reference.** No more hand-wiring addresses.

2. **gen_fpga_nic_net.py** — Skeleton emitter with hardcoded addresses

```python
#!/usr/bin/env python3
"""gen_fpga_nic_net.py — FPGA-level netlist emitter."""

# ---- Module Address Allocations ---- (auto-allocated by specializer)

MODULE_WINDOWS = {
    "adapter": {
        "base": 0x00000000,
        "size": 0x00001000,
        "clock_domain": "mac",
    },
    "wire": {
        "base": 0x00001000,
        "size": 0x00001000,
        "clock_domain": "none",
    },
    # ... etc
}

# CDC Region (reserved, do not allocate)
CDC_REGION = {
    "base": 0x0ff00000,
    "size": 0x00100000,
    "purpose": "Gray-code FIFOs and 2-FF CDC sync",
}

def emit_fpga_nic_netlist() -> dict:
    """Assemble the complete NIC FPGA netlist."""
    # TODO: Load module netlists, wire cross-module connections
    # User fills this in
```

**Next step:** Fill in the cross-module wiring logic (which signals go where).

3. **validation_report.txt** — Allocation summary

```
FPGA SPECIALIZATION VALIDATION REPORT
=====================================

Generated for: NIC
Total Cells: 8,625
Total BRAM: 64

--- ADDRESS ALLOCATION ---

adapter         @ 0x00000000–0x00001000 (4 KB)
wire            @ 0x00001000–0x00002000 (4 KB)
...
fifo_rx         @ 0x00007000–0x0002b000 (144 KB)

Total allocated: 0x0002b000 bytes (172 KB)
CDC region base: 0x0ff00000
Free space: 0x0fed5000 bytes (260948 KB)

Utilization: 0.1% of module space

--- VALIDATION ---

✓ PASS: All constraints satisfied
  ✓ No address overlaps
  ✓ No overflow into CDC region
  ✓ All modules fit
```

---

## Next Steps After Specialization

### 1. Review Address Map

Open `fpga_nic/FPGA_NIC.md` and verify all modules are correctly placed.

```bash
cat fpga_nic/FPGA_NIC.md | grep -A 20 "## Address Map"
```

### 2. Check Validation Report

Ensure the specializer passed all checks:

```bash
tail -5 fpga_nic/validation_report.txt
```

If status is FAIL, fix issues before proceeding.

### 3. Implement Cross-Module Wiring

Edit `fpga_nic/gen_fpga_nic_net.py`:

```python
def emit_fpga_nic_netlist() -> dict:
    netlist = {
        "device": "fpga_nic",
        "modules": [],
        "cross_module_wiring": [],
    }
    
    # Load all module netlists from .hft/
    modules_loaded = {}
    for module_name in MODULE_WINDOWS.keys():
        print(f"Loading {module_name}...")
        mod_net = load_module_netlist(module_name)
        modules_loaded[module_name] = mod_net
        netlist["modules"].append({
            "name": module_name,
            "netlist": mod_net,
            "window_base": f"0x{MODULE_WINDOWS[module_name]['base']:08x}",
        })
    
    # Wire cross-module connections
    # Example: adapter → wire → nic
    netlist["cross_module_wiring"] = [
        {"from": "adapter.WIRE_BID_PX", "to": "wire.BID_IN"},
        {"from": "wire.BID_IN", "to": "nic.BID_READ"},
        # ... add all connections from ARCHITECTURE_CLARIFICATIONS.md
    ]
    
    return netlist
```

**Reference:** See ARCHITECTURE_CLARIFICATIONS.md for the full wiring spec (which signals go where, latency per hop).

### 4. Generate Composite Netlist

```bash
cd fpga_nic
python3 gen_fpga_nic_net.py > fpga_nic.net.json
```

### 5. Validate Composite Netlist

```bash
python3 ../validate.py fpga_nic.net.json
```

Should pass:
- Single-writer law (each register written by one module)
- No-overlap (no read/write conflicts in same tick)
- No-floating (all nodes wired)

### 6. Build & Test (Optional)

```bash
make -f Makefile.fpga_nic validate gen test
```

---

## Module List Template

Copy this and fill in your modules:

```yaml
fpga_name: my_fpga
clock_primary: 250 MHz internal

modules:
  - name: module1
    cells: 100       # From gate.sh output for this module
    bram: 2          # 36-bit BRAM blocks
    clock_domain: internal
    comment: "Brief description"

  - name: module2
    cells: 50
    bram: 0
    clock_domain: internal

  - name: module3
    cells: 500
    bram: 32
    clock_domain: mac_to_internal_crossing
```

**Required fields:** `fpga_name`, `clock_primary`, `modules`
**Per module:** `name`, `cells`, `bram`, `clock_domain`
**Optional:** `comment`

---

## Common Patterns

### Pattern 1: Add a Module

1. Update module list YAML
2. Re-run specializer (addresses auto-reallocate)
3. Update cross-module wiring in gen_fpga_*_net.py
4. Re-run validation

```bash
# Edit fpga_nic_modules.yaml to add new_module
python3 gen_fpga_specialization.py FPGA_TEMPLATE_STRATEGY.md fpga_nic_modules.yaml fpga_nic/
# Addresses automatically change; emitter updates
```

### Pattern 2: Create a Variant FPGA

```bash
cp fpga_nic_modules.yaml fpga_nic_lite_modules.yaml
# Edit to remove modules
python3 gen_fpga_specialization.py FPGA_TEMPLATE_STRATEGY.md fpga_nic_lite_modules.yaml fpga_nic_lite/
```

### Pattern 3: Change Clock Domain

```yaml
modules:
  - name: strategy
    cells: 150
    bram: 8
    clock_domain: fast_internal  # was "internal"
```

Re-run specializer; design doc updates automatically.

---

## Output File Locations

After running:
```bash
python3 gen_fpga_specialization.py FPGA_TEMPLATE_STRATEGY.md fpga_nic_modules.yaml fpga_nic/
```

You get:
```
fpga_nic/
├── FPGA_NIC.md               # Design doc (canonical reference)
├── gen_fpga_nic_net.py       # Emitter skeleton (user fills in wiring)
└── validation_report.txt     # Allocation summary + checks
```

**Key files:**
- **FPGA_NIC.md** — Read this first; it's the address map bible
- **gen_fpga_nic_net.py** — Keep addresses, update wiring logic
- **validation_report.txt** — Verify all constraints passed

---

## Error Messages & Fixes

### "Module list not found: fpga_nic_modules.yaml"

**Fix:** Create the YAML file with correct module list.

```bash
cat > fpga_nic_modules.yaml << 'EOF'
fpga_name: nic
clock_primary: 125 MHz MAC
modules:
  - name: adapter
    cells: 208
    bram: 0
    clock_domain: mac
EOF
```

### "Could not allocate address for module fifo_rx"

**Fix:** Module BRAM requirement too large or device space too small. 
- Reduce BRAM in module list, or
- Increase DEVICE_ADDRESS_SPACE in tool, or
- Split across multiple FPGAs

### "ERROR: Address overlap: adapter overlaps wire"

**Fix:** Rare; indicates tool bug. Rebuild from latest version.

---

## Tips & Tricks

### Tip 1: Keep Module Lists in Git

Version control your YAML files:
```bash
git add fpga_nic_modules.yaml fpga_pipeline_modules.yaml
git commit -m "spec: define FPGA module allocations"
```

Enables easy rollback and change history.

### Tip 2: Rename Safely

When renaming an FPGA (e.g., `fpga_nic` → `fpga_nic_v2`):
1. Update module list YAML
2. Re-run specializer with new output dir
3. Review new design doc
4. Don't delete old version (keep for reference)

### Tip 3: Automate Specialization in CI/CD

Add to your build pipeline:
```bash
#!/bin/bash
for yaml in fpga_*_modules.yaml; do
    fpga_name=$(basename "$yaml" _modules.yaml)
    python3 gen_fpga_specialization.py \
        FPGA_TEMPLATE_STRATEGY.md "$yaml" "$fpga_name/"
    if [ $? -ne 0 ]; then
        echo "FPGA specialization failed: $fpga_name"
        exit 1
    fi
done
```

### Tip 4: Dry Run (Check Feasibility)

Before committing to an FPGA design, run the specializer and check the validation report:

```bash
python3 gen_fpga_specialization.py FPGA_TEMPLATE_STRATEGY.md proposed_modules.yaml /tmp/test_fpga/
cat /tmp/test_fpga/validation_report.txt
# If PASS, keep the design; if FAIL, adjust module list
```

---

## Integration Checklist

After specialization:

- [ ] Review FPGA_<NAME>.md address map
- [ ] Check validation_report.txt (must be PASS)
- [ ] Verify all expected modules are present
- [ ] Update cross-module wiring in gen_fpga_<name>_net.py
- [ ] Generate composite netlist: `python3 gen_fpga_<name>_net.py > fpga_<name>.net.json`
- [ ] Validate netlist: `python3 ../validate.py fpga_<name>.net.json`
- [ ] Build & test (optional but recommended)
- [ ] Commit YAML, design doc, and emitter to version control

---

## References

- **FPGA_SPECIALIZATION_GUIDE.md** — Full documentation
- **FOUNDER_VISION.md** — Canonical architecture reference
- **CLAUDE.md** — Project build instructions
- **ARCHITECTURE_CLARIFICATIONS.md** — Cross-module wiring spec
- **FPGA_TEMPLATE_STRATEGY.md** — Blank template strategy

---

## Questions?

Refer to **FPGA_SPECIALIZATION_GUIDE.md** for comprehensive documentation on:
- Address allocation algorithm
- Customization & configuration
- Design decisions & rationale
- Integration with the broader C-as-RTL system
