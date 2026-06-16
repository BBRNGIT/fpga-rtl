# Enforcement: How C Specification Language Discipline is Automated

## Problem we're solving

Previous dev cycles: the same guidance was explained repeatedly because there was no
**automated enforcement**. Each cell required manual review to check:
- "Did they invent structure?"
- "Is this really what the Verilog says?"
- "Did they use verilog.h or hand-roll something?"

Result: slow, repetitive, failure-prone.

**Solution:** Three gates that run on every cell, before human review. If a cell fails,
the message IS the rule. Developers don't ask; they fix.

---

## Three gates (all automated)

### Gate 1: Compilation (`build.py` — status quo)

**What it does:**
```bash
cc -c clib/unisims/<CELL>.c -o /dev/null
```

**What it enforces:**
- C syntax is valid
- All `verilog.h` macros are defined
- No typos in construct names

**Failure message:** `error: undefined symbol 'wire_with_typo'` — dev fixes the symbol or adds it to verilog.h.

**Status:** ✓ Implemented in `build.py`.

---

### Gate 2: Specification Linting (`lint_spec.py` — to build)

**What it does:**
Parse the C file and check that constructs are used correctly per §2 (HANDOFF.md).

**Checks (phase 1):**

1. **No native C operators on `net_t`**
   - FORBIDDEN: `int x = A.v + B.v;` (using `.v` field directly)
   - FORBIDDEN: `net_t C = {A.v & B.v};` (using & on logic_t values)
   - ALLOWED: `assign(strong1, weak0) C = ...;` (using assign macro)
   - Linter: `grep -E 'net_t.*[\+\-\*/%].*net_t|\.v.*[\&\|\^]' clib/unisims/<CELL>.c`

2. **Vector declarations use `wire_bits()` or `wire [hi:lo]` notation preserved as comment**
   - FORBIDDEN: `net_t X[8];` (no semantic meaning attached)
   - ALLOWED: `wire_bits(X, 7, 0);` expands to `net_t X[8];` (semantic intent preserved)
   - ALLOWED: `// wire [7:0] X; net_t X[8];` (comment shows original notation)
   - Linter: check all `wire` declarations have a `wire_bits()` call or source comment

3. **Vector ranges use `range_assign()`, not raw Verilog `[3:0]` syntax**
   - FORBIDDEN: `assign Y = X[3:0];` (not valid C)
   - ALLOWED: `range_assign(Y, X, 3, 0);` (expands to comment; semantics preserved)
   - Linter: grep for `assign.*\[[0-9]+:[0-9]+\]` and flag as error

4. **Port directions are consistent**
   - FORBIDDEN: `output net_t *X;` followed by `X->v = ...;` (output driving itself is fine, but reading is suspicious)
   - ALLOWED: `input const net_t *X;` (read-only, guaranteed by `const`)
   - ALLOWED: `output net_t *Y;` (write allowed)
   - Linter: check that `input` ports are never assigned to in the module body

5. **Every `assign` has a drive strength**
   - FORBIDDEN: `assign Y = X;` (no drive strength)
   - ALLOWED: `assign(strong1, weak0) Y = X;` (explicit strength)
   - Linter: grep for `assign` not followed by `(strength)` and flag

6. **Parameters are declared and used**
   - FORBIDDEN: `parameter WIDTH = 8;` (declared but never used)
   - ALLOWED: `parameter WIDTH = 8;` followed by `wire_bits(data, WIDTH-1, 0);`
   - Linter: track parameter names and their uses

7. **No invented signals**
   - FORBIDDEN: `net_t temp;` (not in the original `.v`)
   - ALLOWED: All signals match the `.v` names exactly
   - Linter: extract signal names from C, compare to `.v`; flag extra names

**Failure messages are RULES:**
```
lint_spec.py: clib/unisims/FDRE.c
  Line 45: error: output port 'Q' is assigned in two places (no tri-state declaration)
           Add tri-state notation or verify the .v does this.
  Line 52: error: vector assignment 'X[7:4]' uses raw Verilog syntax
           Use: range_assign(Y, X, 7, 4);
  Line 78: error: signal 'internal_temp' not found in source .v
           Invented signals are forbidden. Remove or justify in .v.
```

**Status:** To be written.

---

### Gate 3: Architecture Correctness (`arch_check.py` — to build)

**What it does:**
Verify that the C code accurately describes the original `.v` at the architectural level.

**Approach:**
1. Parse the `.v` file (extract: ports, parameters, signals, assignments, always blocks)
2. Parse the corresponding `.c` file (extract: ports, parameters, signals, assignments, verilog.h usage)
3. Cross-check: does the C describe what the `.v` states?

**Checks (phase 1):**

