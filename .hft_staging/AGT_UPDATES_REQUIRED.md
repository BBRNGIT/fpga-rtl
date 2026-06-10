# AGNT System Updates Required

**Status:** Design specification for updating AGNT to prevent architectural stubs  
**Blocked:** AGNT files are read-only in deployed mode; require update via development repo re-deployment

---

## Overview

The WAVE 1 stub issue (device C files with zero flip-flop logic) occurred because:
1. No architectural validation blocked incomplete specifications
2. Complexity-classification didn't flag emitter-first builds without complete specs as Complex
3. netlist-builder proceeded without validating that comb_nodes were present

These updates prevent repeat of this issue.

---

## Update 1: complexity-classification.md

**File:** `.claude/agents/AGNT/skills/complexity-classification.md`

**Add new repo-specific Complex trigger:**

Insert into the "Repo-specific Complex triggers" section (after line 33):

```markdown
   - Emitter-first build (code generation task) without complete architectural specification:
     If the spec lacks comb_nodes (gate-level logic definitions) or wiring specifications,
     classify as Complex and return to Planner. Incomplete specs → stubs → silent failures.
     Validation: spec must include all of (register state, inputs, outputs, logic, wiring).
```

**Rationale:** This flags any emitter-first build task that hasn't documented gate-level logic, forcing Planner decomposition to handle the architecture work before code generation begins.

---

## Update 2: netlist-builder.md

**File:** `.claude/agents/AGNT/netlist-builder.md`

**Add new section after "Mandatory grounding":**

Insert new section "Pre-Build Validation: Architectural Specification Completeness (CRITICAL)":

```markdown
## Pre-Build Validation: Architectural Specification Completeness (CRITICAL)

Before writing ANY code, validate that the specification is complete:

The spec is complete only if it includes ALL of:
1. Register state (dff_nodes, tables, history_ring) — ✓ Usually present
2. Input interface (cross_module_inputs) — ✓ Usually present
3. Output interface (seam_nodes) — ✓ Usually present
4. Combinational logic (comb_nodes with explicit cell definitions) — ❌ Usually missing
5. Wiring (signal flow between logic blocks) — ❌ Usually missing

Items 4–5 are load-bearing. Without them:
- Emitter generates stubs (register declarations with no logic)
- gennet produces empty COMPUTE phases
- Device passes gate 2a-2c but contains ZERO flip-flop logic
- Stub graduates silently and fails at runtime/test

Validation checklist:
- [ ] Spec has comb_nodes section?
- [ ] Every state-updating register has a comb_node?
- [ ] All comb_nodes use ONLY gate primitives?
- [ ] Wiring between logic blocks explicit?

If spec fails validation, STOP and return BLOCKED with specific missing items.
Reference: .hft_staging/INDICATOR_ARCHITECTURE_TEMPLATE.md (full worked example)

Do NOT proceed with code generation on incomplete specs.
```

**Rationale:** This forces the netlist-builder to validate architectural completeness before proceeding, catching incomplete specs before code generation starts (fail fast, don't generate stubs).

---

## Update 3: agt.md

**File:** `.claude/agents/AGNT/agt.md`

**Add new subsection to "Step 3a: Classify Complexity" (around line 50-60):**

Insert before the complexity-classification dispatch:

```markdown
### Architectural Validation Gate (Pre-Dispatch)

For any task involving code generation (emitter-first builds), AGT must verify that the specification is complete before dispatch:

**Complete specification includes:**
- Register state (dff_nodes, tables, history_ring)
- Input interface (cross_module_inputs)
- Output interface (seam_nodes)
- **Combinational logic (comb_nodes with explicit gate primitives)** ← CRITICAL
- **Wiring (signal flow)** ← CRITICAL

**If incomplete:**
- Log: "Spec incomplete — missing [comb_nodes|wiring]"
- Classify as: COMPLEX
- Return to user with: "Architectural specification incomplete. Required before code generation: ..."
- Reference: .hft_staging/INDICATOR_ARCHITECTURE_TEMPLATE.md

**If complete:**
- Proceed to complexity-classification
```

**Rationale:** This inserts an architectural validation gate into the AGT dispatch pipeline, preventing incomplete specs from reaching code-generation agents.

---

## Update 4: EVA.md

**File:** `.claude/agents/AGNT/EVA.md`

**Add validation checkpoint in the "Step 0: Codebase Grounding" section:**

After codebase-grounding, add:

```markdown
### Step 0b: Architectural Validation (for code-generation tasks)

If the task involves emitter-first builds or netlist generation:
- Verify that the spec includes comb_nodes (gate-level logic definitions)
- Verify that wiring specifications are explicit
- If either is missing, return to AGT with:
  ```
  BLOCKED — Architectural specification incomplete
  Missing: [comb_nodes | wiring]
  Spec is register-only; code generation would produce stubs (zero flip-flop logic).
  Required: Add [missing] to YAML spec before proceeding.
  Reference: .hft_staging/INDICATOR_ARCHITECTURE_TEMPLATE.md
  ```
```

**Rationale:** This adds a fail-fast check in EVA to catch incomplete specs immediately after grounding, before any code is written.

---

## Update 5: gate.sh (Already in .hft_staging/)

**File:** `.hft_staging/gate.sh`

**Status:** ✅ Already updated with stage 2d (logic content validation)

Stage 2d now checks:
```bash
cell_count=$(grep -o "cell_[a-z_]*(" ${GEN} | wc -l)
if [ "$cell_count" -eq 0 ]; then
    echo "FAIL: no structural cell calls found"
    exit 3
fi
```

**No additional action needed.**

---

## Deployment Instructions

These updates must be applied to the AGNT source repo (not this project's copy). Follow the standard re-deployment process:

1. Update AGNT files in development repo:
   - `.claude/agents/AGNT/skills/complexity-classification.md`
   - `.claude/agents/AGNT/netlist-builder.md`
   - `.claude/agents/AGNT/agt.md`
   - `.claude/agents/AGNT/EVA.md`

2. Re-deploy AGNT to this project:
   ```bash
   .claude/agents/AGNT/agnt-deploy.sh
   ```

3. Verify deployment:
   ```bash
   # Should show updated timestamps + new validation logic
   head -20 .claude/agents/AGNT/netlist-builder.md
   ```

---

## Testing the Updates

Once deployed, verify the new validations work:

**Test 1: Incomplete spec is rejected at netlist-builder stage**
```
@netlist-builder
Build the test-stub indicator (incomplete spec with no comb_nodes)
```
Expected: BLOCKED with "Architectural specification incomplete — missing comb_nodes"

**Test 2: Incomplete spec is classified as Complex**
```
@AGT
Task: Build an indicator with registers only (no gate-level logic)
```
Expected: Classified as Complex, returned to Planner with "Spec incomplete — missing comb_nodes"

**Test 3: Gate 2d catches stubs**
```bash
.hft_staging/gate.sh .hft_staging/candle
```
Expected: FAIL at stage 2d with "no structural cell calls found in candle_gen.h"

---

## Summary

| Component | Update | Purpose | Status |
|-----------|--------|---------|--------|
| complexity-classification | Add trigger for incomplete specs | Flag code-gen without architecture as Complex | Documented |
| netlist-builder | Add pre-build validation | Reject specs without comb_nodes + wiring | Documented |
| agt.md | Add architectural gate | Validate specs before dispatch | Documented |
| EVA.md | Add validation checkpoint | Fail fast on incomplete specs | Documented |
| gate.sh | Stage 2d (logic content) | Catch stubs at gate time | ✅ Implemented |

**All AGNT updates require re-deployment to this project via development repo.**
