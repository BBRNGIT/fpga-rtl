#!/bin/bash
# V4 Build & Test Harness
# Least-friction workflow for transcribing UNISIM cells to C

set -e

PROJECT_ROOT=$(cd "$(dirname "$0")/.." && pwd)
V4_ROOT="$PROJECT_ROOT/v4"
LIB="$V4_ROOT/lib"
CELLS="$V4_ROOT/clib/unisims"

echo "=========================================="
echo "V4 UNISIM Build & Validation"
echo "=========================================="
echo ""

# Stage 1: Compile components library
echo "[1/4] Compiling components library..."
cc -c "$LIB/components.c" -o /tmp/components.o -I "$V4_ROOT" 2>/tmp/build.err || {
    echo "❌ components.c failed to compile"
    cat /tmp/build.err
    exit 1
}
echo "✓ components.o built"

# Stage 2: Run component test
echo "[2/4] Testing VCC component..."
cc "$V4_ROOT/test_vcc.c" /tmp/components.o -o /tmp/test_vcc -I "$V4_ROOT" || {
    echo "❌ test_vcc.c failed to compile"
    exit 1
}
/tmp/test_vcc > /dev/null || {
    echo "❌ test_vcc failed"
    /tmp/test_vcc
    exit 1
}
echo "✓ VCC component verified"

# Stage 3: Compile all transcribed cells
echo "[3/4] Compiling transcribed cells..."
if [ -d "$CELLS" ]; then
    for cell_c in "$CELLS"/*.c; do
        if [ -f "$cell_c" ]; then
            cell_name=$(basename "$cell_c" .c)
            echo "  Compiling $cell_name..."
            cc -c "$cell_c" -o "/tmp/${cell_name}.o" -I "$V4_ROOT" || {
                echo "❌ $cell_c failed"
                exit 1
            }
        fi
    done
    echo "✓ All cells compiled"
else
    echo "⚠ No cells directory found"
fi

# Stage 4: Pre-commit validation (if components.c or test_vcc.c changed)
echo "[4/4] Running pre-commit checks..."
if git diff --cached --name-only 2>/dev/null | grep -qE '(lib/components\.(h|c)|test_vcc\.c)'; then
    if "$PROJECT_ROOT/.git/hooks/pre-commit"; then
        echo "✓ Pre-commit checks passed"
    else
        echo "❌ Pre-commit validation failed"
        exit 1
    fi
else
    echo "⚠ No component changes staged"
fi

echo ""
echo "=========================================="
echo "Build complete. Ready for next cell."
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Transcribe next UNISIM cell to $CELLS/CELL_NAME.c"
echo "  2. Run: $V4_ROOT/BUILD.sh"
echo "  3. If all pass: git add $CELLS/CELL_NAME.c && git commit"
echo ""
