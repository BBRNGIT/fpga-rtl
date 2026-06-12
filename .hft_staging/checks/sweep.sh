#!/bin/sh
# sweep.sh — scheduled/CI full conformance sweep (S6). Runs the repo-wide auditor;
# nonzero exit on ANY failure. Wire to cron/CI to catch drift even if a commit
# slipped past the gate-forcing hook. Usage: .hft_staging/checks/sweep.sh
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
echo "=== SCHEDULED CONFORMANCE SWEEP $(date '+%Y-%m-%d %H:%M:%S') ==="
python3 "$HERE/audit_all.py"
