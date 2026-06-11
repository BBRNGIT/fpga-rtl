#!/bin/sh
# check_cells_canon.sh <component_dir>
#
# Verifies a component's cells.h is byte-identical to the canonical cell
# library (.hft_staging/cells/cells.h) modulo the header-guard token: the
# identifier in the #ifndef/#define/#endif guard lines is normalized to a
# placeholder in both files before comparing, so component-specific guards
# (e.g. ADAPTER_CELLS_H) are permitted; nothing else may differ.
#
# Fails (exit 1) if:
#   - the component's cells.h diverges from canon (shows the divergent lines)
#   - the component has no cells.h but a *_gen.h in it includes "cells.h"
#
# Passes (exit 0) if the copy matches, or the component does not use cells.h.

set -u

if [ $# -ne 1 ]; then
    echo "usage: $0 <component_dir>" >&2
    exit 2
fi

COMP_DIR=$1
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CANON=$SCRIPT_DIR/../cells/cells.h

if [ ! -d "$COMP_DIR" ]; then
    echo "check_cells_canon: FAIL: not a directory: $COMP_DIR" >&2
    exit 2
fi
if [ ! -f "$CANON" ]; then
    echo "check_cells_canon: FAIL: canonical cells.h not found at $CANON" >&2
    exit 2
fi

COMP_CELLS=$COMP_DIR/cells.h

# Normalize the header-guard token (the identifier ending in CELLS_H, or the
# bare CELLS_H) in #ifndef/#define/#endif lines to a fixed placeholder.
normalize() {
    sed -E -e 's/[A-Za-z_][A-Za-z0-9_]*CELLS_H/__GUARD__/g' "$1"
}

if [ -f "$COMP_CELLS" ]; then
    TMPA=$(mktemp) || exit 2
    TMPB=$(mktemp) || { rm -f "$TMPA"; exit 2; }
    trap 'rm -f "$TMPA" "$TMPB"' EXIT
    normalize "$CANON"      > "$TMPA"
    normalize "$COMP_CELLS" > "$TMPB"
    if cmp -s "$TMPA" "$TMPB"; then
        echo "check_cells_canon: PASS: $COMP_CELLS matches canon (modulo header guard)"
        exit 0
    fi
    # Classify: strip comments and blank lines; if the C code still matches,
    # this is comment-only drift; otherwise it is a semantic divergence.
    strip_comments() {
        sed -e 's://.*$::' "$1" | awk 'BEGIN{inc=0}
            { line=$0; out="";
              while (length(line)>0) {
                if (inc) { p=index(line,"*/"); if(p==0){line="";break} line=substr(line,p+2); inc=0 }
                else { p=index(line,"/*"); if(p==0){out=out line; line=""} else {out=out substr(line,1,p-1); line=substr(line,p+2); inc=1} }
              }
              gsub(/[ \t]+$/,"",out); if (out!="") print out }'
    }
    TMPC=$(mktemp); TMPD=$(mktemp)
    trap 'rm -f "$TMPA" "$TMPB" "$TMPC" "$TMPD"' EXIT
    strip_comments "$TMPA" > "$TMPC"
    strip_comments "$TMPB" > "$TMPD"
    if cmp -s "$TMPC" "$TMPD"; then
        KIND="comment-only drift (C code identical)"
    else
        KIND="SEMANTIC divergence (C code differs)"
    fi
    echo "check_cells_canon: FAIL: $COMP_CELLS diverges from canonical $CANON — $KIND"
    echo "Divergent lines (canon vs component, header guard normalized):"
    diff -u "$TMPA" "$TMPB" | sed -n '3,40p'
    exit 1
fi

# No cells.h in the component: fail if any *_gen.h here includes cells.h.
for g in "$COMP_DIR"/*_gen.h; do
    [ -f "$g" ] || continue
    if grep -q '#include[[:space:]]*"cells\.h"' "$g"; then
        echo "check_cells_canon: FAIL: missing cells.h — $g includes \"cells.h\" but $COMP_DIR has no cells.h"
        exit 1
    fi
done

echo "check_cells_canon: PASS: $COMP_DIR does not use cells.h (no copy required)"
exit 0
