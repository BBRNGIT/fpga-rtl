# parse_datasheets.py Integration Example

## Pipeline Context

parse_datasheets.py is the **first stage** of the FPGA device specification pipeline:

```
Xilinx Datasheet
   (PDF/Text)
      ↓
[parse_datasheets.py] ← Generate device_specs.json
      ↓
device_specs.json
      ↓
[gen_device_net.py] ← Parse spec, emit netlist
      ↓
device.net.json
      ↓
[validate.py] ← Single-writer, no-overlap checks
      ↓
[gennet.py] ← Generate device C (device_gen.h)
      ↓
device_gen.h
      ↓
[Compile/Link] ← Build device module
      ↓
Device FPGA model (C code)
```

## Complete End-to-End Example

Assume you're setting up a new FPGA device model for the HFT architecture.

### Step 1: Extract Device Specification

```bash
cd fpga-rtl/tools

# Generate device_specs.json with default VU9P
python3 parse_datasheets.py -o device_specs.json -v
```

Output:
```
parse_datasheets.py: Device Spec Extraction Tool
  Output: device_specs.json
  Use VU9P defaults: True
✓ Spec validation passed
  Device: xcvu9p-flga2104-2L
  Resources: 16 entries
  Connectivity: 8 entries
✓ Wrote device_specs.json
  Size: 1753 bytes
```

### Step 2: Inspect Generated Specification

```bash
# View the spec
python3 -m json.tool device_specs.json | head -50

# Or query specific fields
python3 << 'EOF'
import json
with open("device_specs.json") as f:
    spec = json.load(f)

print(f"Device: {spec['device']['name']}")
print(f"CLBs: {spec['resources']['clbs']:,}")
print(f"LUTs: {spec['resources']['luts']:,}")
print(f"DSP48E2: {spec['resources']['dsp48e2']:,}")
print(f"GTY Transceivers: {spec['resources']['gty_transceivers']}")
print(f"I/O Banks: {spec['resources']['io_banks']}")
EOF
```

Output:
```
Device: xcvu9p-flga2104-2L
CLBs: 182,400
LUTs: 1,457,600
DSP48E2: 6,840
GTY Transceivers: 32
I/O Banks: 44
```

### Step 3: Generate Netlist (Next Stage)

Once you have `device_specs.json`, the next tool (`gen_device_net.py`) will:

1. **Read device_specs.json**
2. **Emit a netlist** describing device structure as nodes (parts) and connections (edges)
3. **Output device.net.json** for validation and code generation

Example (gen_device_net.py):
```python
#!/usr/bin/env python3
"""gen_device_net.py — Emit device netlist from spec."""

import json
import sys

def main():
    with open("device_specs.json") as f:
        spec = json.load(f)
    
    # Build netlist from spec
    net = {
        "device": spec["device"]["name"],
        "resources": spec["resources"],
        "dff_nodes": [],  # Device flip-flops (CLBs, BRAM, etc.)
        "comb_nodes": [],  # Device combinational logic (LUTs, routing, etc.)
        "connections": spec["connectivity"]["routing_resources"],
    }
    
    # Example: Create CLB nodes
    clb_count = spec["resources"]["clbs"]
    for i in range(min(clb_count, 100)):  # Sample first 100
        net["dff_nodes"].append({
            "name": f"CLB_{i}_ff",
            "type": "CLB_FF",
            "count": spec["connectivity"]["ff_per_clb"]
        })
    
    # Output netlist
    with open("device.net.json", "w") as f:
        json.dump(net, f, indent=2)
        f.write("\n")
    
    print(f"Emitted device netlist: device.net.json")
    print(f"  CLBs: {clb_count:,}")
    print(f"  Total connections: {sum(v for k, v in net['connections'].items())}")

if __name__ == "__main__":
    main()
```

### Step 4: Validate Netlist

```bash
# After gen_device_net.py creates device.net.json:
python3 validate.py device.net.json
```

Checks:
- ✓ Single-writer (each register written by exactly one node)
- ✓ No overlap (no read/write conflicts on same register)
- ✓ No floating (all nodes wired, no disconnected parts)

### Step 5: Generate Device C Code

```bash
# After validation, generate C code:
python3 gennet.py device.net.json > device_gen.h
```

Output: `device_gen.h` with:
- Device tick function (`device_tick()`)
- Register map (addresses, widths)
- Cell calls (structural logic)
- READ→COMPUTE→WRITE phases

### Step 6: Integrate into Module

