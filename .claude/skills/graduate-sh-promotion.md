---
name: Graduate.sh Promotion
description: Promote validated staging components to immutable .hft/ vault
type: workflow
source: FOUNDER_VISION.md §1, CLAUDE.md
---

# Graduate.sh Promotion

**Core Rule:** Only promote a component to `.hft/` (the immutable vault) after `gate.sh` PASSES. Graduation is write-once; updates require new versioned paths.

## Prerequisites for Graduation

Before running `graduate.sh`:

1. ✅ **Component passes `gate.sh`**
   ```sh
   .hft_staging/gate.sh .hft_staging/<module>
   # Result: PASS
   ```

2. ✅ **All work is committed**
   - No uncommitted changes in `.hft_staging/<module>/`
   - Netlist `.net.json` is committed
   - Generated `*_gen.h` is committed

3. ✅ **Working tree is clean**
   ```sh
   git status  # Should show clean
   ```

## The Graduation Process

```sh
.hft_staging/graduate.sh <module>
```

### What graduate.sh Does

1. **Validates the component**
   - Runs `gate.sh` again (full three-stage validation)
   - If any stage fails, graduation aborts

2. **Cleans the build**
   - Runs `make clean` to remove artifacts
   - Ensures only committed sources are promoted

3. **Builds from committed HEAD**
   - Clean-room rebuild to prove determinism

4. **Copies to vault**
   - Byte-identical copy from `.hft_staging/<module>/` → `.hft/<module>/`
   - Preserves all metadata (timestamps, etc.)

5. **Commits to vault**
   - Creates a new commit in `.hft/`
   - Immutability guards are applied (pre-commit hook blocks edits)

## Example Graduation

```sh
# 1. Ensure all changes are committed
cd .hft_staging/adapter
git add adapter.net.json adapter_gen.h
git commit -m "feat: adapter — price feed deserialization"

# 2. Run gate.sh to validate
.hft_staging/gate.sh .hft_staging/adapter
# Output: ==> [gate] PASS: .hft_staging/adapter

# 3. Graduate to vault
.hft_staging/graduate.sh adapter
# Output:
# [graduate] validating adapter...
# ==> [gate] 1/3 validate netlist
#     Single-writer check OK
#     ...
# ==> [gate] PASS: .hft_staging/adapter
# [graduate] copying adapter → .hft/adapter
# [graduate] committing to vault
# [graduate] DONE: adapter graduated
```

## After Graduation

### Vault is Immutable

The component now lives in `.hft/adapter/` and is **byte-identical and write-once**.

- ❌ **Cannot edit** — Pre-commit hook blocks modifications
- ❌ **Cannot delete** — Pre-commit hook blocks deletions
- ✅ **Can be read** — Other components may depend on its netlist/gennet

### Reading from Vault

Components in staging may depend on published interfaces in vault:

```makefile
# Inside .hft_staging/adapter/Makefile
wire_gen.h: ../.hft/wire/wire.net.json
	python3 ../.hft/wire/gennet.py ../.hft/wire/wire.net.json > wire_gen.h
```

The adapter reads the committed wire netlist and regenerates its seam header at build time.

## Updating a Graduated Component

**Never edit `.hft/<module>/` in place.**

Instead, create a new versioned path:

```sh
# Original (graduated):
.hft/adapter/

# New version (start in staging):
.hft_staging/adapter_v2/
```

Process:
1. Copy the component directory to `.hft_staging/adapter_v2/`
2. Make your changes in staging
3. Run `gate.sh` and `graduate.sh adapter_v2`
4. New version goes to `.hft/adapter_v2/`
5. Old `.hft/adapter/` remains unchanged (archive)

## Re-graduation (Rare)

If you absolutely must re-graduate an existing component (e.g., after fixing a critical bug in an already-graduated module):

```sh
HFT_ALLOW_REGRADUATE=1 .hft_staging/graduate.sh adapter
```

This bypasses the immutability guard **for this one operation only**. Use only with founder approval.

## Exit Codes

- **Exit 0:** PASS — component graduated successfully
- **Exit 1:** Gate validation failed (component not promoted)
- **Exit 2:** Usage error
- **Exit 3:** Copy or commit failed

## Graduation Checklist

Before running `graduate.sh`:

| Item | Check | Command |
|------|-------|---------|
| Netlist valid | ✅ | `cd .hft_staging/<module> && make validate` |
| Generated | ✅ | `cd .hft_staging/<module> && make gen` |
| Thin test passes | ✅ | `cd .hft_staging/<module> && make test` |
| Gate passes | ✅ | `.hft_staging/gate.sh .hft_staging/<module>` |
| All committed | ✅ | `git status` (clean) |
| No stale artifacts | ✅ | `cd .hft_staging/<module> && make clean` |

## What Graduation Guarantees

A graduated component guarantees:

- ✅ Source is committed (no dirty working-tree artifacts)
- ✅ Netlist validates (single-writer, no-overlap, no-floating)
- ✅ Builds from committed HEAD (clean-room, dependency-aware)
- ✅ No native arithmetic in device tick
- ✅ No hand-written device logic
- ✅ Contains structural cell logic (not a stub)
- ✅ Byte-identical to committed HEAD (no build drift)
- ✅ Immutable — cannot be edited in place

## Failed Graduation

If graduation fails:

1. **Check gate output** — Which stage failed?
2. **Fix in staging** — Make changes in `.hft_staging/<module>/`
3. **Validate locally** — Run `make validate`, `make test`
4. **Run gate again** — `.hft_staging/gate.sh .hft_staging/<module>`
5. **Commit** — `git add` and `git commit`
6. **Retry graduation** — `.hft_staging/graduate.sh <module>`

## Vault Structure

After graduation, the vault looks like:

```
.hft/
  adapter/              # Graduated component (immutable)
    adapter.net.json
    adapter_gen.h
    adapter.c
    adapter.h
    ...
  wire/                 # Published interface
    wire.net.json
    gennet.py
  candle/
  footprint/
  ... (15 total modules)
```

## References

- FOUNDER_VISION.md §1 — Build Model
- CLAUDE.md — Commit & Graduate, Graduation Guarantees
- `.hft_staging/graduate.sh` — Full implementation (80 lines)
- `.hft/README.md` — Vault immutability laws
