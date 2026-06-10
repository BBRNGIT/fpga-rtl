# Hooks Quick Reference

## What the Hooks Check

| Check | Blocks | Error | Fix |
|-------|--------|-------|-----|
| **AI Attribution** | `Co-Authored-By: Claude` in commit message | `[FAIL]` | Remove AI markers; use user name |
| **Vault Immutability** | Modifications to `.hft/` files | `[FAIL]` | Create `_v2/` path instead |
| **Thin Test Size** | `test_*.c` files > 45 lines | `[FAIL]` | Remove testbench; keep only init + display |
| **Generated Compliance** | `*_gen.h` doesn't match gennet output | `[WARN]` | Regenerate: `python3 gennet.py *.net.json` |

## Most Common Issues

### ❌ Commit fails: "AI attribution detected"

```
Error: Co-Authored-By: Claude Haiku detected
```

**Fix:**
```bash
git commit --amend          # Edit message
# Remove "Co-Authored-By" line
git commit                  # Retry
```

### ❌ Commit fails: "Cannot modify .hft/"

```
Error: Modified file in .hft/adapter/adapter.net.json
```

**Fix:**
```bash
git reset HEAD .hft/adapter/*        # Unstage
cp -r .hft/adapter .hft_staging/adapter_v2
cd .hft_staging/adapter_v2
# Make changes, then graduate as v2
```

### ❌ Commit fails: "Test file too large"

```
Error: test_adapter.c is 87 lines (max 45)
```

**Fix:**
```bash
# Remove testbench logic (stepping, injection, etc.)
# Keep: init, loop, display only
vim test_adapter.c
git add test_adapter.c
git commit                  # Retry
```

### ⚠️ Warning: "Generated file mismatch"

```
Warning: adapter_gen.h doesn't match gennet output
```

**Fix:**
```bash
cd .hft_staging/adapter
python3 gennet.py adapter.net.json > adapter_gen.h
git add adapter_gen.h
git commit                  # Retry
```

## Allowed Commit Messages

```bash
# ✅ GOOD
git commit -m "feat: add adapter — price feed"
git commit -m "fix: gate-level arithmetic validation"
git commit -m "docs: improve CLAUDE.md"

# ❌ BAD
git commit -m "feat: adapter

Co-Authored-By: Claude Haiku <noreply@anthropic.com>"

git commit -m "feat: adapter — written with Claude Code"
```

## If You Need to Override

```bash
# Emergency bypass (with founder approval only)
git commit --no-verify -m "message"

# Note: Still must pass gate.sh before graduation
```

## Pre-commit Hook Path

```
/Users/bbrn/fpga-rtl/.git/hooks/pre-commit
```

## Verify Hook is Active

```bash
# Check it exists and is executable
ls -l .git/hooks/pre-commit

# Expected output:
# -rwxr-xr-x  ... pre-commit

# If not executable:
chmod +x .git/hooks/pre-commit
```

## Resources

- Full hook documentation: `.claude/hooks/HOOKS.md`
- AI attribution policy: `.claude/skills/no-ai-attribution.md`
- Vault immutability: `.claude/skills/immutability-enforcement.md`
- Thin test rules: `.claude/skills/thin-test-philosophy.md`