```bash
# Place device_gen.h and glue code into a module directory
mkdir -p .hft_staging/device/
cp device.net.json .hft_staging/device/
cp device_gen.h .hft_staging/device/
cp device.c device.h .hft_staging/device/

# Build and test
cd .hft_staging/device
make validate
make gen
make test
```

## Customization Example: VU13P

If you want to generate specs for a different device (e.g., VU13P):

```bash
# Override device name while keeping VU9P resource baseline
python3 parse_datasheets.py \
  --device-name xcvu13p-flga2104-3L \
  --package FLGA2104 \
  --speed-grade -3 \
  --family "Virtex UltraScale+" \
  -o device_specs_vu13p.json -v

# Then proceed with gen_device_net.py using the new spec:
# (Assume gen_device_net.py accepts spec file argument)
python3 gen_device_net.py device_specs_vu13p.json > device.net.json
```

## PDF Extraction Example

If you have an actual Xilinx datasheet PDF:

```bash
# Extract from PDF (if pdfplumber installed)
python3 parse_datasheets.py \
  --datasheet /path/to/DS922_VU9P.pdf \
  -o device_specs.json \
  -v
```

The tool will:
1. Parse device name from PDF header
2. Extract resource counts from tables
3. Fall back to hardcoded specs if parsing fails

## Validation at Each Stage

```bash
# 1. Validate spec
python3 parse_datasheets.py --validate-only -v

# 2. Validate netlist JSON syntax
python3 -m json.tool device.net.json > /dev/null

# 3. Validate netlist structure
python3 validate.py device.net.json

# 4. Validate generated C
python3 -c "
import subprocess
result = subprocess.run(['gcc', '-c', 'device_gen.h', '-o', '/dev/null'], 
                       capture_output=True)
if result.returncode == 0:
    print('✓ C code compiles')
else:
    print('✗ C compilation failed:', result.stderr.decode())
"
```

## Directory Structure After Integration

```
fpga-rtl/
├── tools/
│   ├── parse_datasheets.py  ← You are here (spec extraction)
│   ├── gen_device_net.py    ← Next (netlist emitter)
│   ├── validate.py          ← Validation
│   ├── gennet.py            ← C generation
│   ├── device_specs.json    ← Generated spec
│   └── device_specs_VU9P_reference.json
├── .hft_staging/
│   ├── device/              ← New device module
│   │   ├── device.md        ← Spec doc
│   │   ├── gen_device_net.py
│   │   ├── device.net.json
│   │   ├── validate.py
│   │   ├── gennet.py
│   │   ├── device_gen.h
│   │   ├── device.c
│   │   ├── device.h
│   │   ├── test_device.c
│   │   ├── Makefile
│   │   └── ...
│   └── adapter/
│       └── ... (existing modules)
└── .hft/                    ← Graduated (immutable)
    ├── device/
    └── adapter/
```

## Common Commands Reference

```bash
# Extract spec (default VU9P)
python3 parse_datasheets.py -o device_specs.json

# Extract with verbose output
python3 parse_datasheets.py -v -o device_specs.json

# Extract from PDF
python3 parse_datasheets.py -d datasheet.pdf -o device_specs.json

# Custom device
python3 parse_datasheets.py --device-name xcvu13p-... -o specs.json

# Validate without writing
python3 parse_datasheets.py --validate-only

# Next: emit netlist
python3 gen_device_net.py < device_specs.json > device.net.json

# Validate netlist
python3 validate.py device.net.json

# Generate C
python3 gennet.py device.net.json > device_gen.h
```

## Key Files Generated

| File | Purpose | Input From | Output To |
|------|---------|-----------|-----------|
| `device_specs.json` | Device specification | parse_datasheets.py | gen_device_net.py |
| `device.net.json` | Device netlist | gen_device_net.py | validate.py, gennet.py |
| `device_gen.h` | Device C code | gennet.py | Module Makefile |
| `device.c/.h` | Module glue code | Developer | Makefile |
| `test_device.c` | Thin test | Developer | Makefile |

## Next Steps

1. **Understand parse_datasheets.py** — See [README_PARSE_DATASHEETS.md](README_PARSE_DATASHEETS.md)
2. **Design gen_device_net.py** — Create netlist emitter for your device
3. **Run validation** — Use validate.py to check netlist structure
4. **Generate C** — Use gennet.py to produce device_gen.h
5. **Test** — Build and run thin test in device module
6. **Graduate** — Promote to .hft vault (immutable) with graduate.sh

See also: `XILINX_VU9P_SPEC_EXTRACTION.md` for detailed VU9P specifications and architecture documentation.
