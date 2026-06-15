#!/usr/bin/env python3
"""
toolgov.py — Tool-governance check (Tier 5). Governs the tools themselves.

  C23 tool-output-is-generated — a tool may not emit hardware logic as a triple-quoted
                                 C/HDL string literal (a generated tick function, or any
                                 HDL construct). POST/report harness strings exempt
                                 via enforcement_registry.yaml.
  C24 tool-fact-provenance     — a tool may not introduce a hardware constant
                                 (width/rate/range like "18x30","8b10b","600 MHz") that
                                 is neither read from cache nor tagged "curated-constant".

Reference = the cache (cited docs); exemptions = enforcement_registry.yaml only.
Exit 0 = green, 1 = red. Run: python3 toolgov.py [c23|c24|all]
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "cache")
REG = os.path.join(HERE, "enforcement_registry.yaml")

def ok(m):  print(f"[toolgov] OK  {m}"); sys.exit(0)
def red(m): print(f"[toolgov] RED {m}"); sys.exit(1)

def registry():
    if not os.path.exists(REG): return {}
    txt = open(REG).read()
    out = {"c23_exempt": set(), "curated_ok": set()}
    for m in re.finditer(r"c23_output_exempt:\s*\[([^\]]*)\]", txt):
        out["c23_exempt"] |= {x.strip().strip('"\'') for x in m.group(1).split(",") if x.strip()}
    for m in re.finditer(r"curated_constant_ok:\s*\[([^\]]*)\]", txt):
        out["curated_ok"] |= {x.strip().strip('"\'') for x in m.group(1).split(",") if x.strip()}
    return out

def tools():
    return [f for f in os.listdir(HERE) if f.endswith(".py")]

# ---- C23 tool output is generated ---------------------------------------------
def c23_tool_output_generated():
    reg = registry()
    bad = []
    for f in tools():
        if f in reg.get("c23_exempt", set()): continue
        src = open(os.path.join(HERE, f)).read()
        for m in re.finditer(r'"""(.*?)"""', src, re.S):
            body = m.group(1)
            if re.search(r"\bstatic\s+void\s+\w+_tick\b|\bmodule\b|\bendmodule\b|\balways\s*@|\bassign\s+\w", body):
                bad.append(f)
                break
    red(f"C23 tool-output: hand-written hardware-logic string literal in: {sorted(set(bad))}") if bad \
        else ok(f"C23 tool-output — no tool emits hardware logic as a string literal ({len(tools())} tools)")

# ---- C24 tool fact provenance -------------------------------------------------
# hardware-constant shapes: "18x30", "8b10b", "64b66b", "600 MHz", "1.25 Gb/s", ranges.
_CONST = re.compile(r'"(\d+x\d+|\d+b\d+b|\d+(?:\.\d+)?\s?(?:MHz|GHz|Gb/s|Mb/s|ps|ns))"')

def _cache_text():
    blob = []
    if os.path.isdir(CACHE):
        for fn in os.listdir(CACHE):
            if fn.endswith(".jsonl"):
                blob.append(open(os.path.join(CACHE, fn), errors="ignore").read())
    return "\n".join(blob)

def c24_tool_fact_provenance():
    reg = registry()
    cache_text = _cache_text()
    bad = []
    for f in tools():
        src = open(os.path.join(HERE, f)).read()
        curated = "curated-constant" in src or f in reg.get("curated_ok", set())
        for m in _CONST.finditer(src):
            const = m.group(1)
            in_cache = const.replace(" ", "") in cache_text.replace(" ", "")
            if not in_cache and not curated:
                bad.append(f"{f}:{const}")
    red(f"C24 fact-provenance: uncited hardware constants: {sorted(set(bad))[:8]}") if bad \
        else ok("C24 fact-provenance — every hardware constant in tools traces to cache or is curated-tagged")

CHECKS = {"c23": c23_tool_output_generated, "c24": c24_tool_fact_provenance}

def main():
    arg = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
    if arg == "all":
        for name in ("c23", "c24"):
            if os.system(f"{sys.executable} {os.path.abspath(__file__)} {name}") != 0:
                sys.exit(1)
        print("[toolgov] OK  all tool-governance checks passed"); sys.exit(0)
    if arg in CHECKS: CHECKS[arg]()
    else: print("[toolgov] usage: toolgov.py [c23|c24|all]"); sys.exit(2)

if __name__ == "__main__":
    main()