1. **Port list matches**
   - C ports must be identical to `.v` ports (name, direction, position)
   - Linter output: `Port mismatch in GND: .v has [P, output], .c has [P, GND]. Check port order.`

2. **Parameters match**
   - C parameters must have same names, defaults, and types as `.v`
   - Linter output: `Parameter mismatch: .v has WIDTH=8, .c has WIDTH=16.`

3. **Description + Revisions are preserved**
   - "Description :" line from `.v` must appear in `.c` YAML
   - All "Revision:" lines from `.v` must appear in `.c` comments (with "(from <CELL>.v)" marker)
   - Linter output: `Missing description for glbl.c. Copy from glbl.v line 10.`

4. **No invented structure**
   - C signal count ≈ `.v` signal count (allow +1 for padding, but flag large diffs)
   - Linter output: `Signal count: .v has 12, .c has 45. 33 invented signals. List them.`

5. **Behavioral fidelity (spot-check)**
   - If `.v` has `always @(posedge clk)`, the `.c` must use `always(posedge clk)` macro
   - If `.v` has `assign Y = ...;`, the `.c` must have `assign(...) Y = ...;`
   - Linter output: `Behavioral mismatch: .v line 50 has "always @(posedge clk)", .c does not.`

**Failure messages are CORRECTABLE:**
```
arch_check.py: clib/unisims/FDRE.c vs unisim_src/verilog/src/unisims/FDRE.v

✓ Ports match: input D, C, R, E; output Q
✓ Parameters match: INIT=1'b0, IS_C_INVERTED=1'b0, IS_D_INVERTED=1'b0, IS_R_INVERTED=1'b0
✓ Description preserved: "D flip-flop with reset and clock enable"
✗ Revision missing: "03/23/94 - Initial release." Add to .c revision block.
✗ Signal count: .v has 8 signals, .c has 12 (4 invented). List them: _net_1, _net_2, ...
✗ Behavioral: .v uses 'always @(posedge C)', .c uses 'always_posedge_clk_macro'. Names differ?
```

**Status:** To be written.

---

## Build pipeline integration

### Current (status quo):
```bash
$ python3 build.py

[Transcribe all 249 cells]
✓ 249 -> clib/unisims/*.c

[Compile all 249]
✓ 247 pass
✗ 2 fail (GND needs DELAY macro, VCC needs _1b1 literal)
→ Fix verilog.h, rerun
```

### New (after gates 2 & 3):
```bash
$ python3 build.py

[Transcribe all 249 cells]
✓ 249 -> clib/unisims/*.c

[Gate 1: Compile]
✓ 247 pass
✗ 2 fail → Fix verilog.h

[Gate 2: Lint spec]
✓ 243 pass
✗ 4 fail:
  - FDRE.c: line 45, port Q driven twice without tri-state
  - CARRY8.c: line 78, vector assignment uses [7:4] syntax
  - DSP48E2.c: 23 invented signals detected
  - BRAM36E2.c: parameter WIDTH declared but never used
→ Fix the cells (no verilog.h changes needed; discipline rules broken)

[Gate 3: Architecture]
✓ 240 pass
✗ 3 fail:
  - GND.c: revision "02/11/15 - Initial release" missing
  - VCC.c: parameter P_NAME not in .v, invented
  - PULLUP.c: signal count: .v has 3, .c has 7 (4 extra)
→ Fix the cells (ensures accuracy vs `.v`)

[Summary]
✓ All 249 cells pass all gates
✓ Ready for Phase 2 (assembly/build)
```

---

## How this prevents re-explanation

1. **Discipline is code, not conversation.**
   A dev sees `lint_spec.py` output and KNOWS the rule. They don't ask "why?"

2. **Failure is unambiguous.**
   `error: vector assignment uses raw Verilog [7:4] syntax. Use: range_assign(Y, X, 7, 4);`
   Not: "That looks wrong; can you fix it?"

3. **Review is downstream.**
   Gates 1–3 catch 80% of issues. Human review focuses on what the gates can't check
   (e.g., "is this cell's .v description correct in the first place?").

4. **New devs onboard via **rules**, not re-explaining.**
   They read §2 (HANDOFF.md), see a linting failure, understand the rule,
   and fix it. No back-and-forth.

---

## Implementation priority

**Phase 1 (this week):**
- ✓ Update HANDOFF.md (§2, C spec language definition)
- Gate 1: enhance build.py to run lint_spec.py and arch_check.py
- Gate 2: write lint_spec.py (checks 1–7)
- Gate 3: write arch_check.py (checks 1–5)

**Phase 2 (next):**
- Transcribe cells 2–249, growing verilog.h as needed
- All cells pass gates 1–3
- Build system is locked in

**Phase 3 (later):**
- gate_replica.py or successor validates that builds (NAND decomposition phase)
- Realization pipelines use the locked catalog
