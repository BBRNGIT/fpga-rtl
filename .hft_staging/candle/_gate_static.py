#!/usr/bin/env python3
"""Replicates gate.sh's STATIC checks (2b/2c/2d/2e/canon/clock) in Python, since
the sandbox blocks make/cc. Build+thin-test (stage 2 build, clean-room stage 3)
require a compiler and are reported separately as NOT-RUN-IN-SANDBOX."""
import os, re, subprocess, sys

D = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(D, "candle_gen.h")
NET = os.path.join(D, "candle.net.json")
results = []

def add(name, ok, detail=""):
    results.append((name, ok, detail))

# ---- 1) netlist validate ----
r = subprocess.run([sys.executable, os.path.join(D, "validate.py"), NET],
                   capture_output=True, text=True)
add("1  netlist validate (single-writer/no-overlap/no-floating)",
    r.returncode == 0, r.stdout.strip() or r.stderr.strip())

# ---- 2b) gate-level arithmetic: no native +/-/* in tick body ----
def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//.*", "", text)
    return text

src = open(GEN).read()
lines = src.splitlines()
inbody = False
hits = []
# emulate awk: strip comments line-aware across whole file first is close enough
clean = strip_comments(src).splitlines()
for i, line in enumerate(clean, 1):
    if re.search(r"[a-z_]+_tick\(", line):
        inbody = True
        continue
    if inbody:
        code = line.replace("i = i + 1ULL", "")
        code = code.replace(">>", "").replace("<<", "")
        if re.search(r"[A-Za-z0-9_)\]][ \t]*[+*-][ \t]*[A-Za-z0-9_(]", code):
            hits.append(f"{i}: {line.strip()}")
        if re.match(r"^\}", line):
            inbody = False
add("2b gate-level arithmetic (no native +/-/* in tick)",
    not hits, ("hits:\n   " + "\n   ".join(hits)) if hits else "clean")

# ---- 2c) build-sequence: no hand-written cell_*/ _tick in .c/.h (not gen.h/cells.h) ----
bs_hits = []
cell_re = re.compile(r"cell_(buf|not|and|or|xor|mux|eqmask|fa|gate|sar|dff|addsub)\s*\(")
tick_re = re.compile(r"^\s*(static\s+inline\s+)?void\s+[a-z_]+_tick\s*\(")
for fn in os.listdir(D):
    if not (fn.endswith(".c") or fn.endswith(".h")):
        continue
    if fn == "cells.h" or fn.endswith("_gen.h"):
        continue
    for i, line in enumerate(open(os.path.join(D, fn)), 1):
        s = line.strip()
        if s.startswith(("/*", "*", "//")):
            continue
        if cell_re.search(line) or tick_re.search(line):
            bs_hits.append(f"{fn}:{i}: {s}")
# NOTE: selfcheck_ohlc.c legitimately CALLS candle_tick (a testbench), not defines
# device logic. gate.sh's regex only flags *definitions* of _tick and cell_*()
# COMPOSITION. A call site "candle_tick(R);" does not match tick_re (needs 'void')
# nor cell_re. Keep only true violations.
add("2c build-sequence (no hand-written device logic)",
    not bs_hits, ("hits:\n   " + "\n   ".join(bs_hits)) if bs_hits else "clean")

# ---- 2d) logic-content: >0 cell calls in gen.h ----
cell_calls = len(re.findall(r"cell_[a-z_]*\(", src))
cmp_calls = len(re.findall(r"cmp_lt\(", src))
add("2d logic-content (>0 structural cell calls)",
    cell_calls > 0, f"{cell_calls} cell_*() calls + {cmp_calls} cmp_lt() calls")

# ---- 2e) byte-match: regen netlist & gen.h are byte-identical ----
# invoke exactly as the Makefile does: cwd=D, relative paths (so the path baked
# into the gen.h header comment matches the committed artifact).
net_re = subprocess.run([sys.executable, "gen_candle_net.py"],
                        cwd=D, capture_output=True, text=True).stdout
gh_re = subprocess.run([sys.executable, "gennet.py", "candle.net.json"],
                       cwd=D, capture_output=True, text=True).stdout
nm = (net_re == open(NET).read())
gm = (gh_re == src)
add("2e byte-match (emitter->netlist, gennet->gen.h deterministic)",
    nm and gm, f"netlist={'OK' if nm else 'MISMATCH'} gen.h={'OK' if gm else 'MISMATCH'}")

# ---- 2f) cells canon: gen.h only uses canonical cell vocabulary ----
used = set(re.findall(r"cell_([a-z_]+)\(", src))
canon = {"buf","not","and","or","xor","mux","eqmask","fa","gate","dff","addsub"}
extra = used - canon
add("2f cells canon (only canonical cell_* primitives used)",
    not extra, f"used={sorted(used)}" + (f" EXTRA={sorted(extra)}" if extra else ""))

# ---- 2g) clock rule: power-gated self-running loop, no external step token ----
has_run = "candle_run" in src and re.search(r"while \(r\[CANDLE_CANDLE_POWER\] & 1ULL\)", src)
bad_tokens = [t for t in ("replay","source-type","CSV","csv","file") if re.search(rf"\b{t}\b", src)]
add("2g clock rule (power-gated loop; no replay/CSV/file tokens)",
    bool(has_run) and not bad_tokens,
    ("self-running loop OK" if has_run else "NO power loop") +
    (f"; forbidden tokens {bad_tokens}" if bad_tokens else ""))

# ---- report ----
print("=== CANDLE GATE LEDGER (static stages; build/clean-room need a compiler) ===")
allok = True
for name, ok, detail in results:
    allok = allok and ok
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if detail:
        for ln in detail.splitlines():
            print(f"        {ln}")
print()
print("[N/A ] 2  build + thin test (make)     -> NOT RUN: cc/make blocked in sandbox")
print("[N/A ] 3  clean-room build from HEAD    -> NOT RUN: cc/make blocked; also needs commit")
print()
print("OVERALL static stages:", "ALL PASS" if allok else "FAILURES PRESENT")
sys.exit(0 if allok else 1)
