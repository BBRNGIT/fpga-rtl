#!/bin/sh
# gate_device.sh — the device sign-off conductor (SIGNOFF_SUITE.md, Wave 1).
# Runs every Wave-1 check in order. FAILS CLOSED: a missing check script is itself
# a failure. Any red check stops the gate with a nonzero exit.
#
# Order: provenance/data first (lvs c06), then connectivity (erc, lvs), then
# circuit rules (drc), tool governance (toolgov), integrity (integrity), counts.
#
# Usage: sh gate_device.sh
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
PY=python3
fail() { echo "[gate_device] FAIL: $1"; exit 1; }

# fail-closed: required check scripts must exist
for f in erc.py lvs.py drc.py integrity.py toolgov.py checks_lib.py enforcement_registry.yaml; do
    [ -f "$HERE/$f" ] || fail "missing enforcement file: $f"
done

echo "==> [gate_device] Tier 1 — connectivity (ERC + LVS)"
$PY "$HERE/lvs.py" c06 || fail "C06 connection-provenance"     # guard the data first
$PY "$HERE/erc.py" all || fail "ERC (C01/C02/C03)"
$PY "$HERE/lvs.py" c05 || fail "C05 net-completeness"
$PY "$HERE/lvs.py" c04 || fail "C04 port-direction"
$PY "$HERE/lvs.py" c07 || fail "C07 grid-identity"

echo "==> [gate_device] Tier 2 — circuit rules (DRC)"
$PY "$HERE/drc.py" all || fail "DRC (C08/C09/C12/C14/C15)"

echo "==> [gate_device] Tier 5 — tool governance"
$PY "$HERE/toolgov.py" all || fail "tool-governance (C23/C24)"

echo "==> [gate_device] Tier 4 — generation integrity"
$PY "$HERE/integrity.py" all || fail "integrity (C19/C20/C21/C22)"

echo "==> [gate_device] Tier 3 — counts"
$PY "$HERE/checks_lib.py" counts_match_ds891 || fail "C16 counts-==-DS891"

echo "==> [gate_device] PASS — device signs off (Wave 1 suite)"
exit 0
