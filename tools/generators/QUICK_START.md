# Quick Start: partslist-to-emitter

Generate a Python emitter script from a hardware parts list in 30 seconds.

## One-Liner

```bash
python3 tools/generators/partslist-to-emitter.py <DEVICE>_PARTS_LIST.md <output_dir> <device>
```

## Example: DOM Component

```bash
# Step 1: Generate the emitter
python3 tools/generators/partslist-to-emitter.py \
  .hft_staging/DOM_PARTS_LIST.md \
  .hft_staging/dom \
  dom

# Step 2: Run the emitter to produce the netlist
cd .hft_staging/dom
python3 gen_dom_net.py

# Step 3: Verify the netlist
python3 -m json.tool dom.net.json | head -50
```

## Example: Footprint Component

```bash
# Generate emitter
python3 tools/generators/partslist-to-emitter.py \
  tools/generators/FOOTPRINT_PARTS_LIST.md \
  /tmp/test \
  footprint

# Run it
cd /tmp/test
python3 gen_footprint_net.py
cat footprint.net.json
```

## Workflow

```
PARTS_LIST.md (human-spec)
  ↓
partslist-to-emitter.py
  ↓
gen_<device>_net.py (executable emitter)
  ↓
python3 gen_<device>_net.py
  ↓
<device>.net.json (declarative netlist)
  ↓
gennet.py (code generator)
  ↓
<device>_gen.h (device C code)
```

## Output

Generated emitter script `gen_<device>_net.py`:
- ✅ Valid Python (executable)
- ✅ Declares NET dict with all registers from PARTS_LIST
- ✅ Extracts config_nodes, dff_nodes, tables, relay_nodes
- ✅ Includes `main()` that outputs JSON netlist
- ✅ ~60 lines of clean, documented code

## What Gets Extracted

The parser reads PARTS_LIST.md sections and populates the emitter:

| Section | Extracts To |
|---------|-----------|
| 1. INPUT INTERFACE | `config_nodes` |
| 2. PRICE-INDEXED TABLES | `tables` |
| 3. BEST-PRICE REGISTERS | `dff_nodes` |
| 4. RUNNING TOTALS | `dff_nodes` |
| 6. EVENT COUNTERS | `counters` |
| 7. METADATA | `dff_nodes` |
| 8. RELAY OUTPUTS | `relay_nodes` |
| 9. INTERNAL STATE | `dff_nodes` |

## Type Inference

- Single-bit flags/strobes: `"type": "bit"`
- Everything else: `"type": "u64"`

Keywords that trigger `"bit"`: strobe, flag, empty, valid, enable

## Files Required

- `partslist-to-emitter.py` — main tool
- `emitter-template.jinja2` — Jinja2 template (must be in same directory)

## Files Produced

- `gen_<device>_net.py` — Generated emitter script (executable, committed to git)
- `<device>.net.json` — Netlist JSON (produced by running the emitter; validated then committed)

## Next Step After Generation

```bash
# Validate the netlist
.hft_staging/gate.sh .hft_staging/<module>

# This runs:
# 1. validate.py — checks single-writer, no-overlap, no-floating
# 2. gennet.py — generates <module>_gen.h from netlist
# 3. Build + test the component
```

## Troubleshooting

### `Jinja2 not installed`
```bash
pip install jinja2
```

### `Template 'emitter-template.jinja2' not found`
- Ensure `emitter-template.jinja2` is in `tools/generators/`
- Run from project root: `pwd` should contain `.hft_staging/`

### Generated emitter won't run
```bash
# Check syntax
python3 -m py_compile gen_<device>_net.py

# Run with error detail
python3 gen_<device>_net.py
```

## See Also

- `PARTSLIST_TO_EMITTER.md` — Full reference documentation
- `.hft_staging/DESIGN_GUIDE.md` — Emitter-first workflow
- `.hft_staging/DOM_PARTS_LIST.md` — Example parts list
- `.hft/taiosc/gen_taisoc_net.py` — Example generated emitter

---

**That's it!** The tool handles the boilerplate. Focus on the PARTS_LIST.md spec; the emitter is generated.
