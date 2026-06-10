---
name: Gate.sh Validation
description: Three-stage acceptance gate — netlist, build+checks, clean-room rebuild
type: workflow
source: FOUNDER_VISION.md §1, CLAUDE.md
---

# Gate.sh Validation

**Core Rule:** A component is only validated when `gate.sh` passes all three stages. This is the project's acceptance gate.

## The Three Stages of gate.sh

### Stage 1: Netlist Validation
```sh
.hft_staging/gate.sh .hft_staging/<module>
# Stage 1/3: validate netlist
```

**What it does:**
- Runs `python3 validate.py <module>.net.json`
- Checks for **single-writer:** Each register written by exactly one node
- Checks for **no-overlap:** No read/write conflicts on registers
- Checks for **no-floating:** All nodes in the netlist are wired (no orphans)

**Failure modes:**
- `[FAIL] register REG written by multiple nodes` → Fix netlist; one writer per register
- `[FAIL] node NODE_NAME has no outputs wired` → Remove unused nodes or add wiring

### Stage 2: Build + Test + Gate Checks
```sh
# Stage 2/3: build + thin test (working tree)
```

**Substage 2a: Build and run thin test**
- Runs `make` inside the component directory
- Compiles device C with `-Werror` (all warnings are errors)
- Runs thin test: power-on + display only
- Must succeed in under 1 second

**Substage 2b: Gate-level arithmetic check**
- AWK scan over `*_gen.h`
- **Forbidden:** Native `+`, `-`, `*` operators OUTSIDE `cell_*()` calls in the tick function
- **Allowed:** Shifts `>>`, `<<`; loop counters `i = i + 1ULL`; cell arguments
- **Failure mode:** `[FAIL] native arithmetic operator in generated tick` → Regenerate netlist; use `cell_addsub` for arithmetic

**Substage 2c: Build-sequence check**
- Grep scan of hand-written `.c` and `.h` files (NOT `cells.h`, NOT `*_gen.h`)
- **Forbidden:** `cell_*()` function calls; `*_tick()` function definitions
- **Allowed:** Comments referencing cells (won't match); display/probe code
- **Failure mode:** `[FAIL] hand-written device logic` → Move logic to netlist; regenerate with gennet

**Substage 2d: Logic-content check**
- Counts `cell_*()` calls in `*_gen.h`
- **Requirement:** At least one structural cell (not zero)
- **Failure mode:** `[FAIL] no structural cell calls found` → Netlist is a stub (empty COMPUTE phase); add comb_nodes to spec

### Stage 3: Clean-Room Build
```sh
# Stage 3/3: clean-room build from committed HEAD
```

**What it does:**
- Archives the entire `.hft_staging/` prefix from committed HEAD
- Builds the component in a fresh temp directory
- Proves the build is reproducible from git, not from dirty working-tree artifacts

**Skipped if:**
- Component or its sibling dependencies have uncommitted changes
- Message: `SKIPPED — staging tree has uncommitted changes`

**Failure modes:**
- Build fails in clean room but works in working tree → You have stale artifacts; run `make clean`
- Different output than working tree → Build drift; may indicate non-deterministic generation

## How to Run gate.sh

```sh
# Validate a single component
.hft_staging/gate.sh .hft_staging/adapter

# Output:
# ==> [gate] 1/3 validate netlist
#     Single-writer check OK
#     No-overlap check OK
#     No-floating check OK
# ==> [gate] 2/3 build + thin test (working tree)
#     build+test OK
# ==> [gate] 2b/3 gate-level arithmetic
#     adapter_gen.h tick: no native +/-/* — OK
# ==> [gate] 2c/3 build-sequence
#     no hand-written device logic — OK
# ==> [gate] 2d/3 flip-flop logic content
#     adapter_gen.h: 208 cell calls — OK
# ==> [gate] 3/3 clean-room build from committed HEAD
#     clean-room build OK (/tmp/tmpXXXX/adapter)
# ==> [gate] PASS: .hft_staging/adapter
```

## Exit Codes

- **Exit 0:** PASS — component validated
- **Exit 2:** Usage error (no directory arg)
- **Exit 3:** FAIL — specific stage failed (netlist, build, arithmetic, build-sequence, logic-content)

## Pre-gate Checklist

Before running `gate.sh`:

1. ✅ Run `make validate` in isolation
   ```sh
   cd .hft_staging/adapter && make validate
   ```

2. ✅ Regenerate `*_gen.h` from netlist
   ```sh
   cd .hft_staging/adapter && make gen
   ```

3. ✅ Run `make test` and verify it passes
   ```sh
   cd .hft_staging/adapter && make test
   ```

4. ✅ Commit all changes (no uncommitted files in staging tree)
   ```sh
   git add .hft_staging/adapter/*.net.json .hft_staging/adapter/*_gen.h
   git commit -m "..."
   ```

5. ✅ Run `gate.sh`
   ```sh
   .hft_staging/gate.sh .hft_staging/adapter
   ```

## Common Failures and Fixes

| Failure | Stage | Root Cause | Fix |
|---------|-------|-----------|-----|
| Single-writer violation | 1 | Two nodes write same register | Review netlist; assign each register to one node |
| No-floating nodes | 1 | Orphan nodes in netlist | Remove unused nodes or wire them to COMPUTE phase |
| Build fails | 2a | Compile error in device C | Check generated tick syntax; regenerate |
| Native arithmetic | 2b | `+`/`-`/`*` outside cell calls | Use `cell_addsub`, `cell_mul`, `cell_sar` |
| Hand-written device logic | 2c | `cell_*()` or `*_tick` in `.c`/`.h` | Remove; add to netlist; regenerate |
| No cell calls | 2d | COMPUTE phase is empty | Add comb_nodes to spec; regenerate |
| Clean-room fails | 3 | Stale artifacts from working tree | Run `make clean`; commit HEAD; retry |

## After gate.sh PASS

Once `gate.sh` passes:

```sh
.hft_staging/graduate.sh adapter
```

This copies the validated component to `.hft/adapter/` and locks it as immutable.

## References

- FOUNDER_VISION.md §1 — Build Model
- CLAUDE.md — Architecture Enforcement Tools, Common Commands
- `.hft_staging/gate.sh` — Full implementation (70 lines)
