# Device Merge Examples & Workflows

Practical examples for using the device specification merger in real-world scenarios.

## Example 1: Basic Merge with Sample Data

Generate sample data and merge:

```bash
# Generate test specs
python3 generate_sample_device_specs.py --output-dir test_data

# Merge into canonical model
python3 merge_device_sources.py \
  --datasheet test_data/device_specs.json \
  --f4pga test_data/f4pga_devices.json \
  --trellis test_data/trellis_ecp5.json \
  --output test_data/canonical.json \
  -v

# Output:
# INFO: Loaded datasheet specs from test_data/device_specs.json
# INFO: Loaded f4pga specs from test_data/f4pga_devices.json
# INFO: Loaded Trellis specs from test_data/trellis_ecp5.json
# INFO: Merging specs for device: xcvu9p-flga2104-2L
# INFO: Merging specs for device: xcku9p-ffva1156-2L
# INFO: Merging specs for device: LFE5U85F
# INFO: Wrote canonical model to test_data/canonical.json
# test_data/canonical.json
```

## Example 2: Inspect Merged Device Specs

Extract and display specs for a specific device:

```python
#!/usr/bin/env python3
import json

# Load canonical model
with open("canonical_device_model.json") as f:
    model = json.load(f)

# Get device
device_name = "xcvu9p-flga2104-2L"
device = model["devices"][device_name]

# Display summary
print(f"Device: {device['device']['name']}")
print(f"Sources: {', '.join(device['device']['sources'])}")
print(f"Confidence: {device['validation']['confidence']}")
print(f"Consistency Score: {device['validation']['consistency_score']}")
print()

# Display parts
print("Parts:")
for part in device["parts"]:
    count = part["count"]["value"]
    source = part["count"]["source"]
    conf = part["count"]["confidence"]
    print(f"  {part['type']:6} x {count:6} ({source}, {conf})")

print()

# Display routing
print("Routing:")
for route_type, spec in device["routing"].items():
    value = spec["value"]
    note = spec.get("note", "")
    print(f"  {route_type:12} {value:10} ({note})")

# Display conflicts
if device["audit"]["conflicts_log"]:
    print()
    print("Conflicts:")
    for conflict in device["audit"]["conflicts_log"]:
        print(f"  {conflict['field']}: {conflict['sources']}")
        print(f"    → {conflict['resolution']} ({conflict['severity']})")
```

Output:
```
Device: Xilinx Virtex UltraScale+ XCVU9P
Sources: datasheet, f4pga
Confidence: high
Consistency Score: 0.95

Parts:
  CLB      x 182400 (datasheet, high)
  BRAM     x    912 (datasheet, high)
  DSP      x   3456 (datasheet, high)
  IOB      x   2104 (datasheet, high)
  MMCM     x      4 (datasheet, high)

Routing:
  local          1641600 (Inferred from 182400 CLBs at ~9 local wires/CLB)
  regional       2500000 (Inferred from 182400 CLBs at ~13.7 regional/CLB)

Conflicts:
  parts.DSP.count: {'datasheet': 3456, 'f4pga': 3480}
    → 3456 (datasheet) (warning)
```

## Example 3: Validate Multiple Devices

Check consistency across all devices:

```python
#!/usr/bin/env python3
import json

with open("canonical_device_model.json") as f:
    model = json.load(f)

print("Device Quality Summary")
print("=" * 80)

high_conf = []
med_conf = []
low_conf = []

for name, device in model["devices"].items():
    conf = device["validation"]["confidence"]
    score = device["validation"]["consistency_score"]
    conflicts = device["validation"]["conflicts"]
    
    if conf == "high":
        high_conf.append(name)
    elif conf == "medium":
        med_conf.append(name)
    else:
        low_conf.append(name)
    
    status = "✓" if score > 0.8 else "!" if score > 0.6 else "✗"
    print(f"{status} {name:30} score={score:.2f} conflicts={conflicts}")

print()
print(f"High confidence:   {len(high_conf)} devices")
print(f"Medium confidence: {len(med_conf)} devices")
print(f"Low confidence:    {len(low_conf)} devices")

overall = model["global_validation"]["overall_quality_score"]
print(f"\nOverall quality: {overall:.2%}")
```

