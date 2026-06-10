# Autonomous Indicator Build Workflow

**Status:** Ready for AGT dispatch  
**Spec Resolution:** §A quote-driven ✅ | §B dual OHLC ✅  
**Build Order:** candle → footprint ∥ TPO → fractal ∥ CBR  

---

## Validation Checkpoints (Four Skills)

These are applied at gates within the workflow. AGT calls them to validate outputs before proceeding.

### **Checkpoint 1: indicator-spec-reconciler** (Phase 1)
- **Purpose:** Validate MODULE.md design doc against SPEC_REGISTERS.md
- **Input:** `<module>.md`, spec section, founder decisions (§A, §B)
- **Logic:**
  - Extract IN/OUT registers from diagram
  - Cross-reference against SPEC (exact names, types)
  - Check for ghost reads (DOM_BUY_VOL, TRADE_BUY, is_buy) → CONFLICT
  - Validate single-writer/single-reader contract
  - For candle-dependent: verify candle is graduated + CANDLE_HIST offsets match
- **Output:** MATCH | CONFLICT <details> | BLOCKED <reason>
- **Escalate on:** CONFLICT or BLOCKED

### **Checkpoint 2: netlist-auditor** (Phase 3)
- **Purpose:** Audit emitted `<module>.net.json` for architectural poison
- **Input:** `<module>.net.json`, founder decisions, SPEC
- **Logic:**
  - Parse netlist nodes (JSON)
  - Detect ghost nodes (BUY_VOL, is_buy, etc.) → AUDIT-FAIL
  - Validate cell types (only cell_addsub, cell_mul, cell_mux, cell_gate, cell_eqmask, cell_dff, comparators)
  - Check complexity bounds (POC argmax unrolled? divide staged? imbalance branchless?)
  - For CBR: verify divide_stage + divide_valid registers present (staged pipeline)
  - For fractal: verify h2/l2/c0/c1 field offsets vs CANDLE_HIST layout
- **Output:** PASS | AUDIT-FAIL <details>
- **Escalate on:** AUDIT-FAIL

### **Checkpoint 3: indicator-e2e-validator** (Phase 5)
- **Purpose:** Run test data through ingress chain, verify indicator outputs are sane
- **Input:** Compiled indicator binary, test CSV (market data), reference oracle (bounds or prior implementation)
- **Logic:**
  - Load test data (BID/ASK/QTY/SEQ)
  - Run: adapter → wire → NIC → FIFO → DOM → indicator
  - Read output registers (POC, delta, VAH/VAL for footprint; time_at_price for TPO; etc.)
  - Compare against oracle:
    - Algebraic bounds (delta in [-total_qty, +total_qty])
    - Reference oracle (old hand-written footprint.c if available, or manual calculation)
    - Field presence (all expected registers populated, no stuck zeros)
  - Return divergence details if any
- **Output:** VERIFIED | DIVERGENCE <fields with expected vs actual>
- **Escalate on:** DIVERGENCE

