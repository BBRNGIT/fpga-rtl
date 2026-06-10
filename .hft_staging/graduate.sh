#!/bin/sh
# graduate.sh — promote a VALIDATED, COMMITTED staging component into the
# immutable .hft vault repo, in one reproducible step.
#
#   Usage: .hft_staging/graduate.sh <component> [--regraduate]
#     <component>   a directory under .hft_staging/ (e.g. adapter)
#     --regraduate  allow overwriting an already-graduated component
#                   (sets the vault's HFT_ALLOW_REGRADUATE override). Default
#                   refuses to touch an existing component.
#
# Guarantees: only source that is (a) committed in the parent repo and (b) passes
# its own project gate (make validate + make) is copied. The copy is HEAD via
# `git archive`, so it is byte-identical to the validated commit — no build
# artifacts, no dirty working-tree content.
set -e

COMP=$1
[ -n "$COMP" ] || { echo "usage: graduate.sh <component> [--regraduate]"; exit 2; }
REGRAD=0; [ "$2" = "--regraduate" ] && REGRAD=1

ROOT=$(git rev-parse --show-toplevel)
SRC="$ROOT/.hft_staging/$COMP"
VAULT="$ROOT/.hft"
DEST="$VAULT/$COMP"

[ -d "$SRC" ]        || { echo "[abort] no such staging component: .hft_staging/$COMP"; exit 1; }
[ -d "$VAULT/.git" ] || { echo "[abort] vault repo not initialized (.hft/.git missing)"; exit 1; }

# 1) refuse dirty/uncommitted source — graduation copies HEAD (the validated commit).
if ! git -C "$ROOT" diff --quiet HEAD -- ".hft_staging/$COMP" \
   || [ -n "$(git -C "$ROOT" ls-files --others --exclude-standard -- ".hft_staging/$COMP")" ]; then
    echo "[abort] .hft_staging/$COMP has uncommitted or untracked changes."
    echo "        Commit the validated source first — graduation copies HEAD."
    exit 1
fi

# 2) existing component is protected — require --regraduate to overwrite.
if [ -e "$DEST" ] && [ "$REGRAD" -ne 1 ]; then
    echo "[abort] '$COMP' is already graduated. Re-run with --regraduate to overwrite."
    exit 1
fi

# 3) project gate: only a component that validates + builds may graduate.
#    `make clean` FIRST — a graduate gate must be a CLEAN build, not one masked
#    by stale generated artifacts. (A stale sibling _gen.h once let a broken vault
#    build graduate; clean reproduces the vault's from-scratch condition.)
echo "==> gate: make clean + make validate + make  (.hft_staging/$COMP)"
LOG=$(mktemp)
if ! ( cd "$SRC" && make clean >/dev/null 2>&1; make validate && make ) >"$LOG" 2>&1; then
    echo "[abort] gate FAILED — not validated, not graduating:"; tail -20 "$LOG"; rm -f "$LOG"; exit 1
fi
rm -f "$LOG"
echo "    gate PASS (clean build)"

# 3b) logic content validation — catch stubs before graduation.
#     Every flip-flop-level device MUST contain at least one structural cell call.
#     Register-only stubs pass gate 2a-2c but are architecturally incomplete.
echo "==> logic content check: verify cell calls in device C"
CELL_COUNT=0
for GENH in "$SRC"/*_gen.h; do
    [ -f "$GENH" ] || continue
    COUNT=$(grep -o "cell_[a-z_]*(" "$GENH" 2>/dev/null | wc -l)
    if [ "$COUNT" -gt "$CELL_COUNT" ]; then
        CELL_COUNT="$COUNT"
    fi
    if [ "$COUNT" -eq 0 ]; then
        echo "[abort] $GENH contains NO structural cell calls (register stub, not RTL)"
        echo "        Architecture is incomplete: spec missing comb_nodes and/or wiring."
        echo "        Reference: .hft_staging/INDICATOR_ARCHITECTURE_TEMPLATE.md"
        exit 1
    fi
done
echo "    cell_count: $CELL_COUNT — OK (device contains flip-flop logic)"

# 4) copy the validated, committed source (tracked files only — no artifacts).
rm -rf "$DEST"; mkdir -p "$DEST"
git -C "$ROOT" archive HEAD ".hft_staging/$COMP" | tar -x -C "$DEST" --strip-components=2

# 5) commit into the vault (its pre-commit immutability guard applies).
cd "$VAULT"
git add "$COMP"
if git diff --cached --quiet; then
    echo "==> '$COMP' already up-to-date in vault — nothing to commit."
    exit 0
fi
if [ "$REGRAD" -eq 1 ]; then
    HFT_ALLOW_REGRADUATE=1 git commit -q -m "vault: re-graduate $COMP (validated, byte-identical from staging)"
else
    git commit -q -m "vault: graduate $COMP (validated, byte-identical from staging)"
fi
echo "==> graduated '$COMP' -> .hft/$COMP   (vault $(git rev-parse --short HEAD))"