## Example 4: Export for Hardware Design

Convert canonical model to hardware-design-friendly format:

```python
#!/usr/bin/env python3
import json
import csv

with open("canonical_device_model.json") as f:
    model = json.load(f)

# Export to CSV for spreadsheet
with open("device_specs.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Device", "CLB", "BRAM (36KB)", "DSP", "IOB", "Local Routing", 
                     "Regional Routing", "Confidence", "Sources"])
    
    for name, device in model["devices"].items():
        parts = {p["type"]: p["count"]["value"] for p in device["parts"]}
        routing = device["routing"]
        
        clb = parts.get("CLB", 0)
        bram = parts.get("BRAM", 0)
        dsp = parts.get("DSP", 0)
        iob = parts.get("IOB", 0)
        local = routing.get("local", {}).get("value", 0)
        regional = routing.get("regional", {}).get("value", 0)
        conf = device["validation"]["confidence"]
        sources = ", ".join(device["device"]["sources"])
        
        writer.writerow([name, clb, bram, dsp, iob, local, regional, conf, sources])

print("Exported to device_specs.csv")
```

Output CSV:
```
Device,CLB,BRAM (36KB),DSP,IOB,Local Routing,Regional Routing,Confidence,Sources
xcvu9p-flga2104-2L,182400,912,3456,2104,1641600,2500000,high,datasheet, f4pga
xcku9p-ffva1156-2L,119280,600,2880,1156,1073520,1600000,high,datasheet
LFE5U85F,10848,432,108,381,97632,148617,medium,trellis
```

## Example 5: Conflict Resolution Workflow

Identify and resolve conflicts manually:

```python
#!/usr/bin/env python3
import json

with open("canonical_device_model.json") as f:
    model = json.load(f)

print("Conflict Report")
print("=" * 80)

total_conflicts = 0
for name, device in model["devices"].items():
    conflicts = device["audit"]["conflicts_log"]
    if not conflicts:
        continue
    
    print(f"\n{name}:")
    for conflict in conflicts:
        total_conflicts += 1
        print(f"  Field: {conflict['field']}")
        print(f"  Sources: {conflict['sources']}")
        print(f"  Resolution: {conflict['resolution']}")
        print(f"  Severity: {conflict['severity']}")
        
        # Decision logic
        if conflict["severity"] == "error":
            print(f"  ACTION: Investigate. Pick most reliable source.")
        elif conflict["severity"] == "warning":
            print(f"  ACTION: Review. < 3% difference is acceptable.")
        print()

print(f"\nTotal conflicts: {total_conflicts}")
print(f"High-severity: {sum(1 for d in model['devices'].values() for c in d['audit']['conflicts_log'] if c['severity'] == 'error')}")
```

## Example 6: Integrate Canonical Model into Build System

Use the canonical model in a hardware build:

```makefile
# Makefile excerpt

DEVICE_SPECS = canonical_device_model.json

# Extract CLB count for timing constraints
CLB_COUNT := $(shell python3 -c "import json; d=json.load(open('$(DEVICE_SPECS)')); print(next((p['count']['value'] for p in d['devices']['$(DEVICE)']['parts'] if p['type'] == 'CLB'), 0))")

# Generate timing constraints based on device specs
timing.sdc: $(DEVICE_SPECS)
	@python3 -c "import json; \
	d=json.load(open('$(DEVICE_SPECS)')); \
	device=d['devices']['$(DEVICE)']; \
	clb=$(CLB_COUNT); \
	print('# Auto-generated timing constraints'); \
	print('set_property CLOCK_DELAY_OFFSET {0} [get_clocks sys_clk]'.format(clb/1000))" > $@

# Validate device selection
validate_device:
	@python3 -c "import json; \
	d=json.load(open('$(DEVICE_SPECS)')); \
	if '$(DEVICE)' not in d['devices']: \
	    print('ERROR: Device $(DEVICE) not in canonical model'); exit(1); \
	device=d['devices']['$(DEVICE)']; \
	if device['validation']['consistency_score'] < 0.8: \
	    print('WARNING: Device $(DEVICE) has low consistency score'); \
	print('Device $(DEVICE) validated successfully')"

.PHONY: validate_device
```

