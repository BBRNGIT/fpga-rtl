#!/bin/sh
# contract.sh — THE replica contract, executable. The contract is not prose; it is
# this command. A .c replica is conformant iff this exits 0.
#
#   ./contract.sh            # run the library proof + gate EVERY replica
#   ./contract.sh CARRY8     # the library proof + gate ONE replica
#   ./contract.sh --lib      # only the component-library proof (the verbs/parts)
#
# What it enforces (all must pass):
#   L  the component library + language verbs compile and self-test (lib/test_components)
#   then for each replica, gate_replica.py:
#   C1 exists at the .v-mirrored path        C5 spec-vector behaviour test exits 0
#   C2 compiles                              C6 every information-bearing .v line cited
#   C3 .v annotations carried into the .c    C7 each assign realized beside its citation
#   C4 built from library verbs; no native logic computes a signal level
#
# Exit 0 = contract satisfied. Non-zero = a violation was found (message says which).
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
LIB="$HERE/lib"
GATE="$HERE/clib_gate/gate_replica.py"
CC="${CC:-cc}"

say(){ printf '%s\n' "$*"; }
rule(){ printf '%s\n' "------------------------------------------------------------"; }

# ---- L : the component library + language verbs must compile and self-test -------
prove_library(){
    say "[L] component library + language verbs (lib/test_components)"
    tc="$(mktemp -t contract_lib.XXXXXX)"
    if ! "$CC" -O0 -o "$tc" "$LIB/test_components.c" "$LIB/components.c" 2>"$tc.err"; then
        say "[L] FAIL — library does not compile:"; sed 's/^/      /' "$tc.err"; rm -f "$tc" "$tc.err"; return 1
    fi
    if ! out="$("$tc")"; then
        say "[L] FAIL — library self-test failed:"; printf '%s\n' "$out" | sed 's/^/      /'; rm -f "$tc" "$tc.err"; return 1
    fi
    printf '%s\n' "$out" | tail -1 | sed 's/^/      /'
    rm -f "$tc" "$tc.err"; say "[L] PASS"; rule
}

case "${1:-}" in
  --lib) prove_library; exit 0 ;;
  "" )   prove_library; say "[gate] every replica:"; python3 "$GATE" --all ;;
  * )    prove_library; say "[gate] replica: $1"; python3 "$GATE" "$1" ;;
esac
