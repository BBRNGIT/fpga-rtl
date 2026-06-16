## Cell Transcription Submission

**Cell:** [CELL_NAME]  
**Tier:** [1-9]  
**Phase:** [Phase number, e.g., Phase 1]

### Description
Transcribes [CELL_NAME].v → [CELL_NAME].c using verilog.h vocabulary and components.h types.

Faithfully copies Verilog spec (no interpretation, no decomposition).

### Checklist

- [ ] **Compilation:** Compiles with `cc -c v4/clib/unisims/[CELL_NAME].c -o /tmp/[CELL_NAME].o -I v4`
- [ ] **Type Safety:** No `net_t`, no `_t` suffixes, all types from verilog.h/components.h
- [ ] **Includes:** Includes `#include "../../lib/verilog.h"` header
- [ ] **Verilog Fidelity:**
  - [ ] All parameters present (`parameter X = ...`)
  - [ ] All ports declared (as `net *` or `var`)
  - [ ] All assignments present (`assign`)
  - [ ] All initial blocks present
  - [ ] All delays preserved (`DELAY(n)`)
  - [ ] All gate instantiations preserved
  - [ ] All tri-state declarations preserved (tri, tri1, tri0)
- [ ] **No Invented Signals:** Only signals from .v present
- [ ] **Pre-commit Hook:** Passes (BUILD.sh validates)
- [ ] **Local Testing:** Ran `v4/BUILD.sh` and confirmed success

### Build Status

**Local Validation:**
```
✓ BUILD.sh passed
✓ [CELL_NAME].c compiles
✓ VCC test passes
✓ All cells compile
```

**CI Status:**
- Waiting for automated checks...

### Files Changed

- `v4/clib/unisims/[CELL_NAME].c` — Transcribed cell

### Source Reference

- **Original:** `/unisim_src/verilog/src/unisims/[CELL_NAME].v`
- **Lines:** [number] ports, [number] parameters, [number] assign statements

### Notes

[Any additional context, assumptions, or known gaps]

---

**By submitting this PR, I confirm:**
- ✓ This is a faithful copy of the Verilog spec
- ✓ No hand-written hardware components (used verilog.h + components.h)
- ✓ All changes are in v4/ (no modifications to v3, archive, or other areas)
- ✓ Commit message follows convention: `feat: Add [CELL_NAME] transcription (Tier X)`

