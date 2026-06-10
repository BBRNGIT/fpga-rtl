# FPGA Device Specification Tools

A complete toolset for parsing, reconciling, and validating FPGA device specifications from multiple sources (datasheets, f4pga, Project Trellis).

## Tool Overview

This package includes three complementary Python tools:

### 1. **merge_device_sources.py** — Device Specification Merger

Reconciles device specs from multiple sources into a single canonical model.

**Features:**
- Loads specs from datasheets, f4pga database, and Project Trellis
- Normalizes names, types, and numeric values across sources
- Cross-validates part counts and routing estimates
- Flags conflicts and confidence levels
- Infers missing routing capacity from CLB counts
- Validates consistency (sanity checks)
- Outputs canonical model with full audit trail

**Usage:**
```bash
python3 merge_device_sources.py \
  --datasheet device_specs.json \
  --f4pga f4pga_devices.json \
  --trellis trellis_ecp5.json \
  --output canonical_device_model.json \
  -v
```

See `MERGE_DEVICE_SOURCES.md` for full documentation.

### 2. **generate_sample_device_specs.py** — Sample Data Generator

Generates realistic test data for the merger tool.

**Features:**
- Creates sample datasheet specs (Xilinx Virtex, Kintex UltraScale)
- Generates f4pga device database examples
- Produces Trellis ECP5 reference specs
- Includes intentional small conflicts for testing

**Usage:**
```bash
python3 generate_sample_device_specs.py --output-dir test_data

# Creates:
#   test_data/device_specs.json
#   test_data/f4pga_devices.json
#   test_data/trellis_ecp5.json
```

### 3. **test_merge_device_sources.py** — Unit Test Suite

Comprehensive tests for all merger functionality.

**Coverage:**
- Name normalization (devices, part types)
- Numeric extraction and comparison
- Spec loading from all sources
- Conflict detection and logging
- Consistency validation
- Routing inference
- Output serialization and round-trip
- Integration tests with sample data

**Usage:**
```bash
python3 test_merge_device_sources.py

# All 23 tests pass:
# - 18 unit tests
# - 5 integration tests
```

## Quick Start

### 1. Install Dependencies

No external dependencies required beyond Python 3.8+.

```bash
python3 --version  # Should be 3.8 or later
```

### 2. Generate Sample Specs

```bash
python3 generate_sample_device_specs.py --output-dir .
```

### 3. Merge Specs

```bash
python3 merge_device_sources.py \
  --datasheet device_specs.json \
  --f4pga f4pga_devices.json \
  --trellis trellis_ecp5.json \
  --output canonical_device_model.json \
  -v
```

### 4. Review Output

```bash
python3 -m json.tool < canonical_device_model.json | less

# Or specific device:
python3 -c "import json; d = json.load(open('canonical_device_model.json')); 
print(json.dumps(d['devices']['xcvu9p-flga2104-2L'], indent=2))"
```

## Output Structure

The canonical device model contains:

```json
{
  "schema_version": "1.0",
  "generation_timestamp": "2026-06-10T15:23:11.928833Z",
  "source_summary": {
    "datasheet_devices": 2,
    "f4pga_devices": 2,
    "trellis_devices": 1,
    "merged_devices": 5
  },
  "devices": {
    "<device_name>": {
      "device": {
        "name": "...",
        "sources": ["datasheet", "f4pga"],
        "source_agreement": {...}
      },
      "parts": [
        {
          "name": "CLB",
          "type": "CLB",
          "count": {
            "value": 182400,
            "source": "datasheet",
            "confidence": "high"
          },
          "io_per_unit": {...},
          "total_io": {...}
        }
      ],
      "routing": {
        "local": {"value": 1641600, "source": "datasheet", "confidence": "medium"},
        "regional": {...}
      },
      "validation": {
        "consistency_score": 0.95,
        "conflicts": 0,
        "warnings": 0,
        "confidence": "high"
      },
      "audit": {
        "conflicts_log": [],
        "warnings": []
      }
    }
  },
  "global_validation": {
    "total_devices": 5,
    "high_confidence_devices": 3,
    "devices_with_conflicts": 1,
    "overall_quality_score": 0.6
  }
}
```

## Input Formats

### Device Specs (Datasheet)

```json
{
  "source": "datasheet",
  "devices": {
    "xcvu9p-flga2104-2L": {
      "name": "Xilinx Virtex UltraScale+ XCVU9P",
      "parts": [
        {
          "name": "CLB",
          "type": "CLB",
          "count": 182400,
          "io_per_unit": 50
        }
      ]
    }
  }
}
```

### f4pga Database

```json
{
  "source": "f4pga",
  "schema_version": "2.0",
  "devices": {
    "xcvu9p_flga2104": {
      "name": "Xilinx Virtex UltraScale+ XCVU9P-FLGA2104",
      "family": "vu",
      "parts": [...]
    }
  }
}
```

### Trellis Specs

```json
{
  "source": "trellis",
  "schema_version": "1.0",
  "devices": {
    "LFE5U85F": {
      "name": "Lattice ECP5 LFE5U85F",
      "family": "ecp5",
      "parts": [...]
    }
  }
}
```

## Key Features

### 1. Name Normalization

Devices and part types are normalized across sources:

```
Device names:
  "XCVU9P-FLGA2104-2L" == "xcvu9p_flga2104" == "xcvu 9p flga 2104"
  → normalized to: "xcvu9pflga21042l"

Part types:
  "CLB" == "clb" == "SLC" (Lattice)
  → normalized to: "CLB"
  
  "BRAM" == "bram" == "DPRAM" (Trellis)
  → normalized to: "BRAM"
  
  "DSP48" == "dsp" == "DSUPPORT" (Trellis)
  → normalized to: "DSP"
```