## Example 7: Python Integration Library

Use the merger as a library in your tools:

```python
#!/usr/bin/env python3
"""
device_specs_client.py — Client library for canonical device model
"""

import json
from pathlib import Path
from typing import Dict, Optional

class DeviceSpecsClient:
    """Interface to canonical device model."""
    
    def __init__(self, model_path: str = "canonical_device_model.json"):
        with open(model_path) as f:
            self.model = json.load(f)
    
    def get_device(self, device_name: str) -> Optional[Dict]:
        """Get device specs."""
        return self.model["devices"].get(device_name)
    
    def get_clb_count(self, device_name: str) -> int:
        """Get CLB count for device."""
        device = self.get_device(device_name)
        if not device:
            return 0
        for part in device["parts"]:
            if part["type"] == "CLB":
                return part["count"]["value"]
        return 0
    
    def get_bram_count(self, device_name: str) -> int:
        """Get BRAM count for device."""
        device = self.get_device(device_name)
        if not device:
            return 0
        for part in device["parts"]:
            if part["type"] == "BRAM":
                return part["count"]["value"]
        return 0
    
    def get_dsp_count(self, device_name: str) -> int:
        """Get DSP count for device."""
        device = self.get_device(device_name)
        if not device:
            return 0
        for part in device["parts"]:
            if part["type"] == "DSP":
                return part["count"]["value"]
        return 0
    
    def get_confidence(self, device_name: str) -> str:
        """Get confidence level for device."""
        device = self.get_device(device_name)
        if not device:
            return "unknown"
        return device["validation"]["confidence"]
    
    def is_high_confidence(self, device_name: str) -> bool:
        """Check if device has high confidence specs."""
        return self.get_confidence(device_name) == "high"
    
    def list_devices(self) -> list:
        """List all devices in model."""
        return sorted(self.model["devices"].keys())

# Usage
if __name__ == "__main__":
    client = DeviceSpecsClient()
    
    print("Available devices:")
    for device in client.list_devices():
        clb = client.get_clb_count(device)
        conf = client.get_confidence(device)
        print(f"  {device:30} {clb:7} CLBs ({conf})")
    
    # Query specific device
    device = "xcvu9p-flga2104-2L"
    print(f"\n{device}:")
    print(f"  CLB: {client.get_clb_count(device):,}")
    print(f"  BRAM: {client.get_bram_count(device):,}")
    print(f"  DSP: {client.get_dsp_count(device):,}")
    print(f"  Confidence: {client.get_confidence(device)}")
```

Output:
```
Available devices:
  LFE5U85F                       10848 CLBs (medium)
  xcku9p-ffva1156-2L            119280 CLBs (high)
  xcvu9p-flga2104-2L            182400 CLBs (high)

xcvu9p-flga2104-2L:
  CLB: 182,400
  BRAM: 912
  DSP: 3,456
  Confidence: high
```

## Example 8: CI/CD Integration

Validate device specs in continuous integration:

```bash
#!/bin/bash
# ci_validate_devices.sh

set -e

# Generate specs if not present
if [ ! -f "canonical_device_model.json" ]; then
    echo "Generating canonical device model..."
    python3 merge_device_sources.py
fi

# Validate all devices
echo "Validating device specifications..."
python3 << 'EOF'
import json
import sys

with open("canonical_device_model.json") as f:
    model = json.load(f)

# Check overall quality
overall = model["global_validation"]["overall_quality_score"]
if overall < 0.7:
    print(f"ERROR: Overall quality score {overall:.0%} below threshold (70%)")
    sys.exit(1)

# Check high-confidence devices
high_conf = model["global_validation"]["high_confidence_devices"]
total = model["global_validation"]["total_devices"]
if high_conf < total * 0.8:
    print(f"WARNING: Only {high_conf}/{total} devices have high confidence")

# Check for errors
errors = sum(
    1 for d in model["devices"].values()
    for c in d["audit"]["conflicts_log"]
    if c["severity"] == "error"
)
if errors > 0:
    print(f"ERROR: {errors} high-severity conflicts found")
    for name, device in model["devices"].items():
        for conflict in device["audit"]["conflicts_log"]:
            if conflict["severity"] == "error":
                print(f"  {name}: {conflict['field']}")
    sys.exit(1)

print(f"✓ All devices valid (quality: {overall:.0%})")
EOF

echo "✓ Device specification validation passed"
```

