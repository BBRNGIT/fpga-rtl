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
[ -n "$COMP" ] || { echo "usage: graduate.sh <component> [--as <vaultname>] [--regraduate]"; exit 2; }
shift
REGRAD=0
DESTNAME="$COMP"          # vault path name; defaults to the component name
while [ $# -gt 0 ]; do
    case "$1" in
        --regraduate) REGRAD=1 ;;
        --as) shift; DESTNAME="$1"; [ -n "$DESTNAME" ] || { echo "usage: --as <vaultname>"; exit 2; } ;;
        *) echo "unknown arg: $1"; exit 2 ;;
    esac
    shift
done

ROOT=$(git rev-parse --show-toplevel)
SRC="$ROOT/.hft_staging/$COMP"
VAULT="$ROOT/.hft"
# Versioned promotion (Law #8): --as lets a rebuilt component land at a NEW vault
# path (e.g. candle -> candle_v2), superseding an immutable stub without editing
# it in place. The module's internals/seam names are unchanged.
DEST="$VAULT/$DESTNAME"

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
    GBASE=${GENH%_gen.h}
    # Sibling seam headers regenerated in this dir (e.g. wire_gen.h inside
    # adapter/) have no local netlist here — they are checked in their own
    # component's graduation. Skip them. Mirrors gate.sh stage 2d.
    [ -f "$GBASE.net.json" ] || { echo "    $(basename "$GENH"): sibling seam header (no local netlist) — skipped"; continue; }
    # Passive buses (kind: passive_bus, e.g. wire/dom_bus) carry no compute by
    # design — exempt from the logic-content requirement (which catches stub
    # *indicators*, not buses). Mirrors gate.sh stage 2d.
    if [ -f "$GBASE.net.json" ] && grep -q '"kind"[[:space:]]*:[[:space:]]*"passive_bus"' "$GBASE.net.json" 2>/dev/null; then
        echo "    $(basename "$GENH"): passive bus (no compute by design) — exempt"
        CELL_COUNT=1
        continue
    fi
    if [ -f "$GBASE.net.json" ] && grep -q '"kind"[[:space:]]*:[[:space:]]*"fpga_blank"' "$GBASE.net.json" 2>/dev/null; then
        echo "    $(basename "$GENH"): fpga blank (pure device reference, no logic by law) — exempt"
        CELL_COUNT=1
        continue
    fi
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

# 3c) byte-match check — committed *_gen.h must reproduce byte-identically from
#     the committed netlist via gennet (build-sequence law, closed). A missing
#     enforcement script is itself a failure: no enforcement, no graduation.
echo "==> byte-match check: committed *_gen.h reproduces from committed netlist"
CHECK_GEN="$ROOT/.hft_staging/checks/check_generated.sh"
[ -x "$CHECK_GEN" ] || { echo "[abort] missing enforcement script: $CHECK_GEN"; exit 1; }
"$CHECK_GEN" "$SRC" || { echo "[abort] byte-match FAILED — *_gen.h does not reproduce from netlist, not graduating."; exit 1; }

# 4) copy the validated, committed source (tracked files only — no artifacts).
rm -rf "$DEST"; mkdir -p "$DEST"
git -C "$ROOT" archive HEAD ".hft_staging/$COMP" | tar -x -C "$DEST" --strip-components=2

# 5) commit into the vault (its pre-commit immutability guard applies).
cd "$VAULT"
git add "$DESTNAME"
if git diff --cached --quiet; then
    echo "==> '$DESTNAME' already up-to-date in vault — nothing to commit."
    exit 0
fi
if [ "$REGRAD" -eq 1 ]; then
    HFT_ALLOW_REGRADUATE=1 git commit -q -m "vault: re-graduate $DESTNAME (validated, byte-identical from staging)"
else
    git commit -q -m "vault: graduate $DESTNAME (from .hft_staging/$COMP; validated, byte-identical)"
fi
echo "==> graduated '$COMP' -> .hft/$DESTNAME   (vault $(git rev-parse --short HEAD))"
