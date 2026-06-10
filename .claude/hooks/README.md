# Pre-Commit Hooks

This directory contains documentation and quick references for the fpga-rtl project's git pre-commit hooks.

## What's Active

**`.git/hooks/pre-commit`** — Main enforcement hook

Located in the git hooks directory (not in this folder), this hook runs automatically before every commit to enforce project policies.

## Files in This Directory

| File | Purpose |
|------|---------|
| **HOOKS.md** | Complete documentation of all hook checks, failure modes, and solutions |
| **QUICK_REFERENCE.md** | One-page cheat sheet for common issues |
| **README.md** | This file |

## Quick Start

### The Hook Checks

1. **AI Attribution** — Blocks `Co-Authored-By: Claude` in commit messages
2. **Vault Immutability** — Prevents edits to `.hft/` directory
3. **Thin Test Size** — Enforces `test_*.c` files ≤45 lines
4. **Generated Compliance** — Warns if `*_gen.h` doesn't match gennet output

### If a Commit Fails

```bash
# Read the error message carefully
# Find your issue in QUICK_REFERENCE.md
# Follow the fix steps
# Try commit again
```

## Enable/Disable Hooks

```bash
# Hook is enabled by default (executable)
ls -la .git/hooks/pre-commit

# To temporarily disable (not recommended):
chmod -x .git/hooks/pre-commit

# To re-enable:
chmod +x .git/hooks/pre-commit
```

## For Developers

When working on this project:

1. **Keep commits clean** — No AI attribution markers
2. **Test before committing** — Run `make test` locally
3. **Keep tests thin** — ≤45 lines (no orchestration)
4. **Respect vault** — Create `_v2/` paths for updates
5. **Regenerate when needed** — Run gennet before committing

## References

- Full hook details: **HOOKS.md**
- Common fixes: **QUICK_REFERENCE.md**
- Policy source: **FOUNDER_VISION.md §11** (no AI attribution), **§8** (vault), **§9** (tests)
- Skills guide: **.claude/skills/no-ai-attribution.md**
