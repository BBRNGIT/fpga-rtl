---
name: Clean-Room Rebuild
description: Rebuild from committed HEAD in a temp directory to prove determinism — no dirty artifacts
type: validation
source: FOUNDER_VISION.md §1, CLAUDE.md
---

# Clean-Room Rebuild

**Core Rule:** A component's build must be reproducible from committed HEAD alone, with no stale artifacts from the working tree. The clean-room rebuild validates this by archiving HEAD into a temp directory, building there, and verifying the output byte-matches the working-tree build.

## Why Clean-Room Builds Matter

**Problem:** Hand-written artifacts (object files, generated code) can persist in the working tree and mask broken build logic.

```sh
# Working tree has these files:
.hft_staging/adapter/
  adapter_gen.h              ✅ Committed (correct)
  adapter_gen.o              ❌ Stale object file (from old version)
  adapter_test               ❌ Stale binary (from old version)

# Your working tree builds fine (uses stale files)
# But a clean rebuild from HEAD would fail (stale files not present)
```

**Solution:** `gate.sh` stage 3 rebuilds in a fresh temp directory with only committed files. If the clean build fails or differs from working-tree build, the component is not promoted.

## The Clean-Room Process

```sh
.hft_staging/gate.sh .hft_staging/adapter
# ...stages 1 and 2 pass...

# === STAGE 3: CLEAN-ROOM BUILD ===
# 1. Archive .hft_staging/ from HEAD to temp dir
TMP=$(mktemp -d)
git archive HEAD .hft_staging/ | tar -x -C $TMP --strip-components=1
# Result: $TMP/adapter/ with only committed files

# 2. Build in temp directory
cd $TMP/adapter
make

# 3. Verify output
# If build fails: FAIL (component not promoted)
# If build succeeds: PASS (clean-room build OK)
```

**Output:**
```
==> [gate] 3/3 clean-room build from committed HEAD
clean-room build OK (/tmp/tmpXXXX/adapter)
```

## What It Validates

1. **Build dependencies are committed** — Required source files are in git, not in .gitignore
2. **No hand-written artifacts** — No stale `.o` files or binaries influence the build
3. **Reproducibility** — Running the build commands on HEAD reproduces the same result
4. **Dependency resolution** — Cross-module dependencies (e.g., adapter reading wire's gennet.py) work from HEAD

## Pre-gate Cleanup

Before running `gate.sh`, clean up the working tree:

```sh
cd .hft_staging/adapter

# Remove all built artifacts
make clean

# Verify working tree is clean
git status
# Should show:
# - No modified files
# - No untracked files (except .gitignore'd)
```

## Common Clean-Room Failures

| Failure | Cause | Fix |
|---------|-------|-----|
| `make: No such file or directory` | Makefile not committed | `git add Makefile` |
| `python3: No such file or directory` | gen_*.py not committed | `git add gen_*_net.py` |
| `undefined reference to gennet` | gennet.py not committed | `git add gennet.py` |
| Build fails in clean room but works in working tree | Stale artifacts in working tree | `make clean` before gate |
| Different output in clean room | Build drift (non-deterministic generation) | Check gennet.py for non-determinism |

## Debugging Clean-Room Failures

If gate stage 3 fails or shows differences:

```sh
# 1. Extract the clean room directory from gate output
# Gate prints: clean-room build OK (/tmp/tmpXXXXX/adapter)

# 2. Inspect the temp directory
ls -la /tmp/tmpXXXXX/adapter/

# 3. Compare outputs
diff working_tree_output clean_room_output

# 4. If clean room is missing files:
cd .hft_staging/adapter
git ls-files  # Show all tracked files
# Make sure all required .py, .h, .c files are tracked

# 5. If clean room build fails:
cd /tmp/tmpXXXXX/adapter
make -v  # Show what make is doing
make test  # Try building manually
```

## Ensuring Reproducibility

### Commit All Build Inputs

Everything needed to build must be committed:

```sh
cd .hft_staging/adapter

# Required files (must be tracked):
git add gennet.py            # ✅ Generator
git add gen_adapter_net.py   # ✅ Emitter
git add adapter.net.json     # ✅ Netlist
git add adapter_gen.h        # ✅ Generated device C
git add adapter.c            # ✅ Host glue
git add adapter.h
git add buffer.c
git add display.c
git add test_adapter.c
git add cells.h
git add validate.py
git add Makefile
git add prep.py              # ✅ Data prep (if any)

# Files to gitignore (NOT committed):
# - *.o, *.a (object files)
# - adapter_test (binary)
# - *.bin (generated data)
# - *.csv (data files)
```

### Avoid Non-Deterministic Generation

`gennet.py` and `gen_*_net.py` must produce identical output every run:

```python
# BAD — non-deterministic (random, timestamp, dict iteration order)
import random
output = sorted(nodes, key=lambda x: random.random())  # ❌ Random order
print(f"// Generated {time.time()}")                    # ❌ Timestamp

# GOOD — deterministic (sorted, no randomness)
output = sorted(nodes, key=lambda x: x['name'])        # ✅ Sorted
print(f"// Generated from netlist")                     # ✅ Static message
```

## Clean-Room Rebuild in CI/CD

In a CI/CD pipeline, every build is a clean-room build (no artifacts from previous runs):

```sh
# CI environment starts fresh
git clone repo
cd fpga-rtl/.hft_staging/adapter
make clean       # Remove anything
make test        # Build from scratch (clean room)
.hft_staging/gate.sh .hft_staging/adapter
```

**Result:** If the component passes gate in CI, it's guaranteed to be reproducible.

## Checking for Uncommitted Files

Before gate.sh:

```sh
# List all uncommitted changes in staging tree
git diff HEAD .hft_staging/

# List all untracked files
git ls-files --others --exclude-standard .hft_staging/

# Both should be empty (except .gitignore'd files)
git status .hft_staging/
# Should show:
# On branch master
# nothing to commit, working tree clean (for staging tree)
```

## Pre-graduation Checklist

Before running `gate.sh`:

- [ ] All source files committed (`git add .hft_staging/<module>/*`)
- [ ] All generated files committed (`.net.json`, `*_gen.h`)
- [ ] Working tree is clean (`git status`)
- [ ] Run `make clean` to remove artifacts
- [ ] Run `gate.sh` (stages 1 and 2 pass)
- [ ] Clean-room build passes (stage 3)

## After Graduation

Once clean-room builds pass:

```sh
.hft_staging/graduate.sh adapter
# Copies from HEAD to .hft/adapter/
# Commits to vault with immutability
```

**The vault copy is guaranteed reproducible.**

## Dependency-Aware Clean Rooms

Some components read published interfaces:

```makefile
# In .hft_staging/adapter/Makefile
wire_gen.h: ../.hft/wire/wire.net.json
	python3 ../.hft/wire/gennet.py ../.hft/wire/wire.net.json > wire_gen.h
```

The clean-room includes the whole `.hft_staging/` tree:

```sh
# Archive includes both:
# - .hft_staging/adapter/ (component being gated)
# - .hft_staging/wire/    (sibling dependency)

# So adapter can read wire's netlist and regenerate wire_gen.h
```

**Result:** Cross-module dependencies work in clean room.

## References

- FOUNDER_VISION.md §1 — Build Model, Clean-room rebuild
- CLAUDE.md — Architecture Enforcement Tools
- `.hft_staging/gate.sh` — Stage 3 implementation (lines 152–167)
