#!/bin/sh
# gate.sh — the C-as-RTL acceptance gate for a component. THIS is the project's
# reviewer (it replaces semgrep/CVE/lint, which do not apply to a netlist build).
# A component is "validated" only when this passes.
#
#   Usage: .hft_staging/gate.sh <component-dir>
#     e.g. .hft_staging/gate.sh .hft_staging/adapter
#
# Runs, in order:
#   1) netlist validator   — single-writer / no-overlap / no-floating
#   2) build (make)        — generates device C + compiles -Werror + runs thin test
#   3) clean-room build    — rebuild from committed HEAD in a temp dir, proving it
#                            builds from git (not from a dirty working tree).
#                            Skipped (with a note) if the component (or a sibling
#                            it depends on) is uncommitted.
#
# Dependency-aware clean-room: a component may DEPEND on a sibling's published
# interface (e.g. the adapter DEPOSITS into the wire bus, so it regenerates the
# wire's canonical seam header from ../wire/wire.net.json at build time — there
# is NO committed second copy). Archiving the component prefix in isolation would
# hide that sibling and force a duplicate. So we archive the whole .hft_staging
# staging tree from HEAD, then build INSIDE the component's subdir: the component
# still builds purely from committed git state, with its declared sibling deps
# present exactly as committed. The guarantee (builds from HEAD, not the dirty
# working tree) is intact and now covers cross-component seams.
set -e

DIR=$1
[ -n "$DIR" ] || { echo "usage: gate.sh <component-dir>"; exit 2; }
[ -d "$DIR" ] || { echo "[gate] no such dir: $DIR"; exit 2; }
ROOT=$(git -C "$DIR" rev-parse --show-toplevel)
PREFIX=$(cd "$DIR" && git rev-parse --show-prefix)   # e.g. .hft_staging/adapter/
# the staging tree that holds this component + its sibling deps (.hft_staging/).
STAGE_PREFIX=$(printf '%s' "$PREFIX" | sed -E 's#^([^/]+/).*#\1#')   # e.g. .hft_staging/
COMPONENT=$(printf '%s' "$PREFIX" | sed -E 's#^[^/]+/([^/]+)/.*#\1#')

