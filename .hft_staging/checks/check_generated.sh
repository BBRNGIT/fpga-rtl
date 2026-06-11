#!/bin/sh
# check_generated.sh — build-sequence-law byte-match enforcement.
#
# The committed *_gen.h is a VALIDATION ARTIFACT: it must be exactly what
# gennet produces from the committed netlist. Anything else means the device C
# was hand-edited (or the netlist drifted) — a build-sequence-law violation.
#
#   Usage: check_generated.sh <component-dir>
#
# For each <module>.net.json in the component dir, this re-runs the component's
# generator in a TEMP COPY of the dir (never touching the source tree — safe on
# the immutable .hft vault) and byte-compares (cmp) the regenerated header
# against the committed one. Any mismatch => FAIL (exit 3).
#
# Generator/output discovery, in order:
#   1) Makefile NET/GEN/gen-recipe parse — handles components whose gen.h name
#      differs from the netlist stem (e.g. .hft/taiosc: taisoc.net.json), and
#      components with a non-default generator script.
#   2) Fallback convention: python3 gennet.py <module>.net.json > <module>_gen.h
set -e

DIR=$1
[ -n "$DIR" ] || { echo "usage: check_generated.sh <component-dir>"; exit 2; }
[ -d "$DIR" ] || { echo "[check_generated] no such dir: $DIR"; exit 2; }
DIR=$(cd "$DIR" && pwd)

# Parse Makefile (if present) for NET=, GEN=, and the generator script used in
# the gen recipe line ("$(PY) <script> $(NET) > $(GEN)").
MK_NET=""; MK_GEN=""; MK_SCRIPT=""
if [ -f "$DIR/Makefile" ]; then
    MK_NET=$(sed -nE 's/^NET[[:space:]]*=[[:space:]]*([^[:space:]]+).*/\1/p' "$DIR/Makefile" | head -1)
    MK_GEN=$(sed -nE 's/^GEN[[:space:]]*=[[:space:]]*([^[:space:]]+).*/\1/p' "$DIR/Makefile" | head -1)
    MK_SCRIPT=$(sed -nE 's/^[[:space:]]*\$\(PY\)[[:space:]]+([A-Za-z0-9_./-]*gennet[A-Za-z0-9_.-]*\.py)[[:space:]]+\$\(NET\).*/\1/p' "$DIR/Makefile" | head -1)
fi

FOUND=0
FAIL=0
for NET in "$DIR"/*.net.json; do
    [ -f "$NET" ] || continue
    NETBASE=$(basename "$NET")
    MODULE=$(basename "$NET" .net.json)

    # resolve generator script + expected output for THIS netlist
    GENH="${MODULE}_gen.h"
    SCRIPT="gennet.py"
    if [ "$NETBASE" = "$MK_NET" ]; then
        [ -n "$MK_GEN" ]    && GENH=$MK_GEN
        [ -n "$MK_SCRIPT" ] && SCRIPT=$MK_SCRIPT
    fi

    if [ ! -f "$DIR/$SCRIPT" ]; then
        echo "    [FAIL] $NETBASE — generator script '$SCRIPT' not found in $DIR"
        FAIL=1; continue
    fi
    if [ ! -f "$DIR/$GENH" ]; then
        # Name fallback: Makefile GEN may be stale (e.g. .hft/taiosc commits
        # taiosc_gen.h while its Makefile says taisoc_gen.h). If exactly one
        # *_gen.h exists in the dir, byte-match against it and note the rename.
        CANDS=$(cd "$DIR" && ls ./*_gen.h 2>/dev/null | wc -l | tr -d ' ')
        if [ "$CANDS" = "1" ]; then
            ALT=$(cd "$DIR" && ls ./*_gen.h | sed 's#^\./##')
            echo "    NOTE: expected '$GENH' not found; using sole header '$ALT' (Makefile/name drift)"
            GENH=$ALT
        else
            echo "    [FAIL] $NETBASE — expected generated header '$GENH' not found in $DIR"
            echo "           (netlist committed without its generated validation artifact)"
            FAIL=1; continue
        fi
    fi
    FOUND=1

    # regenerate in a temp copy (read-only on the source tree — vault-safe)
    TMP=$(mktemp -d)
    cp -R "$DIR/." "$TMP/"
    if ! ( cd "$TMP" && python3 "$SCRIPT" "$NETBASE" > regen_check.out 2> regen_check.err ); then
        echo "    [FAIL] $NETBASE — generator '$SCRIPT' failed to run:"
        sed 's/^/      /' "$TMP/regen_check.err" | head -10
        rm -rf "$TMP"; FAIL=1; continue
    fi
    if cmp -s "$TMP/regen_check.out" "$DIR/$GENH"; then
        echo "    $GENH byte-matches $SCRIPT($NETBASE) — OK"
    else
        echo "    [FAIL] $GENH does NOT byte-match output of: python3 $SCRIPT $NETBASE"
        echo "           Committed device C differs from what the committed netlist generates."
        echo "           Hand-edited *_gen.h or stale netlist — regenerate with 'make gen'."
        cmp "$TMP/regen_check.out" "$DIR/$GENH" 2>/dev/null | sed 's/^/           /' || true
        FAIL=1
    fi
    rm -rf "$TMP"
done

if [ "$FOUND" -eq 0 ] && [ "$FAIL" -eq 0 ]; then
    echo "    no <module>.net.json found in $DIR — nothing to byte-match"
fi
[ "$FAIL" -eq 0 ] || exit 3
exit 0