### 2. Numeric Comparison

Values are compared with tolerance for unit/rounding differences:

```python
182400 ≈ 182400 ✓ (exact match)
3456 ≈ 3480 ✓ (0.7% difference, within 3% tolerance)
100 ≠ 110 ✗ (10% difference, exceeds tolerance)
```

### 3. Conflict Detection

When sources disagree:

```json
{
  "field": "parts.DSP.count",
  "sources": {
    "datasheet": 3456,
    "f4pga": 3480
  },
  "resolution": "3456 (datasheet)",
  "severity": "warning"
}
```

### 4. Confidence Scoring

- **High**: Datasheet + cross-source validation agree
- **Medium**: Datasheet only, or secondary sources agree but differ slightly
- **Low**: Conflicting sources or weak evidence
- **Unknown**: No source data

### 5. Routing Inference

When routing specs aren't available, estimates are inferred from CLB count:

```
Local wires: CLB_count × 9
Regional: CLB_count × 13.7
(Based on empirical Xilinx FPGA ratios)
```

### 6. Consistency Validation

Sanity checks ensure specs are plausible:

- Required parts present (CLB, IOB)
- Total I/O > 0
- Routing capacity ≈ 1-100× CLB count
- Agreement across sources boosts confidence

## Python API

```python
from merge_device_sources import DeviceSpecMerger, Confidence, SourceType

# Create merger
merger = DeviceSpecMerger(output_dir=".")

# Load specs
merger.load_datasheet_specs("device_specs.json")
merger.load_f4pga_specs("f4pga_devices.json")
merger.load_trellis_specs("trellis_ecp5.json")

# Merge all devices
result = merger.merge_all_devices()

# Access specific device
xcvu9p = result["devices"]["xcvu9p-flga2104-2L"]
print(f"Confidence: {xcvu9p['validation']['confidence']}")
print(f"CLB count: {xcvu9p['parts'][0]['count']['value']}")
print(f"Conflicts: {xcvu9p['audit']['conflicts_log']}")

# Write output
output_path = merger.write_canonical_model("canonical_device_model.json")
```

## CLI Usage

### Merge with Defaults

```bash
python3 merge_device_sources.py
# Uses: device_specs.json, .f4pga_cache/devices.json, trellis_ecp5.json
# Outputs: canonical_device_model.json
```

### Custom Paths

```bash
python3 merge_device_sources.py \
  --datasheet my_datasheet.json \
  --f4pga my_f4pga.json \
  --trellis my_trellis.json \
  --output my_model.json \
  --output-dir output_dir/
```

### Verbose Logging

```bash
python3 merge_device_sources.py -v

# Shows INFO/DEBUG messages for each operation
```

### Download f4pga Database

```bash
python3 merge_device_sources.py --download-f4pga
# Stub for production; currently a no-op
```

## Testing

### Run All Tests

```bash
python3 test_merge_device_sources.py

# Output:
# Ran 23 tests in 0.010s
# OK
```

### Run Specific Test Class

```bash
python3 -m unittest test_merge_device_sources.TestDeviceSpecMerger -v
```

### Run Specific Test

```bash
python3 -m unittest test_merge_device_sources.TestDeviceSpecMerger.test_normalize_device_name -v
```

## Production Checklist

Before deploying to production:

- [ ] Verify datasheet specs against official vendor documentation
- [ ] Cross-validate f4pga database against known device specs
- [ ] Test on at least 3 representative devices (small/medium/large)
- [ ] Review conflicts_log; investigate any "error" severity entries
- [ ] Ensure consistency_score > 0.8 for all critical devices
- [ ] Validate all required parts present (CLB, BRAM, DSP, IOB)
- [ ] Confirm routing estimates match published fabric specs
- [ ] Test with real datasheets (not just sample data)
- [ ] Integrate into CI/CD pipeline

## Troubleshooting

### Device Not Found

```
ERROR: Device xcvu9p-flga2104-2L not found in any source
```

**Cause**: Device name mismatch between sources.

**Solution**: Check normalization. Device names should match after removing hyphens/spaces/underscores.

### High Conflict Count

```json
"devices_with_conflicts": 5,
"overall_quality_score": 0.4
```

**Cause**: Sources strongly disagree on specs.

**Solution**: 
1. Review conflicts_log for each device
2. Pick most reliable source manually
3. File upstream issue with secondary source maintainers

### Low Consistency Score

```json
"consistency_score": 0.4
```

**Cause**: Inferred fields or missing data.

**Solution**: Provide explicit specs for all parts; don't rely on inference alone.

## Contributing

To extend the tool:

1. **Add a new source**: Implement loader + merge logic
2. **Add validation rules**: Override `validate_consistency()`
3. **Improve inference**: Update `infer_routing_capacity()`
4. **Add tests**: Extend `test_merge_device_sources.py`

Example: Add Intel/Altera specs

```python
def load_intel_specs(self, filepath: str) -> None:
    try:
        with open(filepath, 'r') as f:
            self.intel_specs = json.load(f)
    except FileNotFoundError:
        self.intel_specs = {}
```

## References

- **Xilinx**: https://docs.xilinx.com/ (datasheets, UGs)
- **f4pga**: https://f4pga.readthedocs.io/ (open-source FPGA toolchain)
- **Project Trellis**: https://github.com/YosysHQ/prjtrellis (ECP5 bitstream)
- **Lattice**: https://www.latticesemi.com/ (datasheets, IPs)

## License

Part of the fpga-rtl HFT pipeline project.