echo "==> [gate] 1/3 validate netlist"
( cd "$DIR" && python3 validate.py ./*.net.json )

echo "==> [gate] 2/3 build + thin test (working tree)"
# Hard-fail on any build/test error. A non-compiling component MUST NOT pass the
# gate (a silent `&&` here previously let -Werror failures through). Run the
# thin-test target explicitly so the compile actually happens.
if ! ( cd "$DIR" && make test >/dev/null 2>&1 ); then
    echo "    [FAIL] build / thin test failed — rerun 'make test' in $DIR to see the error"
    exit 2
fi
echo "    build+test OK"

# --- gate_level_arithmetic enforcement (founder ruling) ----------------------
# The device datapath is STRUCTURAL CELLS ONLY: the generated *_tick body must
# contain NO native C +/-/* arithmetic on data — add/sub goes through the
# cell_addsub fa-carry-chain primitive (CLAUDE.md "Gate-level arithmetic").
#
# Method (single awk pass per *_gen.h, robust against comment prose):
#   1) Track whether we are inside a *_tick(...) function body. A body opens on a
#      line matching "_tick(" and closes on the first line that is a lone "}" at
#      column 0 (every generated tick closes that way). Helper functions
#      (cmp_*, cell_*) and the free-running *_run loop are OUTSIDE the body, so
#      their loop counters are never scanned.
#   2) STRIP comments before scanning: block comments /* ... */ (including the
#      multi-line PHC_SUBSEC fold note) and line comments //. Comment prose with
#      hyphens/pluses can therefore never trip the check.
#   3) On the surviving CODE, blank out every cell_*( call's name AND its argument
#      operators are legitimate only inside the primitive — but the bare data-path
#      operators we forbid appear OUTSIDE cell_ calls. We strip recognised safe
#      tokens (shifts >> <<, and the loop step i = i + 1ULL) then flag any
#      remaining +, -, or * that sits between code tokens.
# A hit => the device tick did native arithmetic on data => FAIL (exit 3).
echo "==> [gate] 2b/3 gate-level arithmetic (no native +/-/* in generated tick)"
( cd "$DIR" && for GENH in *_gen.h; do
    [ -f "$GENH" ] || continue
    HITS=$(awk '
      # --- strip block comments spanning lines ---
      {
        line = $0
        out  = ""
        if (incomment) {
          idx = index(line, "*/")
          if (idx == 0) { next }                  # whole line is comment
          line = substr(line, idx + 2)
          incomment = 0
        }
        while ((s = index(line, "/*")) > 0) {
          out = out substr(line, 1, s - 1)
          rest = substr(line, s + 2)
          e = index(rest, "*/")
          if (e == 0) { incomment = 1; line = ""; break }
          line = substr(rest, e + 2)
        }
        out = out line
        # --- strip line comments ---
        c = index(out, "//"); if (c > 0) out = substr(out, 1, c - 1)
        $0 = out
      }
      # the signature line opens the body but is itself a declarator
      # (word_t *r / wire_word_t *bus) — skip scanning it.
      /[a-z_]+_tick\(/ { inbody = 1; next }
      inbody {
        code = $0
        gsub(/i = i \+ 1ULL/, "", code)            # loop step (index math)
        gsub(/>>|<</, "", code)                     # shifts are not add/sub/mul
        if (code ~ /[A-Za-z0-9_)\]][ \t]*[+*-][ \t]*[A-Za-z0-9_(]/) {
          print NR ": " $0
        }
      }
      inbody && /^}/ { inbody = 0 }
    ' "$GENH")
    if [ -n "$HITS" ]; then
        echo "    FAIL — native arithmetic operator in generated tick ($GENH):"
        printf '%s\n' "$HITS" | sed 's/^/      /'
        exit 3
    fi
    echo "    $GENH tick: no native +/-/* — OK"
done ) || exit 3

echo "==> [gate] 2c/3 build-sequence (device logic generated, not hand-written)"
# Hand-written .c/.h (NOT cells.h, NOT *_gen.h) must NOT define a *_tick or
# compose cell_*() logic — the device tick comes ONLY from gennet -> *_gen.h.
( cd "$DIR" && for SRC in *.c *.h; do
    [ -f "$SRC" ] || continue
    case "$SRC" in cells.h|*_gen.h) continue;; esac
    HITS=$(grep -nE 'cell_(buf|not|and|or|xor|mux|eqmask|fa|gate|sar|dff|addsub)[[:space:]]*\(|^[[:space:]]*(static[[:space:]]+inline[[:space:]]+)?void[[:space:]]+[a-z_]+_tick[[:space:]]*\(' "$SRC" \
          | grep -vE '^[0-9]+:[[:space:]]*(/\*|\*|//)')
    if [ -n "$HITS" ]; then
        echo "    [FAIL] $SRC — hand-written device logic; write the netlist + emitter, run gennet:"
        printf '%s\n' "$HITS" | sed 's/^/      /'
        exit 3
    fi
done ) || exit 3
echo "    no hand-written device logic — OK"

echo "==> [gate] 2d/3 flip-flop logic content (cell calls in device C)"
# Every flip-flop-level device MUST contain at least one structural cell call
# (cell_addsub, cell_mux, cell_cmp_lt, cell_eqmask, cell_gate, cmp_lt, etc.).
# Empty COMPUTE phases (register stubs) pass all prior gates but are incomplete
# architecturally. This check catches incomplete specifications at gate time.
# Scope: only generated headers OWNED by this component (those with a matching
# committed netlist here). Sibling seam headers regenerated at build time (e.g.
# wire_gen.h inside adapter/) are passive register maps by design and are
# checked in their own component's gate run.
( cd "$DIR" && for GENH in *_gen.h; do
    [ -f "$GENH" ] || continue
    BASE=${GENH%_gen.h}
    [ -f "$BASE.net.json" ] || { echo "    $GENH: sibling seam header (no local netlist) — skipped"; continue; }
    CELL_COUNT=$(grep -o "cell_[a-z_]*(" "$GENH" 2>/dev/null | wc -l)
    if [ "$CELL_COUNT" -eq 0 ]; then
        echo "    [FAIL] $GENH — no structural cell calls found"
        echo "           Device C is a register stub (empty COMPUTE phase)"
        echo ""
        echo "           Possible causes:"
        echo "           1. Netlist has no comb_nodes (emitter did not generate logic)"
        echo "           2. YAML spec omitted gate-level primitive definitions"
        echo "           3. gennet did not translate comb_nodes to cell calls"
        echo ""
        echo "           Verify that:"
        echo "           — Spec includes comb_nodes with gate-level definitions"
        echo "           — Emitter generated complete netlist with wiring"
        echo "           — gennet translated cells to function calls"
        exit 3
    fi
    echo "    $GENH: $CELL_COUNT cell calls — OK"
done ) || exit 3

# --- Phase-0 enforcement checks (missing check script = missing enforcement = FAIL)
CHECKS=$(cd "$(dirname "$0")" && pwd)/checks

echo "==> [gate] 2e/3 byte-match: committed *_gen.h reproduces from committed netlist"
# Build-sequence law, closed: the committed *_gen.h must be EXACTLY what gennet
# produces from the committed netlist — re-run the generator in a temp copy and
# cmp byte-for-byte. Any drift (hand-edited gen.h, stale netlist) => FAIL.
[ -x "$CHECKS/check_generated.sh" ] || { echo "    FAIL — missing enforcement script: $CHECKS/check_generated.sh"; exit 3; }
"$CHECKS/check_generated.sh" "$DIR" || exit 3

echo "==> [gate] 2f/3 cells.h canon (primitives byte-match the canonical cells.h)"
[ -x "$CHECKS/check_cells_canon.sh" ] || { echo "    FAIL — missing enforcement script: $CHECKS/check_cells_canon.sh"; exit 3; }
"$CHECKS/check_cells_canon.sh" "$DIR" || exit 3

echo "==> [gate] 2g/3 clock rule (self-running clock, no external step) per netlist"
[ -f "$CHECKS/check_clock_rule.py" ] || { echo "    FAIL — missing enforcement script: $CHECKS/check_clock_rule.py"; exit 3; }
( cd "$DIR" && for NET in *.net.json; do
    [ -f "$NET" ] || continue
    python3 "$CHECKS/check_clock_rule.py" "$NET" || exit 3
done ) || exit 3

echo "==> [gate] 3/3 clean-room build from committed HEAD"
# Uncommitted check covers the whole staging tree: a sibling dep changing would
# also invalidate a clean-room build of this component, so gate the real artifact
# only when the component AND its sibling deps are committed.
if ! git -C "$ROOT" diff --quiet HEAD -- "$STAGE_PREFIX" \
   || [ -n "$(git -C "$ROOT" ls-files --others --exclude-standard -- "$STAGE_PREFIX")" ]; then
    echo "    SKIPPED — staging tree has uncommitted changes (commit to gate the real artifact)"
else
    # Strip the leading path so STAGE_PREFIX lands at the temp root; then build
    # inside the component subdir, with sibling deps present exactly as committed.
    N=$(printf '%s' "$STAGE_PREFIX" | tr -cd '/' | wc -c | tr -d ' ')
    TMP=$(mktemp -d)
    git -C "$ROOT" archive HEAD "$STAGE_PREFIX" | tar -x -C "$TMP" --strip-components="$N"
    ( cd "$TMP/$COMPONENT" && make >/dev/null 2>&1 ) && echo "    clean-room build OK ($TMP/$COMPONENT)"
    rm -rf "$TMP"
fi

echo "==> [gate] PASS: $DIR"
