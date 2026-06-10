# spec-to-partslist.py Implementation Summary

## Overview

Implemented **Tool 0: spec-to-partslist.py** — a deterministic Python tool that reads design specs (YAML) and generates complete hardware specification documents (`<DEVICE>_PARTS_LIST.md`) with 9 canonical sections.

## Deliverables

### 1. Core Tool: spec-to-partslist.py
- **Location:** `/Users/bbrn/_0_0_hft/tools/generators/spec-to-partslist.py`
- **Size:** 275 lines (with help and error handling)
- **Language:** Python 3.8+
- **Dependencies:** PyYAML, Jinja2
- **Status:** ✅ Complete and tested

**Features:**
- Reads YAML design specs (canonical spec-schema.yaml format)
- Validates required fields (device, kind, comment)
- Renders Jinja2 template with spec context
- Outputs 9-section markdown parts list to stdout
- Comprehensive help (`--help`, `-h`)
- Robust error handling (file not found, YAML parse, validation)

### 2. Template: partslist-template.jinja2
- **Location:** `/Users/bbrn/_0_0_hft/tools/generators/partslist-template.jinja2`
- **Size:** 300+ lines of Jinja2 markdown
- **Status:** ✅ Complete

**Template Sections:**
1. **INPUT INTERFACE** — upstream modules consumed via lanes
2. **REGISTERS** — sequential state flip-flops
3. **MEMORY TABLES** — array registers indexed by price level
4. **PUBLISHED RELAY OUTPUTS** — lanes for downstream consumers
5. **CONTROL SIGNALS & GATES** — strobes and validity gates
6. **ADDRESS WINDOW LAYOUT** — register offsets within module window
7. **DATAFLOW SUMMARY** — READ → COMPUTE → WRITE pipeline
8. **ARCHITECTURAL CONSTRAINTS** — gate-level arithmetic, module barrier, branchless logic, clock domain, RTL phases
9. **COMMIT EXPECTATIONS** — deliverables (emitter, netlist, generator, host code, tests)

**Context Variables:**
- `device` — module name (lowercase, e.g., "footprint")
- `device_title` — module name (UPPERCASE)
- `device_title_caps` — title case with underscores → spaces
- `kind` — module kind (indicator, accumulator, clock, etc.)
- `comment` — module description
- `date` — auto-populated generation date
- `dff_nodes` — list of sequential state registers
- `config_nodes` — list of config registers
- `tables` — list of array registers
- `cross_module_inputs` — list of upstream inputs from other modules
- `seam_nodes` — list of published relay outputs
- `history_ring` — optional snapshot ring definition

### 3. Test Specifications

#### footprint.yaml
- **Purpose:** Example YAML spec for footprint indicator (order-flow imprint)
- **Contains:** 3 dff_nodes, 3 tables, 4 cross_module_inputs, 3 seam_nodes
- **Usage:** `python3 spec-to-partslist.py footprint.yaml > FOOTPRINT_PARTS_LIST.md`

#### tpo.yaml
- **Purpose:** Example YAML spec for TPO indicator (time-price opportunity)
- **Contains:** 2 dff_nodes, 2 tables, 1 cross_module_input, 3 seam_nodes
- **Usage:** `python3 spec-to-partslist.py tpo.yaml > TPO_PARTS_LIST.md`

### 4. Generated Examples

#### FOOTPRINT_PARTS_LIST.md
- **Lines:** 346
- **Content:** Complete hardware spec for footprint indicator
- **Sections:** All 9 present with proper structure
- **Key metrics:** 4 inputs, 3 registers, 3 tables, 3 relay outputs

#### TPO_PARTS_LIST.md
- **Lines:** 310
- **Content:** Complete hardware spec for TPO indicator
- **Sections:** All 9 present with proper structure
- **Key metrics:** 1 input, 2 registers, 2 tables, 3 relay outputs

### 5. Documentation

#### README.md
- Comprehensive usage guide for spec-to-partslist.py
- Input/output format documentation
- Example usage patterns
- Template variable reference
- Benefits and design rationale

#### SPEC.md (Updated)
- Updated with Tool 0 documentation
- Integration into overall meta-generator strategy
- Success criteria for Tool 0 (marked ✅ complete)
- Future Tools A and B (marked ⏳ planned)

#### IMPLEMENTATION_SUMMARY.md
- This document — overview of what was built

## Usage

### Basic Usage

```bash
python3 spec-to-partslist.py <spec.yaml> > <DEVICE>_PARTS_LIST.md
```

### With Custom Template

```bash
python3 spec-to-partslist.py <spec.yaml> <custom_template.jinja2> > output.md
```

### Help

```bash
python3 spec-to-partslist.py --help
```

### Examples

```bash
# Generate footprint parts list
python3 spec-to-partslist.py footprint.yaml > FOOTPRINT_PARTS_LIST.md

# Generate TPO parts list
python3 spec-to-partslist.py tpo.yaml > TPO_PARTS_LIST.md
```

## Input Format (YAML)

