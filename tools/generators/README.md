# Meta-Generator Tools

Deterministic Python tools that eliminate hand-written boilerplate from the HFT pipeline architecture (flip-flop-level RTL in C).

## Tool 0: spec-to-partslist.py ✅ IMPLEMENTED

Read a design spec (YAML) and generate `<DEVICE>_PARTS_LIST.md` — the complete hardware specification with 9 sections: interface, registers, tables, relay outputs, control signals, address layout, dataflow, architectural constraints, and commit expectations.

### Usage

```bash
python3 spec-to-partslist.py <spec.yaml> [template.jinja2]
```

### Example

```bash
# Generate parts list for footprint
python3 spec-to-partslist.py footprint.yaml > FOOTPRINT_PARTS_LIST.md

# Generate parts list for TPO
python3 spec-to-partslist.py tpo.yaml > TPO_PARTS_LIST.md
```

### Input Spec Format (YAML)

See `spec-schema.yaml` for the canonical schema. Required fields:
- `device` — module name (lowercase, e.g., "footprint")
- `kind` — module kind ("indicator", "accumulator", "clock", "gateway", "memory", "oscillator")
- `comment` — module description

Optional fields:
- `dff_nodes` — sequential state registers (name, type, comment)
- `config_nodes` — initialization constants
- `tables` — array registers (name, type, depth, index_from, comment)
- `cross_module_inputs` — reads from other modules (name, source, type, comment)
- `seam_nodes` — published relay outputs (name, from, type, comment)
- `history_ring` — snapshot ring for display (depth, fields, comment)

### Output

Markdown file with 9 sections:
1. **INPUT INTERFACE** — upstream modules consumed via lanes
2. **REGISTERS** — sequential state flip-flops
3. **MEMORY TABLES** — array registers indexed by price level or address
4. **PUBLISHED RELAY OUTPUTS** — lanes for downstream consumers
5. **CONTROL SIGNALS & GATES** — strobes and validity gates
6. **ADDRESS WINDOW LAYOUT** — register offsets within module window
7. **DATAFLOW SUMMARY** — READ → COMPUTE → WRITE pipeline
8. **ARCHITECTURAL CONSTRAINTS** — gate-level arithmetic, module barrier, branchless logic, clock domain, RTL phases
9. **COMMIT EXPECTATIONS** — deliverables (emitter, netlist, generator, host code, tests)

### Template

`partslist-template.jinja2` — Jinja2 markdown template for parts list generation. Uses context:
- `device` — module name (lowercase)
- `device_title` — module name (uppercase)
- `device_title_caps` — module name (title case with underscores → spaces)
- `kind` — module kind
- `comment` — module description
- `date` — generation date (auto-populated)
- `dff_nodes` — list of flip-flop nodes
- `config_nodes` — list of config nodes
- `tables` — list of table definitions
- `cross_module_inputs` — list of upstream inputs
- `seam_nodes` — list of relay outputs

### Validation

- Required fields: `device`, `kind`, `comment`
- Device name is lowercase (enforced in template)
- File not found → FileNotFoundError
- YAML parse error → YAMLError

### Benefits

- Eliminates repetitive boilerplate (parts lists are all similar)
- Ensures consistent structure across all component specs
- Single source of truth: spec → parts list → grounding for emitter
- Human-readable spec for code review and documentation
- Auto-populates counts, offsets, and dataflow descriptions

---

## Tool 1: partslist-to-emitter.py ✅ IMPLEMENTED

Read a `<DEVICE>_PARTS_LIST.md` and generate `gen_<device>_net.py` — the emitter script that produces a declarative netlist in JSON format.

### Usage

```bash
python3 partslist-to-emitter.py <PARTS_LIST.md> <output_dir> [device_name]
```

### Example

```bash
# Generate emitter for DOM component
python3 partslist-to-emitter.py DOM_PARTS_LIST.md .hft_staging/dom dom

# Run the generated emitter to produce the netlist
cd .hft_staging/dom
python3 gen_dom_net.py
```

### Input: PARTS_LIST.md

Markdown file with hardware spec (sections: INPUT INTERFACE, REGISTERS, TABLES, RELAY OUTPUTS, etc.)

### Output

Python script `gen_<device>_net.py` that:
- Declares a `NET` dict with config_nodes, dff_nodes, tables, relay_nodes
- Extracts registers from PARTS_LIST sections 1–9
- Includes a `main()` function that outputs `<device>.net.json`
- Is executable: `python3 gen_<device>_net.py`

### Template

`emitter-template.jinja2` — Jinja2 Python template for emitter generation.

### Documentation

See `PARTSLIST_TO_EMITTER.md` for complete reference, examples, and workflow integration.

**Status:** ✅ Complete. Tested on DOM_PARTS_LIST.md and FOOTPRINT_PARTS_LIST.md.

---

## Tool B: spec-to-gennet.py (Planned)

Read a design spec (YAML) and generate `gennet.py` — the code generator that reads a netlist JSON and outputs device C code.

**Status:** Planned (depends on Tool 0 completion and gennet pattern extraction)

---

## Test Examples

### Footprint Spec

```bash
# Generate parts list
python3 spec-to-partslist.py footprint.yaml > FOOTPRINT_PARTS_LIST.md

# Output: 346-line markdown with 4 cross-module inputs, 3 registers, 3 tables, 3 relay outputs
```

### TPO Spec

```bash
# Generate parts list
python3 spec-to-partslist.py tpo.yaml > TPO_PARTS_LIST.md

# Output: 310-line markdown with 1 cross-module input, 2 registers, 2 tables, 3 relay outputs
```

---

## References

- **Canonical spec schema:** `spec-schema.yaml`
- **Architectural reference:** `.hft_staging/DOM_PARTS_LIST.md` (existing 418-line parts list)
- **Design guide:** `.hft_staging/DESIGN_GUIDE.md` (emitter-first workflow)
- **Build status:** 9 components graduated (adapter, wire, taiosc, tai, mac, internal, tai_cdc, nic, fifo_rx)
- **Next component:** dom (price-indexed tables) — parts list complete, awaiting emitter implementation

---

## Dependencies

- Python 3.8+
- PyYAML (for YAML parsing)
- Jinja2 (for template rendering)

**Installation:**
```bash
pip install pyyaml jinja2
```

---

## File Structure

```
tools/generators/
  ├─ spec-to-partslist.py          ✅ Implemented (265 lines) — YAML → PARTS_LIST.md
  ├─ partslist-template.jinja2      ✅ Implemented (300+ lines)
  ├─ spec-schema.yaml                  Reference schema
  ├─ SPEC.md                        ✅ Updated with Tool 0 docs
  │
  ├─ partslist-to-emitter.py       ✅ Implemented (280 lines) — PARTS_LIST.md → gen_*_net.py
  ├─ emitter-template.jinja2        ✅ Implemented (130 lines)
  ├─ PARTSLIST_TO_EMITTER.md       ✅ Documentation + examples
  │
  ├─ README.md                      ✅ This file
  │
  ├─ footprint.yaml                    Test spec (indicator)
  ├─ FOOTPRINT_PARTS_LIST.md        ✅ Generated example (346 lines)
  │
  ├─ tpo.yaml                          Test spec (indicator)
  ├─ TPO_PARTS_LIST.md              ✅ Generated example (310 lines)
  │
  ├─ spec-to-gennet.py              ⏳ Planned — PARTS_LIST.md → gennet.py
  └─ gennet-template.jinja2         ⏳ Planned
```
