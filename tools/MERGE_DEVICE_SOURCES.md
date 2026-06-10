# merge_device_sources.py — Device Specification Merger

A Python tool for reconciling FPGA device specifications from multiple authoritative sources (datasheets, f4pga database, Project Trellis bitstream docs) into a single canonical device model with conflict detection, source attribution, and confidence scoring.

## Overview

Building high-frequency trading hardware pipelines on real FPGAs requires accurate device specifications: CLB counts, BRAM capacity, DSP availability, I/O capability, and routing resources. These specs come from multiple sources, each with different coverage, naming conventions, and precision:

- **Datasheets** (primary): Official vendor specs (Xilinx, Lattice, Intel), most authoritative
- **f4pga database**: Community-maintained open-source device database; good for cross-validation
- **Project Trellis**: ECP5 bitstream reference; Lattice-focused, excellent for detailed routing

This tool **reconciles all three sources** into a single **canonical device model** (`canonical_device_model.json`) with:

1. **Source attribution** — every spec field marks which source provided it
2. **Confidence scoring** — agreement across sources boosts confidence
3. **Conflict logging** — all mismatches are logged for manual review
4. **Consistency validation** — sanity checks (CLB count vs. routing, total I/O, etc.)
5. **Audit trail** — full history of decisions and uncertainties

## Design Philosophy

- **Datasheet is primary**: Vendor specs are authoritative; f4pga/Trellis are cross-checks
- **Conflicts are logged, not hidden**: All mismatches recorded with severity and resolution
- **Determinism through reconciliation**: Identical canonical model across builds and environments
- **No guessing**: Where sources disagree, the discrepancy is flagged; no silent fallback
- **Confidence is earned**: High confidence = datasheet + cross-validation, not just datasheet alone

## Installation

```bash
# No external dependencies beyond Python 3.8+
python3 merge_device_sources.py --help
```

## Quick Start

### 1. Generate Sample Specs (for testing)

```bash
python3 generate_sample_device_specs.py --output-dir .

# Creates:
#   device_specs.json          — sample datasheet specs
#   f4pga_devices.json         — sample f4pga database
#   trellis_ecp5.json          — sample Trellis specs
```

### 2. Merge Specs into Canonical Model

```bash
python3 merge_device_sources.py \
  --datasheet device_specs.json \
  --f4pga f4pga_devices.json \
  --trellis trellis_ecp5.json \
  --output canonical_device_model.json
```

### 3. Review Output

```bash
cat canonical_device_model.json | python3 -m json.tool | less
```

## Input Format

### device_specs.json (Datasheet)

Parsed from vendor datasheets by `parse_datasheets.py` (companion tool).

```json
{
  "source": "datasheet",
  "devices": {
    "xcvu9p-flga2104-2L": {
      "name": "Xilinx Virtex UltraScale+ XCVU9P",
      "device_code": "xcvu9p",
      "package": "flga2104",
      "speed_grade": "-2L",
      "parts": [
        {
          "name": "CLB",
          "type": "CLB",
          "count": 182400,
          "io_per_unit": 50,
          "note": "Configurable Logic Blocks"
        },
        {
          "name": "BRAM",
          "type": "BRAM",
          "count": 912,
          "io_per_unit": 1024
        },
        ...
      ]
    }
  }
}
```

### f4pga_devices.json (f4pga Database)

From f4pga repository or cached download.

```json
{
  "source": "f4pga",
  "schema_version": "2.0",
  "devices": {
    "xcvu9p_flga2104": {
      "name": "Xilinx Virtex UltraScale+ XCVU9P-FLGA2104",
      "family": "vu",
      "parts": [
        {
          "name": "CLB",
          "type": "CLB",
          "count": 182400,
          "io_per_unit": 50
        },
        ...
      ],
      "routing": {
        "local": 1641600,
        "regional": 2500000,
        "long_lines": 18720
      }
    }
  }
}
```

### trellis_ecp5.json (Project Trellis)

ECP5 bitstream reference and device details.

```json
{
  "source": "trellis",
  "schema_version": "1.0",
  "devices": {
    "LFE5U85F": {
      "name": "Lattice ECP5 LFE5U85F",
      "family": "ecp5",
      "parts": [
        {
          "name": "SLICE",
          "type": "CLB",
          "count": 10848,
          "io_per_unit": 4
        },
        ...
      ]
    }
  }
}
```

## Output Format

### canonical_device_model.json