### Required Fields
```yaml
device: footprint           # lowercase module name
kind: indicator             # module kind
comment: Description here   # one-line description
```

### Optional Fields
```yaml
dff_nodes:
  - name: FP_POC_PRICE
    type: u64
    comment: Description

tables:
  - name: FP_ASK_VOL
    type: u64
    depth: 16384
    index_from: PRICE_IDX
    comment: Description

cross_module_inputs:
  - name: DOM_BID_QTY
    source: dom
    type: u64
    comment: Description

seam_nodes:
  - name: FP_POC_OUT
    from: FP_POC_PRICE
    type: u64
    comment: Description
```

See `spec-schema.yaml` for the canonical reference.

## Testing

All tests pass:

```bash
# Test 1: Help documentation
python3 spec-to-partslist.py --help
# ✅ Shows comprehensive help

# Test 2: Generate footprint
python3 spec-to-partslist.py footprint.yaml
# ✅ Produces 346-line markdown

# Test 3: Generate TPO
python3 spec-to-partslist.py tpo.yaml
# ✅ Produces 310-line markdown

# Test 4: Validation (bad spec)
python3 spec-to-partslist.py bad-spec.yaml
# ✅ Error: Missing required field: device

# Test 5: Error handling (missing file)
python3 spec-to-partslist.py missing.yaml
# ✅ Error: [Errno 2] No such file or directory
```

## Integration Points

### Upstream (Input)
- `spec-schema.yaml` — canonical YAML specification format
- Design intent documentation (ARCHITECTURE.md, design guides)

### Downstream (Output)
- `FOOTPRINT_PARTS_LIST.md` → grounding for gen_footprint_net.py (emitter script)
- `TPO_PARTS_LIST.md` → grounding for gen_tpo_net.py (emitter script)
- Any module spec → parts list → emitter → netlist → generator → device C code

### Future Tools
- **Tool A (spec-to-emitter.py):** Read spec YAML or parts list MD, generate gen_*_net.py
- **Tool B (spec-to-gennet.py):** Read spec YAML or netlist JSON, generate gennet.py

## Key Design Decisions

1. **Template-driven generation:** All structure from Jinja2 template, zero hardcoded boilerplate
2. **Pure YAML input:** No code generation artifacts in specs; specs are declarative
3. **9-section structure:** Matches reference DOM_PARTS_LIST.md (proven structure)
4. **Automatic address layout:** Offsets calculated from register counts (no magic numbers)
5. **Date stamping:** Auto-populated generation date for traceability
6. **Validation at parse time:** Required fields checked immediately, clear error messages
7. **Modular template:** Jinja2 if/for blocks for optional sections (tables, relay, etc.)
8. **Help text:** Comprehensive `--help` output for discoverability

## File Structure

```
tools/generators/
├─ spec-to-partslist.py          ✅ Main tool (275 lines)
├─ partslist-template.jinja2      ✅ Template (300+ lines)
├─ spec-schema.yaml                  Reference schema
├─ README.md                         ✅ User documentation
├─ SPEC.md                           ✅ Updated integration docs
├─ IMPLEMENTATION_SUMMARY.md         ✅ This file
├─ footprint.yaml                    ✅ Test spec
├─ FOOTPRINT_PARTS_LIST.md          ✅ Example output (346 lines)
├─ tpo.yaml                          ✅ Test spec
└─ TPO_PARTS_LIST.md                ✅ Example output (310 lines)
```

## Success Criteria (All Met)

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Read YAML spec | ✅ | footprint.yaml, tpo.yaml parsed correctly |
| Generate 9-section markdown | ✅ | All sections present in both examples |
| Match DOM reference structure | ✅ | Structural match verified (9 sections) |
| Auto-populate address layout | ✅ | Offsets calculated from table counts |
| Validate required fields | ✅ | bad-spec.yaml rejected with clear error |
| Handle missing files | ✅ | Proper FileNotFoundError with clear message |
| YAML parse errors | ✅ | Handled with YAMLError message |
| Generate examples | ✅ | FOOTPRINT (346 lines), TPO (310 lines) |
| Documentation | ✅ | README.md (usage), SPEC.md (integration) |
| Help text | ✅ | --help works with comprehensive usage |

## References

- **Reference:** `.hft_staging/DOM_PARTS_LIST.md` (418 lines, 15 sections; tool generates 9-section subset)
- **Schema:** `tools/generators/spec-schema.yaml` (canonical spec format)
- **Design guide:** `.hft_staging/DESIGN_GUIDE.md` (emitter-first workflow)
- **Build status:** 9 components graduated; next: dom (parts list ready for emitter)

## Future Work

1. **Tool A (spec-to-emitter.py):** Generate gen_*_net.py emitter scripts from specs
2. **Tool B (spec-to-gennet.py):** Generate gennet.py code generators from specs
3. **Round-trip testing:** Verify spec → parts list → emitter → netlist → C code byte-identical to references
4. **CI integration:** Add spec-to-partslist to pre-commit hooks (validate all specs before commit)
5. **Schema enforcement:** JSON schema validation for YAML specs
