# parse_datasheets.py Quick Start

## TL;DR: Extract VU9P Specs in One Line

```bash
cd fpga-rtl/tools
python3 parse_datasheets.py -o device_specs.json
```

Done. You now have `device_specs.json` with complete VU9P specifications.

## Common Use Cases

### 1. Generate Default VU9P Spec

```bash
python3 parse_datasheets.py -o device_specs.json
```

Creates `device_specs.json` with hardcoded VU9P specs from XILINX_VU9P_SPEC_EXTRACTION.md.

### 2. Extract from PDF Datasheet

```bash
# If you have a Xilinx datasheet PDF:
python3 parse_datasheets.py -d DS922_VU9P.pdf -o device_specs.json -v
```

The tool will try to:
- Parse device name, package, speed grade from PDF
- Extract resource counts from tables
- Fall back to hardcoded specs if parsing fails

### 3. Override Device Identity

```bash
# Use VU9P resource counts but with custom device name
python3 parse_datasheets.py \
  --device-name xcvu13p-flga2104-3L \
  --speed-grade -3 \
  -o vu13p_specs.json
```

Output has VU13P device ID but keeps VU9P's resource baseline (override more fields as needed).

### 4. Validate Without Writing

```bash
python3 parse_datasheets.py --validate-only -v
```

Checks spec validity without creating output file. Good for testing.

## Output: device_specs.json

The tool creates a JSON file with this structure:

```json
{
  "device": {
    "name": "xcvu9p-flga2104-2L",
    "family": "Virtex UltraScale+",
    "package": "FLGA2104",
    "speed_grade": "-2"
  },
  "resources": {
    "clbs": 182400,
    "luts": 1457600,
    "flip_flops": 2918400,
    "bram36": 2160,
    "dsp48e2": 6840,
    "gty_transceivers": 32,
    "io_banks": 44,
    ...
  },
  "connectivity": {
    "lut_inputs": 6,
    "lut_outputs": 1,
    "ff_per_clb": 16,
    "carry_chain_length": 4,
    ...
  },
  "structure": { ... },
  "metadata": { ... }
}
```

Use this JSON as input to the next pipeline stage: `gen_device_net.py`.

## Next Steps

1. **Generate netlist from spec:**
   ```bash
   python3 gen_device_net.py device_specs.json > device.net.json
   ```

2. **Validate netlist:**
   ```bash
   python3 validate.py device.net.json
   ```

3. **Generate device C:**
   ```bash
   python3 gennet.py device.net.json > device_gen.h
   ```

## Troubleshooting

**Q: No output file created?**  
A: Check verbose mode:
```bash
python3 parse_datasheets.py -v
```
Look for validation errors or file permission issues.

**Q: PDF not parsing?**  
A: Install pdfplumber:
```bash
pip install pdfplumber
```
Or use command-line overrides:
```bash
python3 parse_datasheets.py \
  --device-name xcvu9p-flga2104-2L \
  --package FLGA2104 \
  --speed-grade -2
```

**Q: How accurate are the specs?**  
A: VU9P specs are extracted from official Xilinx datasheets (DS922, PG252). See `XILINX_VU9P_SPEC_EXTRACTION.md` for full documentation and citations.

## See Also

- `README_PARSE_DATASHEETS.md` — Full documentation
- `XILINX_VU9P_SPEC_EXTRACTION.md` — Canonical VU9P specification source