### **Checkpoint 4: rtl-project-gate (extended)**
- **Purpose:** Interpret gate.sh output with structured findings
- **Input:** gate.sh execution (stages 1–5: validate, build, 2b, 2c, clean-room)
- **Logic:**
  - Parse stage-by-stage output
  - Stage 2b fail: identify line with native +/−/* in generated tick
  - Stage 2c fail: identify file with hand-written `*_tick` or `cell_*()`
  - Stage 5 fail: compute byte diff, explain what diverged (gennet drift? emitter version?)
  - Construct structured findings (not just PASS/FAIL)
- **Output:** PASS | FAIL <stage>, <explanation>, <remediation>
- **Escalate on:** FAIL

---

## AGT Dispatch Sequence

### **Phase 0: Pre-flight Check**
```
✓ Spec resolved (§A, §B in DECISIONS.md or committed to SPEC_REGISTERS.md)
✓ No uncommitted changes on main
✓ Four validation checkpoints ready
✓ netlist-builder subagent available
```

### **Phase 1: Build Candle (Prerequisite)**
```
git worktree add --track -b task/candle wt-candle origin/main

dispatch netlist-builder (candle) in wt-candle/
  Phase 1: extract CANDLE.md from SPEC_REGISTERS.md §6
  Checkpoint 1: indicator-spec-reconciler candle
  Phase 2–4: gen_candle_net.py → candle.net.json → gennet.py → candle_gen.h
  Checkpoint 2: netlist-auditor candle.net.json
  Phase 5: gate.sh (validate, build, 2b, 2c, clean-room)
  Checkpoint 4: rtl-project-gate output
  Phase 6: commit, graduate

git checkout main
git merge task/candle
git worktree remove wt-candle
git branch delete task/candle (optional)
```

### **Phase 2: Build Footprint ∥ TPO (Parallel)**
```
Parallel dispatch (two subagents concurrently):

FOR footprint:
  git worktree add --track -b task/footprint wt-footprint origin/main
  dispatch netlist-builder (footprint) in wt-footprint/
    Phase 1: FOOTPRINT.md from SPEC §7
    Checkpoint 1: indicator-spec-reconciler footprint
    Phase 2–5: emitter → netlist → gennet → gate
    Checkpoint 2: netlist-auditor
    Checkpoint 3: indicator-e2e-validator (feed test data)
    Checkpoint 4: rtl-project-gate
    Phase 6: commit

FOR TPO:
  git worktree add --track -b task/tpo wt-tpo origin/main
  dispatch netlist-builder (TPO) in wt-tpo/
    [same phases/checkpoints]

After both complete:
  git checkout main
  git merge task/footprint
  git merge task/tpo
  git worktree remove wt-footprint
  git worktree remove wt-tpo
```

### **Phase 3: Build Fractal ∥ CBR (Parallel, after candle + footprint)**
```
Parallel dispatch:

FOR fractal:
  git worktree add --track -b task/fractal wt-fractal origin/main
  dispatch netlist-builder (fractal) in wt-fractal/
    [same phases/checkpoints]

FOR CBR:
  git worktree add --track -b task/cbr wt-cbr origin/main
  dispatch netlist-builder (CBR) in wt-cbr/
    [same phases/checkpoints]

After both complete:
  git checkout main
  git merge task/fractal
  git merge task/cbr
  git worktree remove wt-fractal
  git worktree remove wt-cbr
```

---

## Escalation Rules

**Checkpoint 1 (spec-reconcile) fails:**
- Escalate to user: "MODULE.md mismatches SPEC. Details: X. Fix doc and retry."

**Checkpoint 2 (netlist-audit) fails:**
- Escalate: "Netlist contains poison (ghost node X, or complexity Y). Emitter violated spec. Retry with corrected emitter."

**Checkpoint 3 (e2e-validator) fails:**
- Escalate: "Output divergence: expected Z, got W. Reference oracle mismatch. Investigate emitter logic."

**Checkpoint 4 (gate) fails:**
- Escalate: "Gate stage N failed: X. Details: Y. Cannot graduate until gate passes."

**Any blocker (missing candle, spec conflict, gate fail):**
- AGT returns BLOCKED with escalation message
- User reviews, resolves, re-dispatches

---

## Worktree Cleanup

After each phase:
```
git worktree remove wt-<module>   # Reclaim disk (shared .git, not a copy)
git branch delete task/<module>   # Optional (or keep for history)
```

If worktree creation fails (disk full, permissions), AGT escalates before dispatch.

---

## Success Criteria

✅ All four modules built and graduated  
✅ All checkpoints pass (spec, netlist, e2e, gate)  
✅ No worktrees left in `.hft_staging/`  
✅ Commits carry user name only, no AI attribution  
✅ History branches (task/*) in git log  

---

## Next Step

AGT: Confirm pre-flight checks, then dispatch Phase 1 (candle).
