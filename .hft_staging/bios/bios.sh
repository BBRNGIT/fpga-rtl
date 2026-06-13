#!/usr/bin/env bash
# bios.sh — THE BIOS CONSOLE (human entry point). Starting this starts the system.
# Boot/config/adapters/dashboard/kill/restart for the FPGA. The console output is
# its OWN — it runs WITHOUT the display adapter; the live dashboard is just one
# option that needs the display adapter, everything else works offline. Adapters
# are scanned from adapters.reg (not hardcoded). Adds no datapath logic: it sets
# config and sequences power; the clocks drive the system.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
FAB="${FPGA_DIR:-$ROOT/fpga}"          # FPGA to control: bare blank (Phase A) -> .bbhft clone (Phase D)
ENGINE="$HERE/engine"; STATE="$HERE/.state"; CONF="$HERE/system.conf"; REG="$HERE/adapters.reg"

build_engine(){ cc -O0 -std=c11 -w -I"$FAB" "$HERE/engine.c" -o "$ENGINE" 2>/tmp/bios_cc.err \
  || { echo "engine build FAILED: $(tail -1 /tmp/bios_cc.err)"; return 1; }; }
state_get(){ grep -q "booted=1" "$STATE" 2>/dev/null && echo ON || echo OFF; }
state_set(){ echo "booted=$1" > "$STATE"; }

banner(){ echo "============== .bbhft  BIOS console =============="
  echo " FPGA: $(basename "$FAB")   power: $(state_get)   ingress: $(grep '^selected=' "$CONF"|cut -d= -f2)"
  echo "================================================="; }
cmd_boot(){ echo "[boot sequence]"; "$ENGINE" boot; state_set 1; }
cmd_shutdown(){ echo "[shutdown]"; "$ENGINE" shutdown; state_set 0; }
cmd_restart(){ cmd_shutdown; echo; cmd_boot; }
cmd_status(){ echo "[status]"; "$ENGINE" status; echo "  session power: $(state_get)"; }
cmd_adapters(){ echo "[registered adapters]  (adapters.reg — scanned, not hardcoded)"
  grep -vE '^\s*#|^\s*$' "$REG" | sed 's/^/  - /'
  echo -n "select ingress adapter (blank=keep): "; read -r a || return
  [ -z "$a" ] && return
  if grep -qE "^\s*$a\s*:" "$REG"; then sed -i.bak "s/^selected=.*/selected=$a/" "$CONF"; echo "  -> ingress = $a"
  else echo "  !! '$a' not in registry"; fi; }
cmd_config(){ echo "[config: system.conf — FPGA + all components]"; sed 's/^/  /' "$CONF"
  echo -n "set 'key=value' (blank=return): "; read -r kv || return
  [ -n "$kv" ] && { printf '%s\n' "$kv" >> "$CONF"; echo "  -> set $kv"; }; }
cmd_dashboard(){ [ "$(state_get)" = ON ] || { echo "  system is OFF — boot first."; return; }
  local d; d=$(grep '^adapter=' "$CONF"|cut -d= -f2)
  if grep -qE "^\s*$d\s*:\s*display" "$REG"; then
    echo "  dashboard -> display adapter '$d' (Phase D wires it to the live fabric)."
  else echo "  no display adapter registered — console-only; use Status."; fi; }

build_engine || exit 1
[ -f "$STATE" ] || state_set 0
while true; do
  banner
  cat <<'EOF'
  1) Boot      2) Adapters   3) Dashboard   4) Config
  5) Kill all  6) Restart    7) Status      0) Exit
EOF
  echo -n "select> "; read -r c || break
  case "$c" in
    1) cmd_boot;; 2) cmd_adapters;; 3) cmd_dashboard;; 4) cmd_config;;
    5) cmd_shutdown;; 6) cmd_restart;; 7) cmd_status;;
    0|q|exit) echo "bye."; break;; *) echo "  ? unknown option '$c'";;
  esac; echo
done
