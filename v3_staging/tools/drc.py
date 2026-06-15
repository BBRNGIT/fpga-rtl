#!/usr/bin/env python3
"""
drc.py — Design-Rule Check (Tier 2). Structural-only gates over device/device.json
and emitted *_gen.h. No invented reference values.

  C08 branchless-datapath  — no if/?:/switch/for/while, no native + - * / % in any _tick
  C09 combinational-loop    — no comb cycle unbroken by a flip-flop
  C12 self-running-clock    — clock tick reads no injected step input
  C14 logic-content         — every generated block has >=1 real cell_* call
  C15 analog-boundary       — analog primitives appear only as boundary cells, not gate-decomposed

Exit 0 = green, 1 = red. Read-only. Run: python3 drc.py [c08|c09|c12|c14|c15|all]
"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
DEV = os.path.join(ROOT, "device")

def ok(m):  print(f"[drc] OK  {m}"); sys.exit(0)
def red(m): print(f"[drc] RED {m}"); sys.exit(1)

def load(name):
    for base in (DEV, HERE):
        p = os.path.join(base, name)
        if os.path.exists(p): return json.load(open(p))
    raise FileNotFoundError(name)

def gen_headers():
    return [os.path.join(DEV, f) for f in os.listdir(DEV) if f.endswith("_gen.h")] if os.path.isdir(DEV) else []

# ---- C08 branchless datapath --------------------------------------------------
def _strip_comments(src):
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"//[^\n]*", "", src)
    return src

def _tick_bodies(src):
    """Yield the body text of each *_tick(...) function."""
    bodies = []
    for m in re.finditer(r"[A-Za-z_]\w*_tick\s*\([^)]*\)\s*\{", src):
        i = m.end() - 1
        depth = 0
        for j in range(i, len(src)):
            if src[j] == "{": depth += 1
            elif src[j] == "}":
                depth -= 1
                if depth == 0:
                    bodies.append(src[i+1:j]); break
    return bodies

def c08_branchless():
    bad = []
    for h in gen_headers():
        src = _strip_comments(open(h).read())
        for body in _tick_bodies(src):
            b = re.sub(r">>|<<", "", body)                       # shifts allowed
            b = re.sub(r"\bi\s*=\s*i\s*\+\s*1ULL", "", b)        # loop step (if any)
            if re.search(r"\b(if|switch|while|for)\b|\?", b):
                bad.append(f"{os.path.basename(h)}: branch in tick")
            if re.search(r"[A-Za-z0-9_)\]]\s*[+*/%-]\s*[A-Za-z0-9_(]", b):
                bad.append(f"{os.path.basename(h)}: native arithmetic in tick")
    red(f"C08 branchless: {sorted(set(bad))}") if bad \
        else ok(f"C08 branchless — no branches/native arithmetic in any tick ({len(gen_headers())} headers)")

# ---- C09 combinational loop ---------------------------------------------------
def c09_comb_loop():
    dev = load("device.json"); prims = dev.get("primitives", {}); blocks = dev.get("blocks", {})
    seq = {"dff_d", "latch_d", "dff", "latch", "cfgcell"}      # state-holding types break loops
    bad = []
    for bname, blk in blocks.items():
        # build net dependency among combinational insts only
        producers = {}                       # net -> ref (driver)
        deps = {}                            # ref -> set(input nets)
        is_seq = {}
        for inst in blk.get("insts", []):
            ref, itype = inst.get("ref"), inst.get("type")
            is_seq[ref] = itype in seq
            outs = prims.get(itype, {}).get("out", [])
            for pin, net in (inst.get("conn") or {}).items():
                if pin in outs: producers[net] = ref
                else: deps.setdefault(ref, set()).add(net)
        # DFS for a cycle through combinational refs only
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {}
        def visit(ref):
            if is_seq.get(ref): return False
            color[ref] = GRAY
            for net in deps.get(ref, ()):
                drv = producers.get(net)
                if drv is None or is_seq.get(drv): continue
                c = color.get(drv, WHITE)
                if c == GRAY: return True
                if c == WHITE and visit(drv): return True
            color[ref] = BLACK
            return False
        for inst in blk.get("insts", []):
            r = inst.get("ref")
            if color.get(r, WHITE) == WHITE and not is_seq.get(r):
                if visit(r): bad.append(f"{bname}:{r}"); break
    red(f"C09 combinational loops: {bad[:6]}") if bad \
        else ok(f"C09 comb-loop — no unbroken combinational cycles in {len(blocks)} blocks")

# ---- C14 logic content --------------------------------------------------------
def _logic_content_exempt():
    """Headers exempt from the >=1 cell_* rule — ONLY from the closed registry
    (enforcement_registry.yaml). No inline exemption: a tool cannot exempt its
    own output. Each entry carries a reason in the registry."""
    reg = os.path.join(HERE, "enforcement_registry.yaml")
    if not os.path.exists(reg): return set()
    txt = open(reg).read()
    m = re.search(r"logic_content_exempt:\s*\[([^\]]*)\]", txt)
    if not m: return set()
    return {x.strip().strip('"\'') for x in m.group(1).split(",") if x.strip()}

def c14_logic_content():
    exempt = _logic_content_exempt()
    bad = []
    for h in gen_headers():
        base = os.path.basename(h)
        if base in exempt: continue
        src = open(h).read()
        if len(re.findall(r"\bcell_[a-z_]+\s*\(", src)) == 0:
            bad.append(base)
    red(f"C14 logic-content: headers with zero cell_* calls: {bad}") if bad \
        else ok(f"C14 logic-content — every non-exempt generated header has >=1 cell_* call")

# ---- C12 self-running clock ---------------------------------------------------
def c12_self_running_clock():
    # structural: a *_tick takes no argument (self-running); an injected step would be a parameter.
    bad = []
    for h in gen_headers():
        src = _strip_comments(open(h).read())
        for m in re.finditer(r"([A-Za-z_]\w*_tick)\s*\(([^)]*)\)", src):
            args = m.group(2).strip()
            if args and args != "void":
                bad.append(f"{os.path.basename(h)}:{m.group(1)}({args})")
    red(f"C12 self-running-clock: ticks take external input: {bad[:6]}") if bad \
        else ok("C12 self-running-clock — all ticks are argument-free (no injected step)")

# ---- C15 analog boundary ------------------------------------------------------
def c15_analog_boundary():
    lib = load("library.json")
    prims = lib.get("primitives", {}); blocks = lib.get("blocks", {})
    analog = {k for k, v in prims.items() if isinstance(v, dict) and v.get("analog")}
    if not analog:
        ok("C15 analog-boundary — no analog primitives declared (nothing to gate)")
    bad = []
    # an analog primitive must NOT itself be decomposed into a gate netlist (no cells[])
    for name in analog:
        if name in blocks and (blocks[name].get("cells") or blocks[name].get("insts")):
            bad.append(f"{name} gate-decomposed")
    red(f"C15 analog-boundary: {bad}") if bad \
        else ok(f"C15 analog-boundary — {len(analog)} analog prims kept as boundary cells, not decomposed")

CHECKS = {"c08": c08_branchless, "c09": c09_comb_loop, "c12": c12_self_running_clock,
          "c14": c14_logic_content, "c15": c15_analog_boundary}

def main():
    arg = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
    if arg == "all":
        for name in ("c08", "c14", "c09", "c12", "c15"):
            if os.system(f"{sys.executable} {os.path.abspath(__file__)} {name}") != 0:
                sys.exit(1)
        print("[drc] OK  all DRC checks passed"); sys.exit(0)
    if arg in CHECKS: CHECKS[arg]()
    else: print("[drc] usage: drc.py [c08|c09|c12|c14|c15|all]"); sys.exit(2)

if __name__ == "__main__":
    main()
