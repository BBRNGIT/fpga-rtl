---
name: Immutability Enforcement
description: Graduated components in .hft/ are write-once — no edits, only new versioned paths
type: enforcement
source: FOUNDER_VISION.md §1 & §8, CLAUDE.md
---

# Immutability Enforcement

**Core Rule:** Once a component is graduated to `.hft/`, it is **byte-identical and immutable**. Files in the vault cannot be edited or deleted in place. Updates require new versioned paths (e.g., `adapter_v2/`).

## Why Immutability

1. **Archive:** Graduated code is a frozen snapshot; other components may depend on it
2. **Reproducibility:** If a component worked at graduation time, it must work identically when rebuilt
3. **Audit trail:** Code history is preserved; no silent modifications
4. **Clean re-graduation:** New versions are tested completely (not patches to old code)

## The Vault Structure

```
.hft/                           # Immutable vault
  adapter/                      # v1 (graduated, locked)
    adapter.net.json
    adapter_gen.h
    gennet.py
    cells.h
    ...
  adapter_v2/                   # v2 (new version, started in staging)
    adapter_v2.net.json
    adapter_v2_gen.h
    ...
  candle/                       # Original version
  candle_v2/                    # Bugfix version
  ...
```

**Key:** Each version is a separate directory. The original is never edited.

## Workflow for Updates

### Scenario: You need to update an existing graduated component

**WRONG (editing in place):**
```sh
cd .hft/adapter
# ❌ Edit adapter.net.json
# ❌ Edit gennet.py
# ❌ Try to git add and commit

# Result: Pre-commit hook blocks the edit
# [FAIL] .hft/ files are write-once; create a new versioned path
```

**RIGHT (new versioned path):**
```sh
# 1. Copy graduated component to staging with new version
cp -r .hft/adapter .hft_staging/adapter_v2

# 2. Make edits in staging
cd .hft_staging/adapter_v2
# Edit adapter_v2.net.json
# Edit gennet.py
# Edit other files as needed

# 3. Build and validate in staging
make validate
make gen
make test
.hft_staging/gate.sh .hft_staging/adapter_v2

# 4. Commit in staging
git add adapter_v2.*
git commit -m "feat: adapter_v2 — improved deserialization"

# 5. Graduate to vault
.hft_staging/graduate.sh adapter_v2

# Result: adapter_v2/ is now in .hft/ (immutable)
# Original .hft/adapter/ is unchanged
```

## Pre-commit Hook (Vault Protection)

The `.hft/` directory has a pre-commit hook that:

1. **Blocks modifications** — Cannot edit any tracked file
2. **Blocks deletions** — Cannot delete any tracked file
3. **Allows new files** — New versions can be added

**Behavior:**

```sh
# Attempt to edit a vault file
cd .hft/adapter
vim adapter.net.json
git add adapter.net.json
git commit -m "fix: update adapter"

# Output:
# [FAIL] .hft/.githooks/pre-commit
# Immutable vault: cannot modify or delete already-tracked files in .hft/
# Create a new versioned path instead: adapter_v2/, adapter_v3/, etc.
# To override (rare): HFT_ALLOW_REGRADUATE=1 git commit ...
```

## Emergency Re-graduation (HFT_ALLOW_REGRADUATE)

**Only use with founder approval.** In rare cases (critical security bug, post-graduation discovery of broken logic):

```sh
# Make changes in staging (e.g., adapter/)
cd .hft_staging/adapter
# Fix the bug
git add adapter.net.json adapter_gen.h
git commit -m "fix: critical bug in adapter"

# Validate
.hft_staging/gate.sh .hft_staging/adapter

# Re-graduate (override immutability)
HFT_ALLOW_REGRADUATE=1 .hft_staging/graduate.sh adapter

# Result: .hft/adapter/ is re-graduated (overwritten)
# Use only if absolutely necessary; prefer new versions otherwise
```

## Version Naming Convention

**Standard format:** `<module>_v<number>`

Examples:
- `adapter` → `adapter_v2` → `adapter_v3`
- `candle` → `candle_v2`
- `fifo_rx` → `fifo_rx_v2`

**Rationale:**
- Clear version history
- Easy to identify original vs. updates
- Prevents name collisions

## Checking for Vault Compliance

Before committing:

```sh
# Check that you're not editing vault files
git status | grep ".hft/"

# Should show nothing (or only new files under .hft/)
# If it shows modifications to .hft/*, you're violating immutability
```

## Updating Cross-Module Dependencies

When a graduated component has a dependency that updates:

```
Old: adapter (in .hft/) reads from wire (in .hft/)
New: wire updates to wire_v2 (new graduation)
```

**Question:** Does adapter need to update?

**Answer:** Only if the wire interface changed. If wire_v2's outputs match wire's, adapter can still read wire. If the interface changed, create adapter_v2 that reads wire_v2.

```sh
# Example: wire interface changed, adapter must update
cd .hft_staging
cp -r ../hft/adapter adapter_v2

# Edit Makefile to read wire_v2 instead of wire
sed -i 's/wire\/wire.net.json/wire_v2\/wire_v2.net.json/' adapter_v2/Makefile
sed -i 's/wire_gen.h/wire_v2_gen.h/' adapter_v2/Makefile

# Continue with test, gate, graduate
.hft_staging/gate.sh .hft_staging/adapter_v2
.hft_staging/graduate.sh adapter_v2
```

## Vault Directory Listing

View all graduated components and their versions:

```sh
ls -la .hft/
# adapter/        — v1
# adapter_v2/     — v2 (bugfix, updated interface)
# candle/         — v1
# candle_v2/      — v2 (new indicator variant)
# fifo_rx/        — v1
# ...
```

**Each directory is a frozen snapshot in time.**

## Graduation Guarantees (Why Immutability)

When a component is graduated:
- ✅ Source is committed
- ✅ Netlist validates
- ✅ Device logic is generated deterministically
- ✅ Clean-room build succeeds
- ✅ All tests pass

**Immutability ensures:** If you rebuild from .hft/adapter HEAD, you get identical behavior.

## Handling Deprecated Versions

Old versions are preserved for history and dependency tracing. You can:

1. **Keep old versions** — Documents evolution
2. **Reference in docs** — "adapter_v1 supported broker X; adapter_v2 dropped it"
3. **Archive old versions** — Move to a `.hft_archive/` if the vault grows too large (rare)

## Checking What Changed Between Versions

```sh
# Compare netlists
diff .hft/adapter/adapter.net.json .hft/adapter_v2/adapter_v2.net.json

# Compare generated code
diff .hft/adapter/adapter_gen.h .hft/adapter_v2/adapter_v2_gen.h

# Check commit history
git log --oneline .hft/adapter/
git log --oneline .hft/adapter_v2/
```

## Pre-graduation Checklist

Before graduating:

- [ ] All edits are in `.hft_staging/<module>/`
- [ ] No files in `.hft/` are modified (check git status)
- [ ] If updating, `<module>` has a `_vN` suffix (new version)
- [ ] Staging version is validated and committed
- [ ] `.hft_staging/graduate.sh <module>` runs successfully

## References

- FOUNDER_VISION.md §8 — Immutability of .hft
- CLAUDE.md — Immutability of .hft (Write-Once Vault)
- `.hft/README.md` — Vault immutability laws
- `.hft_staging/graduate.sh` — Implements immutability
