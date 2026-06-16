# CI/CD Pipeline — Professional Grade

This repository uses **GitHub Actions** for automated building, testing, and releasing of the V4 UNISIM cell transcription project.

## Overview

### CI (Continuous Integration)
**Workflow:** `.github/workflows/ci.yml`

**Triggers:**
- On every `push` to `main`, `master`, or `develop` branches
- On every `pull_request` to those branches
- Only if `v4/**` files changed (to avoid noise)

**What it does:**
1. **Compile components library** — `v4/lib/components.c` → object file
2. **Run VCC test** — Verify reference component works
3. **Compile all transcribed cells** — Each `v4/clib/unisims/*.c` → object file
4. **Type safety check** — Verify no deprecated `_t` suffixes
5. **Semantic validation** — Check port/parameter counts against `.v` specs

**Success criteria:**
- ✅ All cells compile without errors
- ✅ No type errors or undefined symbols
- ✅ VCC test passes
- ✅ All code quality checks pass

**Failure behavior:**
- ❌ Blocks merge to main (required check)
- ❌ Blocks pull request if CI fails
- ❌ Error logs available in GitHub Actions UI

### CD (Continuous Deployment)
**Workflow:** `.github/workflows/cd.yml`

**Triggers:**
- On every `push` to `main` or `master` branches (after CI passes)
- Manual trigger via `workflow_dispatch` (run button on GitHub)

**What it does:**
1. **Pre-release validation** — Run full test suite again
2. **Auto-detect version** — Bump patch version or use manual input
3. **Build artifacts** — Create tarball of v4/ directory
4. **Generate release notes** — Markdown with cell status, build info
5. **Create GitHub release** — Tag commit, attach artifacts, publish

**Artifacts created:**
- `fpga-rtl-v4-vX.Y.Z.tar.gz` — Complete v4 directory (ready to use)
- `BUILD_MANIFEST.txt` — Build metadata
- GitHub Release page with release notes

**Example release:**
```
Release: v0.1.0
Assets:
  - fpga-rtl-v4-v0.1.0.tar.gz (500 KB)
  - BUILD_MANIFEST.txt
```

---

## Workflow Files

### `ci.yml` — Continuous Integration

| Phase | Purpose | Failure = Block |
|-------|---------|-----------------|
| **build** | Compile & test | Yes (merge blocked) |
| **lint** | Code quality | Yes (merge blocked) |
| **summary** | Report status | Informational |

**Jobs:**

#### Job: `build`
- Compiles `components.c` and all cells
- Runs `test_vcc` (passes only if VCC source works)
- Checks for type safety (`net_t` suffixes)
- Validates semantic correctness (port counts)

**On failure:**
- Shows compilation error in GitHub UI
- Displays which cell/file failed
- Suggests fix (usually add missing macro to verilog.h)

#### Job: `lint`
- Checks file naming conventions (uppercase start)
- Verifies all `.c` files include `verilog.h`
- Looks for hand-written components (should use verilog.h)

**On failure:**
- Shows which file violates convention
- Suggests correction

#### Job: `summary`
- Aggregates results from `build` and `lint`
- Passes only if ALL checks pass

---

### `cd.yml` — Continuous Deployment

| Phase | Purpose | Outcome |
|-------|---------|---------|
| **validate** | Pre-release checks | Fails if build broken |
| **version** | Determine release tag | Auto-increment or manual |
| **build-artifacts** | Create release assets | Tarball + manifest |
| **release** | Publish to GitHub | Creates release page |
| **notify** | Report success | Summary message |

**Jobs:**

#### Job: `validate`
- Runs same tests as CI
- Ensures release is valid before tagging

#### Job: `version`
- **Auto mode (default):** Detects last tag, bumps patch version
  - `v0.0.0` → `v0.0.1` (patch bump)
  - `v0.1.5` → `v0.1.6` (patch bump)
- **Manual mode:** Use `workflow_dispatch` to specify version
  - Input field: `v0.1.0`, `v1.0.0`, etc.

#### Job: `build-artifacts`
- Creates `fpga-rtl-v4-vX.Y.Z.tar.gz` containing:
  - `v4/` — all source files
  - `CLAUDE.md` — project docs
  - Everything except `.git`, `.github`, unneeded directories
- Size: ~500 KB (compressed)

#### Job: `release`
- Tags commit with version
- Creates GitHub Release
- Attaches tarball and manifest
- Publishes release notes with:
  - Cell status table
  - Build validation summary
  - Next steps for Phase 1

#### Job: `notify`
- Prints success summary
- Shows release URL
- Guides next actions

---

## Usage

### Running CI Manually (for debugging)

If you want to test the CI locally before pushing:

```bash
cd v4
./BUILD.sh
```

This runs the equivalent of the CI pipeline on your machine.

### Triggering CD Manually

Navigate to: **Actions** → **CD — Release & Publish** → **Run workflow**

**Inputs:**
- **version:** Leave as `auto` (auto-detect) or enter `v0.2.0` (manual)

**Result:**
- Creates release on GitHub
- Artifacts available for download

### Checking CI/CD Status

**On GitHub:**
1. Go to **Actions** tab
2. See workflow runs for each push/PR
3. Click run to see detailed logs
4. Expand job to see step outputs

**In CLI:**
```bash
# List recent workflow runs
gh run list -R bbrnfx/fpga-rtl

# Watch workflow in real-time
gh run watch <run-id>

# View logs
gh run view <run-id> --log
```

