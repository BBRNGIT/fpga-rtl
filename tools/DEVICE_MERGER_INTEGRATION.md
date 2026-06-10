# Device Merger Integration Guide

Complete guide for integrating the device specification merger into your FPGA design pipeline.

## Overview

The device merger toolset provides three integrated Python tools:

1. **merge_device_sources.py** — Core merger (reconcile multi-source specs)
2. **generate_sample_device_specs.py** — Sample data generator (testing)
3. **test_merge_device_sources.py** — Unit test suite (validation)

All tools are self-contained, require only Python 3.8+, and have no external dependencies.

## File Locations

```
/Users/bbrn/fpga-rtl/tools/
├── merge_device_sources.py              (22 KB, executable)
├── generate_sample_device_specs.py      (8.4 KB, executable)
├── test_merge_device_sources.py         (13 KB, executable)
├── MERGE_DEVICE_SOURCES.md              (14 KB, primary documentation)
├── README_DEVICE_TOOLS.md               (10 KB, overview + API)
├── DEVICE_MERGE_EXAMPLES.md             (16 KB, 10 practical examples)
└── DEVICE_MERGER_INTEGRATION.md         (this file)
```

## Quick Integration Checklist

### 1. Setup

```bash
# Ensure Python 3.8+
python3 --version

# Make tools executable
chmod +x /Users/bbrn/fpga-rtl/tools/merge_device_sources.py
chmod +x /Users/bbrn/fpga-rtl/tools/generate_sample_device_specs.py
chmod +x /Users/bbrn/fpga-rtl/tools/test_merge_device_sources.py

# Test installation
/Users/bbrn/fpga-rtl/tools/merge_device_sources.py --help
```

### 2. Prepare Device Specs

Create JSON files for each source:

**device_specs.json** (from datasheets):
```json
{
  "source": "datasheet",
  "devices": {
    "xcvu9p-flga2104-2L": {
      "name": "Xilinx Virtex UltraScale+ XCVU9P",
      "parts": [
        {"name": "CLB", "type": "CLB", "count": 182400, "io_per_unit": 50},
        ...
      ]
    }
  }
}
```

**f4pga_devices.json** (from f4pga database):
```json
{
  "source": "f4pga",
  "devices": {
    "xcvu9p_flga2104": {
      "name": "Xilinx Virtex UltraScale+ XCVU9P-FLGA2104",
      "parts": [...]
    }
  }
}
```

**trellis_ecp5.json** (from Project Trellis):
```json
{
  "source": "trellis",
  "devices": {
    "LFE5U85F": {
      "name": "Lattice ECP5 LFE5U85F",
      "parts": [...]
    }
  }
}
```

### 3. Run Merger

```bash
cd /Users/bbrn/fpga-rtl/tools

# Basic merge (uses defaults)
python3 merge_device_sources.py

# Custom paths
python3 merge_device_sources.py \
  --datasheet path/to/device_specs.json \
  --f4pga path/to/f4pga_devices.json \
  --trellis path/to/trellis_ecp5.json \
  --output path/to/canonical_device_model.json \
  -v
```

### 4. Validate Output

```bash
# Check file was created
ls -lh canonical_device_model.json

# Inspect quality metrics
python3 -c "import json; m=json.load(open('canonical_device_model.json')); \
print(f'Devices: {m[\"source_summary\"][\"merged_devices\"]}'); \
print(f'Quality: {m[\"global_validation\"][\"overall_quality_score\"]:.0%}')"

# Review conflicts
python3 -c "import json; m=json.load(open('canonical_device_model.json')); \
[print(f'{k}: {len(v[\"audit\"][\"conflicts_log\"])} conflicts') \
for k,v in m['devices'].items() if v['audit']['conflicts_log']]"
```

## Architecture Integration

### Dataflow

```
Vendor Datasheets → device_specs.json ──┐
                                        ├→ merge_device_sources.py → canonical_device_model.json
f4pga Database   → f4pga_devices.json ──┤
                                        │
Project Trellis  → trellis_ecp5.json ───┘

                                        ↓

Hardware Design Tools
  ├─ Timing Analysis (extract CLB count)
  ├─ Resource Planning (BRAM, DSP availability)
  ├─ Device Selection (confidence scores)
  ├─ Constraint Generation (routing estimates)
  └─ CI/CD Validation (consistency checks)
```

### Build System Integration

In your Makefile or build script:

```makefile
# Variables
DEVICE_SPECS = canonical_device_model.json
DEVICE = xcvu9p-flga2104-2L

# Regenerate canonical model if sources change
$(DEVICE_SPECS): device_specs.json f4pga_devices.json trellis_ecp5.json
	python3 /Users/bbrn/fpga-rtl/tools/merge_device_sources.py \
	  --datasheet device_specs.json \
	  --f4pga f4pga_devices.json \
	  --trellis trellis_ecp5.json \
	  --output $@

# Validate device before synthesis
.PHONY: validate_device
validate_device: $(DEVICE_SPECS)
	@python3 << 'EOF'
import json, sys
m = json.load(open('$(DEVICE_SPECS)'))
if '$(DEVICE)' not in m['devices']:
	print('ERROR: Device not in canonical model'); sys.exit(1)
dev = m['devices']['$(DEVICE)']
if dev['validation']['consistency_score'] < 0.7:
	print('ERROR: Device has low consistency score'); sys.exit(1)
print('✓ Device validated')
EOF

# Generate constraints from device specs
constraints.sdc: $(DEVICE_SPECS)
	python3 scripts/generate_constraints.py \
	  --device $(DEVICE) \
	  --specs $(DEVICE_SPECS) \
	  --output $@
```

### Script Integration

Use in shell scripts:

```bash
#!/bin/bash
# build_hft_pipeline.sh

set -e

# Merge device specs
python3 tools/merge_device_sources.py -v

# Extract device properties
DEVICE="xcvu9p-flga2104-2L"
CLB_COUNT=$(python3 -c "
import json
d = json.load(open('canonical_device_model.json'))
clb = next(p['count']['value'] for p in d['devices']['$DEVICE']['parts'] if p['type'] == 'CLB')
print(clb)
")

echo "Building for $DEVICE (CLB: $CLB_COUNT)"

# Proceed with synthesis
vivado -mode batch -source build.tcl -tclargs $DEVICE $CLB_COUNT
```

### Python Integration

As a library in your Python tools:

```python
import json
from pathlib import Path

class FPGADeviceDatabase:
    """Interface to canonical device model."""
    
    def __init__(self, model_path="canonical_device_model.json"):
        with open(model_path) as f:
            self.model = json.load(f)
    
    def get_device(self, name):
        """Get device specs."""
        return self.model["devices"].get(name)
    
    def validate_device(self, name, min_confidence="high"):
        """Validate device meets requirements."""
        dev = self.get_device(name)
        if not dev:
            raise ValueError(f"Device {name} not found")
        
        conf_levels = {"low": 0, "medium": 1, "high": 2}
        conf_val = conf_levels[dev["validation"]["confidence"]]
        min_val = conf_levels[min_confidence]
        
        if conf_val < min_val:
            raise ValueError(
                f"Device confidence {dev['validation']['confidence']} "
                f"< {min_confidence}"
            )
        
        if dev["validation"]["consistency_score"] < 0.8:
            raise ValueError(
                f"Device consistency {dev['validation']['consistency_score']} < 0.8"
            )
    
    def get_clb_count(self, name):
        """Get CLB count."""
        dev = self.get_device(name)
        return next((p["count"]["value"] for p in dev["parts"] if p["type"] == "CLB"), 0)

# Usage
db = FPGADeviceDatabase()
db.validate_device("xcvu9p-flga2104-2L")
clb_count = db.get_clb_count("xcvu9p-flga2104-2L")
print(f"Device has {clb_count:,} CLBs")
```

## CI/CD Pipeline Integration

### GitHub Actions Example

```yaml
name: Device Specification Validation

on:
  push:
    paths:
      - "device_specs.json"
      - "f4pga_devices.json"
      - "trellis_ecp5.json"
  pull_request:

jobs:
  validate-devices:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Merge device specs
        run: |
          cd tools
          python3 merge_device_sources.py -v
      
      - name: Validate quality
        run: |
          python3 << 'EOF'
import json, sys
m = json.load(open("tools/canonical_device_model.json"))
gv = m["global_validation"]
if gv["overall_quality_score"] < 0.7:
    print(f"ERROR: Quality score {gv['overall_quality_score']:.0%} < 70%")
    sys.exit(1)
print(f"✓ Quality OK ({gv['overall_quality_score']:.0%})")
EOF
      
      - name: Check conflicts
        run: |
          python3 << 'EOF'
import json
m = json.load(open("tools/canonical_device_model.json"))
errors = sum(
    1 for d in m["devices"].values()
    for c in d["audit"]["conflicts_log"]
    if c["severity"] == "error"
)
if errors > 0:
    print(f"ERROR: {errors} high-severity conflicts")
    exit(1)
EOF
      
      - name: Upload canonical model
        uses: actions/upload-artifact@v3
        with:
          name: canonical-device-model
          path: tools/canonical_device_model.json
```

### GitLab CI Example

```yaml
device-validation:
  stage: validate
  script:
    - cd tools
    - python3 merge_device_sources.py -v
    - python3 -c "
        import json, sys
        m = json.load(open('canonical_device_model.json'))
        if m['global_validation']['overall_quality_score'] < 0.7:
          sys.exit(1)
        print('Device specs validated')
      "
  artifacts:
    paths:
      - tools/canonical_device_model.json
  only:
    - merge_requests
    - main
```