```json
{
  "schema_version": "1.0",
  "generation_timestamp": "2026-06-10T14:32:15.123456Z",
  "source_summary": {
    "datasheet_devices": 2,
    "f4pga_devices": 2,
    "trellis_devices": 1,
    "merged_devices": 4
  },
  "devices": {
    "xcvu9p-flga2104-2L": {
      "device": {
        "name": "xcvu9p-flga2104-2L",
        "sources": ["datasheet", "f4pga"],
        "source_agreement": {
          "all_agree": true,
          "source_count": 2
        }
      },
      "parts": [
        {
          "name": "CLB",
          "type": "CLB",
          "count": {
            "value": 182400,
            "source": "datasheet",
            "confidence": "high",
            "notes": null
          },
          "io_per_unit": {
            "value": 50,
            "source": "datasheet",
            "confidence": "high"
          },
          "total_io": {
            "value": 9120000,
            "source": "datasheet",
            "confidence": "high"
          }
        },
        ...
      ],
      "routing": {
        "local": {
          "value": 1641600,
          "source": "datasheet",
          "confidence": "medium",
          "note": "Inferred from 182400 CLBs at ~9 local wires/CLB"
        },
        "regional": {
          "value": 2500000,
          "source": "datasheet",
          "confidence": "medium",
          "note": "Inferred from 182400 CLBs at ~13.7 regional/CLB"
        }
      },
      "validation": {
        "consistency_score": 0.95,
        "conflicts": 0,
        "warnings": 0,
        "issues": [],
        "confidence": "high"
      },
      "audit": {
        "conflicts_log": [
          {
            "field": "parts.DSP.count",
            "sources": {
              "datasheet": 3456,
              "f4pga": 3480
            },
            "resolution": "3456 (datasheet)",
            "severity": "warning"
          }
        ],
        "warnings": [
          "Only 80% of parts from datasheet; others inferred or from secondary sources"
        ]
      }
    }
  },
  "global_validation": {
    "total_devices": 4,
    "high_confidence_devices": 3,
    "devices_with_conflicts": 1,
    "overall_quality_score": 0.75
  }
}
```

## Key Fields

### device

- `name`: Device identifier (from datasheet)
- `sources`: Array of sources this device appears in
- `source_agreement`: Whether all sources agree on specs

### parts[N]

- `name`, `type`: Part name and normalized type (CLB, BRAM, DSP, IOB, etc.)
- `count`: SpecValue with value, source, confidence, notes
- `io_per_unit`: I/O pins per logic unit
- `total_io`: Total I/O capacity (count × io_per_unit)

### routing

- `local`: Local interconnect resources (per-CLB wiring)
- `regional`: Regional routing (span-4, span-12, etc.)
- Each with value, source, confidence, and inference notes

### validation

- `consistency_score`: 0–1 float; 1.0 = perfect, < 0.6 = problematic
- `conflicts`: Count of disagreements between sources
- `warnings`: Count of suspicious or inferred fields
- `issues`: List of identified problems (top 5)
- `confidence`: Overall confidence (high/medium/low)

### audit

- `conflicts_log`: Detailed log of all conflicts (field, sources, resolution, severity)
- `warnings`: List of warning messages

### SpecValue (in JSON format)

- `value`: The actual spec value
- `source`: Where it came from (datasheet/f4pga/trellis/inferred)
- `confidence`: Confidence level (high/medium/low/unknown)
- `notes`: Optional explanation

## Merging Algorithm

### Phase 1: Normalize

- Device names: Remove hyphens, spaces, underscores; lowercase
- Part types: Map vendor-specific names to canonical types (CLB, BRAM, DSP, IOB)
- Numeric values: Extract from strings; identify units

### Phase 2: Load Sources

Load specs from all available sources (datasheet primary, f4pga/Trellis secondary):

1. **Datasheet** — authoritative; primary confidence source
2. **f4pga** — community database; cross-validates datasheet
3. **Trellis** — ECP5 bitstream reference; fills gaps for Lattice devices

### Phase 3: Merge

For each device:

1. Collect all parts from all sources
2. Normalize part types
3. Cross-validate part counts (flag conflicts if > 3% difference)
4. Select primary value (datasheet > f4pga > Trellis)
5. Boost confidence if secondary sources agree with primary
6. Log all conflicts with severity

### Phase 4: Infer

For fields missing from all sources:

- **Routing capacity**: Inferred from CLB count using empirical ratios:
  - Local wires: CLB count × 9
  - Regional: CLB count × 13.7
- Confidence marked as "medium" (inferred) or "low" (highly uncertain)

### Phase 5: Validate

Run consistency checks:

- Required parts present (CLB, IOB)
- Total I/O > 0
- Routing capacity plausible relative to CLB count
- Agreement across sources (boosts confidence)

Output **consistency_score** (0–1) and **confidence** (high/medium/low).

## Confidence Scoring

- **High**: Datasheet + cross-source validation agree (≥ 2 sources, < 3% mismatch)
- **Medium**: Datasheet only OR secondary sources agree; OR inferred with high consistency (> 0.8)
- **Low**: Conflicting sources OR weak evidence (< 0.6 consistency)
- **Unknown**: No source data available