Run in CI:
```bash
$ ./ci_validate_devices.sh
Generating canonical device model...
INFO: Loaded datasheet specs from device_specs.json
INFO: Loaded f4pga specs from f4pga_devices.json
Validating device specifications...
✓ All devices valid (quality: 87%)
✓ Device specification validation passed
```

## Example 9: Compare Two Models

Compare canonical models from different time periods or sources:

```python
#!/usr/bin/env python3
import json

# Load two models
with open("canonical_old.json") as f:
    old = json.load(f)
with open("canonical_new.json") as f:
    new = json.load(f)

print("Model Comparison")
print("=" * 80)

# Device count
old_count = len(old["devices"])
new_count = len(new["devices"])
print(f"Devices: {old_count} → {new_count} ({new_count - old_count:+d})")

# Quality change
old_quality = old["global_validation"]["overall_quality_score"]
new_quality = new["global_validation"]["overall_quality_score"]
print(f"Quality: {old_quality:.0%} → {new_quality:.0%} ({new_quality - old_quality:+.1%})")

# Device-by-device changes
print("\nDevice Changes:")
for device in sorted(set(list(old["devices"].keys()) + list(new["devices"].keys()))):
    old_dev = old["devices"].get(device)
    new_dev = new["devices"].get(device)
    
    if old_dev is None:
        print(f"  + {device} (NEW)")
    elif new_dev is None:
        print(f"  - {device} (REMOVED)")
    else:
        old_score = old_dev["validation"]["consistency_score"]
        new_score = new_dev["validation"]["consistency_score"]
        if old_score != new_score:
            print(f"  ~ {device} consistency {old_score:.2f} → {new_score:.2f}")
```

## Example 10: Generate Hardware Design Guide

Create device selection guide for engineers:

```python
#!/usr/bin/env python3
import json
from typing import Dict, List

def generate_device_guide(model_path: str = "canonical_device_model.json"):
    """Generate device selection guide."""
    
    with open(model_path) as f:
        model = json.load(f)
    
    # Categorize devices by size
    devices = []
    for name, device in model["devices"].items():
        clb = next((p["count"]["value"] for p in device["parts"] if p["type"] == "CLB"), 0)
        devices.append({
            "name": name,
            "clb": clb,
            "confidence": device["validation"]["confidence"],
            "score": device["validation"]["consistency_score"],
        })
    
    devices.sort(key=lambda d: d["clb"])
    
    print("FPGA Device Selection Guide")
    print("=" * 80)
    
    # Small devices
    print("\nSmall Devices (< 50K CLBs):")
    for d in devices:
        if d["clb"] < 50000:
            print(f"  {d['name']:30} {d['clb']:7,} CLBs ({d['confidence']})")
    
    # Medium devices
    print("\nMedium Devices (50K - 150K CLBs):")
    for d in devices:
        if 50000 <= d["clb"] < 150000:
            print(f"  {d['name']:30} {d['clb']:7,} CLBs ({d['confidence']})")
    
    # Large devices
    print("\nLarge Devices (> 150K CLBs):")
    for d in devices:
        if d["clb"] >= 150000:
            print(f"  {d['name']:30} {d['clb']:7,} CLBs ({d['confidence']})")
    
    # Recommended (high confidence)
    print("\nRecommended (High Confidence):")
    for d in sorted(devices, key=lambda x: -x["clb"]):
        if d["confidence"] == "high" and d["score"] > 0.9:
            print(f"  ✓ {d['name']}")

if __name__ == "__main__":
    generate_device_guide()
```

---

These examples demonstrate how to integrate the device specification merger into real-world hardware design workflows, CI/CD pipelines, and design tools.