## Production Deployment

### Checklist

Before deploying to production:

- [ ] Generate canonical model from real datasheets (not samples)
- [ ] Verify all critical devices have `confidence: "high"`
- [ ] Check consistency_score > 0.8 for all devices
- [ ] Review conflicts_log; investigate any `"error"` severity
- [ ] Validate against real hardware (known device specs)
- [ ] Run all unit tests: `python3 test_merge_device_sources.py`
- [ ] Integration test with design tools
- [ ] Document any manual conflicts resolved
- [ ] Store canonical_device_model.json in version control
- [ ] Set up automated regeneration in CI/CD

### Version Control

```bash
# Commit canonical model with specs
git add device_specs.json f4pga_devices.json trellis_ecp5.json
git add canonical_device_model.json
git commit -m "docs: update device specifications

- Merged specs from datasheet, f4pga, Trellis
- 5 devices with high confidence
- 0 high-severity conflicts
- Overall quality: 87%"

# Tag stable version
git tag -a v1.0-device-specs -m "First production device spec release"
```

## Troubleshooting

### Issue: Merger Takes Too Long

**Cause**: Large device databases.

**Solution**: Profile with verbose logging:
```bash
python3 merge_device_sources.py -v 2>&1 | grep INFO | tail -20
```

### Issue: Low Quality Score

**Cause**: Many inferred fields or conflicting sources.

**Solution**:
1. Add missing explicit specs to source files
2. Review conflicts_log, pick most reliable source
3. Increase tolerance in numeric comparison if appropriate

### Issue: Device Not Found After Merge

**Cause**: Name mismatch between sources.

**Solution**:
```bash
# List all devices in model
python3 -c "import json; m=json.load(open('canonical_device_model.json')); \
print('\n'.join(sorted(m['devices'].keys())))"

# Check source files for name variants
grep -i "xcvu9p" device_specs.json f4pga_devices.json trellis_ecp5.json
```

## Testing

### Run All Tests

```bash
cd /Users/bbrn/fpga-rtl/tools
python3 test_merge_device_sources.py -v

# Output:
# Ran 23 tests in 0.010s
# OK
```

### Run Specific Test Category

```bash
# Unit tests only
python3 -m unittest test_merge_device_sources.TestDeviceSpecMerger -v

# Integration tests only
python3 -m unittest test_merge_device_sources.TestIntegrationWithSampleData -v

# Specific test
python3 -m unittest test_merge_device_sources.TestDeviceSpecMerger.test_normalize_device_name -v
```

## Documentation Map

| Document | Purpose | Audience |
|----------|---------|----------|
| **MERGE_DEVICE_SOURCES.md** | Detailed tool documentation, algorithm, API | Developers, RTL engineers |
| **README_DEVICE_TOOLS.md** | Overview, quick start, troubleshooting | All users |
| **DEVICE_MERGE_EXAMPLES.md** | 10 practical usage examples | Engineers, integrators |
| **DEVICE_MERGER_INTEGRATION.md** | Integration into build/CI/CD systems | Build engineers, DevOps |

## Support & Contributing

### Reporting Issues

If you find issues with the merger:

1. Run with verbose logging: `merge_device_sources.py -v`
2. Check conflicts_log in output
3. Verify source specs are correctly formatted
4. Provide: device name, source specs, output (sanitized)

### Contributing Improvements

To extend the merger:

1. Add new source type (loader + merge logic)
2. Improve routing inference for specific device families
3. Add device-specific validation rules
4. Enhance conflict resolution heuristics
5. Add tests for new functionality

All changes should:
- Maintain backward compatibility
- Include unit tests
- Update documentation
- Pass all existing tests

## FAQ

**Q: Do I need to regenerate the canonical model after each datasheet update?**

A: Yes, run `merge_device_sources.py` after updating any source spec. Integrate into CI/CD to automate.

**Q: Can I manually edit the canonical model?**

A: Not recommended. Manual edits will be overwritten on next merge. Edit source specs instead.

**Q: What if sources disagree on part counts?**

A: Conflicts are logged with severity. Datasheet is chosen as primary, but check conflicts_log for details.

**Q: How accurate is the routing inference?**

A: Empirical estimates based on Xilinx device characteristics. Marked as "medium" confidence. Verify against published specs.

**Q: Can I add my own custom device source?**

A: Yes, subclass DeviceSpecMerger and implement load_my_source_specs() + merge logic.

**Q: What Python versions are supported?**

A: 3.8+ (requires only standard library; no external dependencies).

---

For detailed tool documentation, see **MERGE_DEVICE_SOURCES.md**.
For practical examples, see **DEVICE_MERGE_EXAMPLES.md**.
For API reference, see **README_DEVICE_TOOLS.md**.