## Conflict Detection

Conflicts are logged when:

1. **Numeric mismatch** > 3% between sources
2. **Missing required part** (CLB, IOB, etc.)
3. **Inconsistent routing** (routing < CLB count, or > 100× CLB count)
4. **Inferred fields** (marked with "medium" or "low" confidence)

Each conflict includes:

- Field path (e.g., `parts.DSP.count`)
- All source values
- Resolution (chosen value + rationale)
- Severity (warning/error)

## API Usage

### Python

```python
from merge_device_sources import DeviceSpecMerger

# Create merger
merger = DeviceSpecMerger(output_dir=".")

# Load specs
merger.load_datasheet_specs("device_specs.json")
merger.load_f4pga_specs("f4pga_devices.json")
merger.load_trellis_specs("trellis_ecp5.json")

# Merge all devices
result = merger.merge_all_devices()

# Write canonical model
output_path = merger.write_canonical_model("canonical_device_model.json")
print(f"Canonical model written to {output_path}")

# Access specific device
xcvu9p_specs = result["devices"]["xcvu9p-flga2104-2L"]
print(f"Confidence: {xcvu9p_specs['validation']['confidence']}")
print(f"CLB count: {xcvu9p_specs['parts'][0]['count']['value']}")
```

### CLI

```bash
# Merge with defaults
python3 merge_device_sources.py

# Custom paths
python3 merge_device_sources.py \
  --datasheet my_datasheets.json \
  --f4pga my_f4pga.json \
  --trellis my_trellis.json \
  --output my_model.json

# Verbose logging
python3 merge_device_sources.py -v

# Download f4pga database (stub for production)
python3 merge_device_sources.py --download-f4pga
```

## Testing

### Run Unit Tests

```bash
python3 test_merge_device_sources.py
```

Tests cover:

- Name normalization (device, part types)
- Numeric extraction and comparison
- Spec loading (all sources)
- Conflict detection
- Consistency validation
- Routing inference
- Output serialization
- Integration with sample data

### Generate Test Data

```bash
python3 generate_sample_device_specs.py --output-dir test_data

# Creates test_data/{device_specs,f4pga_devices,trellis_ecp5}.json
```

## Production Checklist

Before using in production:

- [ ] Verify datasheet specs match official vendor documentation
- [ ] Cross-validate f4pga database against real silicon (known CLB counts)
- [ ] Test on known device (e.g., XCVU9P): spec should match datasheet table
- [ ] Review conflicts_log in output; investigate any "error" severity entries
- [ ] Confirm consistency_score > 0.8 for critical devices
- [ ] Ensure all required parts present (CLB, BRAM, DSP, IOB)
- [ ] Validate routing estimates against published fabric specs

## Extending the Tool

### Adding a New Source

1. Add SourceType enum variant:
   ```python
   class SourceType(Enum):
       MY_SOURCE = "my_source"
   ```

2. Implement loader:
   ```python
   def load_my_source_specs(self, filepath: str) -> None:
       try:
           with open(filepath, 'r') as f:
               self.my_source_specs = json.load(f)
       except FileNotFoundError:
           logger.warning(f"Source not found at {filepath}")
           self.my_source_specs = {}
   ```

3. Integrate into merge:
   ```python
   def merge_device(self, device_name: str) -> Dict[str, Any]:
       # ... existing code ...
       # Add merge logic for my_source specs
   ```

### Custom Validation Rules

Override `validate_consistency()` to add domain-specific checks:

```python
def validate_consistency(self, device_name, parts, routing):
    score, issues = super().validate_consistency(device_name, parts, routing)
    
    # Custom check: device must have at least N CLBs
    clb_count = next((p["count"]["value"] for p in parts if p["type"] == "CLB"), 0)
    if clb_count < 1000:
        issues.append("Device has too few CLBs for HFT pipeline")
        score -= 0.2
    
    return score, issues
```

## Troubleshooting

### Issue: "Device not found in any source"

**Cause**: Device name doesn't match across sources.

**Fix**: Check normalization in source file names. Add manual mapping if needed.

### Issue: "High conflict count (> 5)"

**Cause**: Sources strongly disagree on specs.

**Fix**: Review conflicts_log; pick most reliable source manually; file upstream issue.

### Issue: "Consistency score < 0.6"

**Cause**: Inferred fields or missing data.

**Fix**: Provide explicit specs for missing parts; don't rely on inference alone.

## References

- [Xilinx Virtex UltraScale+ datasheets](https://docs.xilinx.com/)
- [f4pga project](https://f4pga.readthedocs.io/)
- [Project Trellis (ECP5 bitstream)](https://github.com/YosysHQ/prjtrellis)
- [Lattice MachXO3/MachXO3D datasheets](https://www.latticesemi.com/)

## License

Part of the fpga-rtl HFT pipeline project.