---

## Configuration

### Branch Protection Rules

To enforce CI/CD, configure GitHub branch protection for `main`:

**Settings** → **Branches** → **Branch protection rules** → **main**

Enable:
- ✅ **Require status checks to pass before merging**
  - Select: `CI — Build & Validate V4 Cells / build`
  - Select: `CI — Build & Validate V4 Cells / lint`
  - Select: `CI — Build & Validate V4 Cells / summary`
- ✅ **Require branches to be up to date before merging**
- ✅ **Dismiss stale pull request approvals**

### Concurrency Control

Both workflows have `concurrency` settings to prevent parallel runs on the same branch:

```yaml
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
```

This means:
- If you push twice in quick succession, second push cancels first run
- Saves CI minutes (useful at scale)

---

## Extending the Pipelines

### Adding New Validation Checks

Edit `.github/workflows/ci.yml` and add a step in the `build` job:

```yaml
      - name: Custom validation
        run: |
          # Your validation script here
          ./custom_check.sh
          echo "✓ Custom check passed"
```

### Changing Release Artifacts

Edit `.github/workflows/cd.yml`, `build-artifacts` job:

```yaml
      - name: Create release tarball
        run: |
          tar --exclude=.git \
              --exclude=unwanted_dir \
              -czf fpga-rtl-v4-${VERSION}.tar.gz v4/
```

### Triggering on Different Events

Modify the `on:` trigger in either workflow:

```yaml
on:
  push:
    branches: [ main, develop ]
    tags: [ 'v*' ]  # Also trigger on version tags
```

---

## Troubleshooting

### CI Fails: "undefined macro"

**Problem:** New cell uses a macro not in `verilog.h`

**Solution:**
1. Identify the macro from compiler error
2. Add it to `v4/lib/verilog.h`
3. Push again (CI re-runs automatically)

**Example:**
```
error: 'DELAY' undeclared
→ Add to verilog.h: #define DELAY(n)  /* delay marker */
```

### CI Fails: "net_t not declared"

**Problem:** Cell still uses old `net_t` type

**Solution:**
1. Edit cell `.c` file
2. Replace `net_t` with `net`
3. Commit and push
4. CI re-runs

### CD Fails: Release already exists

**Problem:** Tag already pushed

**Solution:**
1. Delete tag locally: `git tag -d v0.1.0`
2. Delete on GitHub: `git push origin :refs/tags/v0.1.0`
3. Retry CD manually with new version

### Artifacts Not Uploading

**Problem:** GitHub Actions storage full

**Solution:**
- Delete old artifacts (older than 90 days)
- Or adjust `retention-days` in workflow

---

## Permissions & Secrets

### Required Permissions

The workflow needs:
- ✅ `contents: write` — To create releases and tags
- ✅ `actions: read` — To read workflow status

These are **automatically granted** for repositories (no setup needed).

### No Secrets Required

This pipeline uses only public information (GITHUB_TOKEN is built-in). No external service logins needed.

---

## Costs

### GitHub Actions Free Tier

- **Free:** 2,000 CI/CD minutes per month per account
- **Usage per run:** ~5 minutes (compile + test)
- **Monthly budget:** ~400 runs (plenty for active development)

If you exceed free tier:
- GitHub charges $0.25 per 1,000 minutes
- Or pay flat rate: $21/month for 3,000 additional minutes

### Optimization

To stay within free tier:
- Use concurrency control (already enabled)
- Cancel stale runs (already enabled)
- Run on `push` only, not on every PR (current config is PR-inclusive, adjust if needed)

---

## Best Practices

1. **Always test locally before pushing:**
   ```bash
   cd v4
   ./BUILD.sh
   ```

2. **Use descriptive commit messages:**
   ```bash
   git commit -m "Add FDRE cell transcription (Tier 1)"
   ```

3. **Push frequently** (CI catches issues fast)

4. **Review CI logs** when builds fail (not just check red/green)

5. **Use draft releases** during development:
   - In `cd.yml`, change `draft: false` to `draft: true`
   - Allows you to edit release notes before publishing

6. **Version consistently:**
   - Use semantic versioning: `vMAJOR.MINOR.PATCH`
   - Bump MAJOR for breaking changes (rare for this project)
   - Bump MINOR for feature additions (new cells/phases)
   - Bump PATCH for fixes (type fixes, macro additions)

---

## Next Steps

1. **Push to GitHub:**
   ```bash
   git add .github/
   git commit -m "feat: Add professional CI/CD pipeline"
   git push origin main
   ```

2. **Watch first CI run:**
   - Go to **Actions** tab
   - See workflow execute
   - Confirm all checks pass

3. **Merge a cell (Phase 1):**
   ```bash
   git add v4/clib/unisims/FDRE.c
   git commit -m "Add FDRE cell (Tier 1, Phase 1)"
   git push
   # CI runs automatically
   # If passes: can merge to main
   # If fails: fix and push again
   ```

4. **Create first release (optional):**
   - Go to **Actions** → **CD — Release & Publish**
   - Click **Run workflow**
   - Leave version as `auto`
   - Watch it create a release

---

## Support

For issues or questions:
- Check GitHub Actions logs (most detailed)
- Review `.github/workflows/*.yml` (source of truth)
- See `v4/CE_PLAN.md` for architectural context

