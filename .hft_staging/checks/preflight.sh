#!/bin/sh
# preflight.sh — run at the START of any task (S5). Prints the governing laws and
# current conformance so work begins from the laws (in the codebase), not memory.
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../.." && pwd)
echo "=== GOVERNING LAWS (CLAUDE.md) ==="
grep -nE "^### [0-9]+\. |IMMUTABLE ARCHITECTURAL LAW|BINDING CONDUCT LAW" "$ROOT/CLAUDE.md" | sed 's/^/  /'
echo ""
echo "=== CURRENT CONFORMANCE (audit_all) ==="
python3 "$HERE/audit_all.py"
