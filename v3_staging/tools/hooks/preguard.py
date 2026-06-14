#!/usr/bin/env python3
"""
preguard.py — the PreToolUse enforcement guard (harness-invoked, reads the tool call as JSON
on stdin). Exit 0 = allow; exit 2 = DENY (the harness blocks the call). Enforces, with no AI
discretion:
  - Law #1: no Verilog/VHDL/TCL writes.
  - Law #2: no hand-editing generated artifacts (*_gen.h/.c, device/library/container .json).
  - Bulletproof gate: phase-advancing tools denied while device/bulletproof.json is RED.
  - Self-protection: edits to the engine/guards/enforcement files denied unless FOUNDER_OVERRIDE=1.
  - Frozen cache: no edits under cache/; no extract.py without --force.
Founder override: set FOUNDER_OVERRIDE=1 to bypass the self-protection + gate (human root of trust).
"""
import sys, json, os, re
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
def deny(m): print(f"[BLOCKED by preguard] {m}", file=sys.stderr); sys.exit(2)
def allow(): sys.exit(0)
OVERRIDE = os.environ.get("FOUNDER_OVERRIDE") == "1"

try: ev = json.load(sys.stdin)
except Exception: allow()
tool = ev.get("tool_name", ""); ti = ev.get("tool_input", {}) or {}
path = ti.get("file_path") or ti.get("path") or ""
cmd = ti.get("command", "") if tool == "Bash" else ""

# Law #1 — no Verilog/VHDL/TCL
if tool in ("Write", "Edit", "MultiEdit") and re.search(r"\.(v|sv|svh|vhd|vhdl|tcl)$", path, re.I):
    deny("Law #1 — C IS the RTL: no Verilog/VHDL/TCL. Emit C via a generator.")

# Law #2 — no hand-editing generated artifacts
if tool in ("Write", "Edit", "MultiEdit") and re.search(r"_gen\.(h|c)$|/(device|library|container)\.json$|\.net\.json$", path):
    if not OVERRIDE: deny("Law #2 — generated artifact. Edit the GENERATOR tool, not its output.")

# frozen cache
if tool in ("Write", "Edit", "MultiEdit") and re.search(r"/cache/.*\.jsonl$", path):
    if not OVERRIDE: deny("cache is frozen (extraction is one-time). Use extract.py --force if truly re-extracting.")
if tool == "Bash" and re.search(r"extract\.py", cmd) and "--force" not in cmd:
    deny("extract.py without --force on a committed cache — re-extraction is blocked.")

# self-protection — guard the guards
SELF = r"(tools/hooks/|tools/(checks_lib|runner|jobgen)\.py|tools/jobs\.json|settings\.json|hooks/(pre-commit|commit-msg)|install_hooks\.sh)"
if tool in ("Write", "Edit", "MultiEdit") and re.search(SELF, path):
    if not OVERRIDE: deny("enforcement file — set FOUNDER_OVERRIDE=1 to modify the engine/guards (founder root of trust).")

# bulletproof gate — phase-advancing tools denied while RED
PHASE = r"\b(cast|gen_container|route|clkfab|ps_realize|map|unify)\.py\b"
if tool == "Bash" and re.search(PHASE, cmd) and not OVERRIDE:
    bp = os.path.join(ROOT, "device", "bulletproof.json")
    try: green = json.load(open(bp)).get("bulletproof", False)
    except Exception: green = False
    if not green:
        try: nxt = open(os.path.join(ROOT, "device", "next_action.txt")).read().strip()
        except Exception: nxt = "run runner.py"
        deny(f"codebase not BULLETPROOF — phase tools gated. Fix integrity first. Next: {nxt}")

allow()
