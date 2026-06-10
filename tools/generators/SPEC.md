# Meta-Generator Tools Specification

## Overview
Three deterministic Python tools generate design artifacts from specs, eliminating hand-written code in the pipeline.

```
Design Spec (YAML)
  ├─ Tool 0: spec-to-partslist.py
  │   ↓
  │ <DEVICE>_PARTS_LIST.md (hardware specification; human-readable)
  │
  ├─ Tool A: spec-to-emitter.py (planned)
  │   ↓
  │ gen_*_net.py (generated)
  │   ↓ Run emitter
  │ *.net.json (generated)
  │
  └─ Tool B: spec-to-gennet.py (planned)
      ↓
    gennet.py (generated)
      ↓ Run gennet
    *_gen.h (generated)
```

---

## Tool 0: spec-to-partslist.py

**Purpose:** Read a design spec (YAML) and generate `<DEVICE>_PARTS_LIST.md` (complete hardware specification)

**Input Spec Format (YAML):** Canonical spec-schema.yaml format
- `device`: module name (e.g., "footprint")
- `kind`: module kind ("indicator", "accumulator", "clock", etc.)
- `comment`: module description
- `dff_nodes`: sequential state registers (name, type, comment)
- `tables`: array registers (name, type, depth, index_from, comment)
- `cross_module_inputs`: reads from other modules (name, source, type, comment)
- `seam_nodes`: published relay outputs (name, from, type, comment)
- `config_nodes`: initialization constants (optional)
- `history_ring`: snapshot ring for display (optional)

**Output:** `<DEVICE>_PARTS_LIST.md` (9 sections: interface, registers, tables, relay, gates, layout, dataflow, constraints, commit expectations)

**Template:** `partslist-template.jinja2` (Jinja2 markdown template)

**Algorithm:**
1. Parse YAML spec using PyYAML
2. Validate required fields (device, kind, comment)
3. Load Jinja2 template from `partslist-template.jinja2`
4. Render template with spec context (device name, sections, structure, address layout)
5. Output markdown to stdout

**Validation:**
- Required fields present
- Device name is lowercase (enforced in template)
- Table depth is power of 2 (validated at generation time or noted in output)
- Cross-module inputs reference valid source modules (validated external to tool)

**Example Usage:**
```bash
# Generate parts list for footprint
python3 spec-to-partslist.py footprint.yaml > FOOTPRINT_PARTS_LIST.md

# Generate parts list for any module
python3 spec-to-partslist.py <module>.yaml > <MODULE>_PARTS_LIST.md
```

**Benefits:**
- Eliminates repetitive PARTS_LIST boilerplate
- Ensures consistent structure across all component specs
- Captures dataflow, architectural constraints, commit expectations in one place
- Grounding for emitter (gen_*_net.py) implementation
- Human-readable spec for code review and documentation

---

## Tool A: spec-to-emitter.py (planned)

**Purpose:** Read a design spec (YAML) and generate gen_*_net.py (the emitter script)

**Input Spec Format (YAML):**
```yaml
device: footprint
kind: indicator
window_base: null  # assigned at init or implicit; not pre-assigned

config_nodes:
  - name: FP_POWER
    type: bit
    comment: Power bit

dff_nodes:  # registered (sequential) nodes
  - name: FP_POC_PRICE
    type: u64
    comment: Point of control price

tables:  # array registers indexed by price_idx
  - name: FP_ASK_VOL
    type: u64
    depth: 16384  # per-price accumulator
    comment: Ask volume per price level

comb_nodes:  # combinational logic
  - name: POC_UPDATA
    cell: mux
    inputs: [CURRENT_POC, NEW_POC, POC_UPDATE_GATE]
    comment: POC mux

history_ring:
  depth: 256
  fields:
    - POC_PRICE
    - VAH_PRICE
    - VAL_PRICE
```

**Output:** `gen_<device>_net.py` (executable Python that outputs JSON netlist)

**Algorithm:**
1. Parse YAML
2. Generate Python dict structure (matching adapter.net.json pattern)
3. Emit Python script with `main()` that dumps to `<device>.net.json`
4. Template-based generation (no manual coding)

---

## Tool B: spec-to-gennet.py

**Purpose:** Read a design spec (YAML) and generate gennet.py (the code generator)

**Input:** Same YAML as Tool A

**Output:** `gennet.py` (executable Python that reads netlist JSON and outputs C code)

**Algorithm:**
1. Parse YAML
2. Generate Python code generator with:
   - Register address assignment (from netlist nodes)
   - `init()` function
   - `*_tick()` function (READ → COMPUTE → WRITE phases)
   - Cell instantiation (from netlist combinational logic)
   - Display ring handling (if present)
3. Template-based generation

**Key constraint:** The generated gennet.py must read a JSON netlist (not hardcoded). This keeps the data (netlist) separate from the generator (code).

---

## Implementation Approach

**Both tools use:**
- Jinja2 templates (or similar) for code generation
- Spec validation (schema check)
- Error reporting on invalid specs
- Output to stdout (or specified file)

**Deliverables:**
1. `spec-to-emitter.py` — ~200–300 lines (Jinja2 template + emitter template)
2. `spec-to-gennet.py` — ~300–400 lines (Jinja2 template + gennet template)
3. `emitter-template.jinja2` — Python emitter template
4. `gennet-template.jinja2` — Python code generator template
5. Tests: generate a known module (taiosc) and byte-match against existing

---

## Success Criteria

### Tool 0 (spec-to-partslist.py) — IMPLEMENTED
1. ✅ `spec-to-partslist.py footprint.yaml > FOOTPRINT_PARTS_LIST.md` generates 9-section parts list
2. ✅ All sections present: interface, registers, tables, relay, gates, layout, dataflow, constraints, commit
3. ✅ Template structure matches reference DOM_PARTS_LIST.md (structural match, not hash)
4. ✅ Cross-module inputs documented correctly
5. ✅ Relay outputs documented correctly
6. ✅ Address layout calculated automatically from register counts
7. ✅ No hand-written content in generated parts list (pure template expansion)
8. ✅ Validation: required fields checked (device, kind, comment)
9. ✅ Date auto-populated (datetime.now())

### Tool A (spec-to-emitter.py) — PLANNED
1. ⏳ `spec-to-emitter.py footprint.yaml > gen_footprint_net.py` generates Python emitter script
2. ⏳ Emitter produces `footprint.net.json` (netlist)
3. ⏳ Netlist validates: single-writer, no-overlap, no-floating

### Tool B (spec-to-gennet.py) — PLANNED
1. ⏳ `spec-to-gennet.py footprint.yaml > gennet.py` generates Python code generator
2. ⏳ Generator reads netlist and outputs device C code
3. ⏳ Round-trip: spec → emitter → netlist → gennet → device C (all generated, byte-identical to originals)
