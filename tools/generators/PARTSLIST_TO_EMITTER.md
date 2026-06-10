# partslist-to-emitter.py

Convert a `PARTS_LIST.md` file into a Python emitter script (`gen_*_net.py`).

## Purpose

This tool automates **DESIGN_GUIDE step 3** (netlist generation): taking a hardware specification document (PARTS_LIST.md) and outputting a Python emitter script that produces the declarative netlist (`.net.json`).

The emitter-first workflow:
1. **PARTS_LIST.md** — Human-readable hardware spec (parts, registers, interconnects, behavior)
2. **gen_*_net.py** (this tool's output) — Python emitter script that builds the netlist
3. **<device>.net.json** (emitter's output) — Declarative netlist (single-writer, no-overlap, no-floating)
4. **gennet.py** — Netlist generator (produces `<device>_gen.h`, the device C code)

## Usage

```bash
python3 partslist-to-emitter.py <PARTS_LIST.md> <output_dir> [device_name]
```

### Arguments

- **`<PARTS_LIST.md>`** — Input file (required). Path to the hardware specification.
- **`<output_dir>`** — Output directory (required). Where to write `gen_<device>_net.py`.
- **`[device_name]`** — Optional override. Device name (inferred from PARTS_LIST title if not provided).

### Example

```bash
# Parse DOM_PARTS_LIST.md and generate gen_dom_net.py
python3 tools/generators/partslist-to-emitter.py .hft_staging/DOM_PARTS_LIST.md .hft_staging/dom dom

# Verify the emitter works
cd .hft_staging/dom
python3 gen_dom_net.py
cat dom.net.json
```

## Output

The generated `gen_<device>_net.py` file is a standalone Python script that:
- Declares a `NET` dictionary containing the netlist specification
- Extracts config nodes (input lanes) from PARTS_LIST section 1
- Extracts DFF nodes (registered state) from sections 3, 4, 7, 9
- Extracts array tables (price-indexed, etc.) from section 2
- Extracts relay nodes (downstream outputs) from section 8
- Extracts event counters from section 6
- Includes a `main()` function that writes `<device>.net.json`
- Is executable: `python3 gen_<device>_net.py > <device>.net.json`

## Requirements

### Input: PARTS_LIST.md Structure

The PARTS_LIST.md must follow the standard structure:

```markdown
# <DEVICE> Architectural Parts List

**Purpose:** ...
**Status:** ...

## 1. INPUT INTERFACE (from ...)

- `INPUT_NAME` — description (marked as 'bit' or 'u64' based on context)

## 2. PRICE-INDEXED MEMORY TABLES (Primary Accumulators)

- `TABLE_NAME[16384]` — 64-bit flip-flop counters

## 3. BEST-PRICE REGISTERS (Eager Tracking)

- `BEST_PRICE_REG` — 64-bit flip-flop

## 4. RUNNING TOTALS (Sum Accumulators)

- `TOTAL_REG` — 64-bit accumulator

## 6. EVENT COUNTERS (Diagnostic)

- `PKT_COUNT_REG` — 64-bit accumulator

## 7. METADATA

- `LAST_FEED_TIME_REG` — 64-bit flip-flop

## 8. RELAY OUTPUTS (Downstream Feed for Indicators)

- `REL_BID_PRICE[0..9]` — 10 price registers

## 9. INTERNAL STATE (Previous Price Tracking)

- `PREV_BID_PRICE` — 64-bit flip-flop
```

### Parser Capabilities

The parser extracts:

| Section | Extracts | Destination |
|---------|----------|-------------|
| 1. INPUT INTERFACE | Register names, types | `config_nodes` |
| 2. PRICE-INDEXED | Table names, depths | `tables` |
| 3. BEST-PRICE | Registers | `dff_nodes` |
| 4. RUNNING TOTALS | Accumulators | `dff_nodes` |
| 6. EVENT COUNTERS | Counter registers | `counters` |
| 7. METADATA | State registers | `dff_nodes` |
| 8. RELAY OUTPUTS | Downstream lanes | `relay_nodes` |
| 9. INTERNAL STATE | History registers | `dff_nodes` |

**Type inference:**
- Single-bit registers: marked as `'bit'` if description contains 'strobe', 'flag', 'empty', 'valid', 'enable'
- Multi-bit registers: marked as `'u64'` (default)

### Template (emitter-template.jinja2)

The tool uses a Jinja2 template to generate the emitter script. The template:
- Renders the parsed spec into Python code
- Declares the `NET` dict with all extracted nodes
- Includes proper JSON serialization in `main()`
- Handles escaping and formatting automatically

## Generated Emitter Structure

```python
#!/usr/bin/env python3
"""gen_<device>_net.py — EMITTER: writes <device>.net.json."""

import json

NET = {
    "device": "<device>",
    "window_base": "0x...",
    "kind": "...",
    "comment": "...",
    "config_nodes": [...],
    "dff_nodes": [...],
    "tables": [...],
    "relay_nodes": [...],
    "counters": [...],
    # ... other sections
}

def main():
    with open("<device>.net.json", "w") as f:
        json.dump(NET, f, indent=2)
        f.write("\n")
    print(f"emitted <device>.net.json")

if __name__ == "__main__":
    main()
```

## Workflow Integration

### Step 1: Create PARTS_LIST.md

Write the hardware specification document (see example: `.hft_staging/DOM_PARTS_LIST.md`).

### Step 2: Generate Emitter

```bash
python3 tools/generators/partslist-to-emitter.py \
  .hft_staging/<MODULE>_PARTS_LIST.md \
  .hft_staging/<module> \
  <module>
```

### Step 3: Run Emitter

```bash
cd .hft_staging/<module>
python3 gen_<module>_net.py
```

Output: `.hft_staging/<module>/<module>.net.json`

### Step 4: Validate Netlist

```bash
# Run the project gate
.hft_staging/gate.sh .hft_staging/<module>
```

The gate validates:
- Single-writer (each register has one writer)
- No-overlap (registers don't collide in address space)
- No-floating (all inputs are declared or consumed)

### Step 5: Generate Device Code

```bash
cd .hft_staging/<module>
python3 gennet.py <module>.net.json > <module>_gen.h
```

Output: `.hft_staging/<module>/<module>_gen.h` (committed to git)

## Error Handling

### Errors

```
ERROR: Jinja2 not installed. Install with: pip install jinja2
```
→ Install the template engine: `pip install jinja2`

```
ERROR: Validation failed: Missing device name
```
→ Check PARTS_LIST.md title: `# <DEVICE> Architectural Parts List`

```
Template 'emitter-template.jinja2' not found.
```
→ Ensure `emitter-template.jinja2` is in the same directory as the tool.

## Files

- **`partslist-to-emitter.py`** — Main tool (parser + generator)
- **`emitter-template.jinja2`** — Jinja2 template for emitter generation
- **`PARTSLIST_TO_EMITTER.md`** — This documentation

## References

- `DESIGN_GUIDE.md` — Emitter-first build workflow
- `DOM_PARTS_LIST.md` — Example parts list (DOM component)
- `.hft/taiosc/gen_taisoc_net.py` — Reference emitter (taiosc)
- `.hft/nic/gen_nic_net.py` — Reference emitter (NIC gateway)

## Testing

Run the example:

```bash
# From project root:
python3 tools/generators/partslist-to-emitter.py \
  .hft_staging/DOM_PARTS_LIST.md \
  /tmp/test_dom \
  dom

# Verify output
cd /tmp/test_dom
python3 gen_dom_net.py
python3 -m json.tool dom.net.json | head -50
```

Expected output: valid `dom.net.json` with config_nodes, dff_nodes, tables, relay_nodes, counters.

## Known Limitations

1. **Inline comments in PARTS_LIST:** Parser assumes one register per line (backtick-delimited names).
2. **Complex descriptions:** Multiline descriptions are truncated to 80 chars in JSON.
3. **Custom cell types:** Parser infers `cell_mux`, `cell_addsub`, etc. from description keywords; if not found, no cell type is assigned (gennet must infer or error).
4. **Index ranges:** Array indices are parsed as strings (e.g., `"0..9"` or `"16384"`); depth inference is heuristic.

## Future Enhancements

- [ ] Validate PARTS_LIST.md against a JSON schema (ensure required sections)
- [ ] Generate validation script (`validate.py`) alongside emitter
- [ ] Support custom cell type declarations in PARTS_LIST
- [ ] Extract address layout table from section 12 (ADDRESS WINDOW LAYOUT)
- [ ] Generate Makefile targets for the component
- [ ] Support YAML/JSON PARTS_LIST input as alternative to Markdown

---

**Status:** ✅ Functional. Tested on DOM_PARTS_LIST.md.
