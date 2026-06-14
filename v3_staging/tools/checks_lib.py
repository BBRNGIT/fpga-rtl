#!/usr/bin/env python3
"""
checks_lib.py — the invariant checks the integrity jobs call. Each named check prints a
one-line message and exits 0 (green) or 1 (red). Side-effect-free (read-only). runner.py
invokes these via `python3 checks_lib.py <name>`. Add an invariant = add a function + a
jobs.json entry (via jobgen.py).
"""
import sys, os, json, glob, subprocess, re
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
def L(p):
    for base in (HERE, os.path.join(ROOT, "device"), ROOT):   # data in tools/, generated in device/
        fp = os.path.join(base, p)
        if os.path.exists(fp): return json.load(open(fp))
    raise FileNotFoundError(p)
def ok(m): print(m); sys.exit(0)
def red(m): print(m); sys.exit(1)
def sh(c): return subprocess.run(c, shell=True, cwd=ROOT, capture_output=True, text=True)

def configmap_subset_catalog():
    cat = set(L("catalog.json")); cm = L("configmap.json")
    members = {m for d in cm.values() for m in d.get("members", [])}
    extra = members - cat
    red(f"{len(extra)} configmap members not in catalog: {sorted(extra)[:5]}") if extra else ok(f"all {len(members)} configmap members ⊆ catalog")

def no_orphan_primitives():
    # bidirectional: configmap.json leaf elements <-> configmap-owned primitives in library.json.
    # configmap.py injects each leaf physical element into primitives.json (-> library.json),
    # marked "see configmap.json". Tier-0 atomic axioms (no marker) and PS leaves owned by
    # ps_realize.py ("see ps_ports.json") are out of scope. Orphans = either direction's gap.
    cm = L("configmap.json")
    leaf = {el for el, d in cm.items() if d.get("kind") == "leaf"}
    prims = L("library.json").get("primitives", {})
    owned = {k for k, v in prims.items()
             if isinstance(v, dict) and "see configmap.json" in str(v.get("_note", ""))}
    orphans = owned - leaf            # in library, no configmap leaf element (stale dead weight)
    missing = leaf - owned            # configmap leaf element, no library primitive (not emitted)
    if orphans or missing:
        red(f"orphan primitives: {len(orphans)} stale in library {sorted(orphans)[:5]}, "
            f"{len(missing)} configmap leaves missing from library {sorted(missing)[:5]}")
    ok(f"0 orphans — all {len(leaf)} configmap leaf elements ⇄ library primitives (bidirectional)")

def zero_unmapped():
    bad = [k for k in (list(L("configmap.json")) ) if "_unmapped" in k]
    h = L("hierarchy.json")
    bad += [n["id"] for n in h["nodes"] if "_unmapped" in n["id"]]
    red(f"{len(bad)} _unmapped nodes present") if bad else ok("0 _unmapped nodes")

def no_verilog():
    hits = sh(r"find . -path ./archive -prune -o \( -name '*.v' -o -name '*.sv' -o -name '*.vhd' -o -name '*.tcl' \) -print").stdout.strip()
    red(f"Verilog/TCL files present: {hits[:120]}") if hits else ok("no Verilog/VHDL/TCL in tree (Law #1)")

def container_compiles():
    dev = os.path.join(HERE, "container_post.c") if os.path.exists(os.path.join(HERE, "container_post.c")) else os.path.join(ROOT, "device", "container_post.c")
    if not os.path.exists(dev): red("container_post.c missing")
    r = subprocess.run(f"cc -O0 -o /tmp/_bp_post {dev}", shell=True, cwd=os.path.dirname(dev), capture_output=True, text=True)
    if r.returncode: red(f"container compile FAIL: {r.stderr.strip()[:100]}")
    p = subprocess.run("/tmp/_bp_post", capture_output=True, text=True)
    ok("container compiles + POST exit 0") if p.returncode == 0 else red(f"POST exit {p.returncode}")

def counts_match_ds891():
    cont = L("container.json"); inv = next(iter(L("ds_resources.json").values()))
    want = {"storage_element": "CLB Flip-Flops", "LUT6": "CLB LUTs", "DSP48E2": "DSP Slices"}
    cm = {e["name"]: e["count"] for e in cont["elements"]}
    bad = []
    for el, k in want.items():
        ds = int(str(inv.get(k, "")).replace(",", "") or 0)
        if cm.get(el) != ds: bad.append(f"{el}:{cm.get(el)}≠{ds}")
    red(f"count mismatch vs DS891: {bad}") if bad else ok("element counts == DS891 (FF/LUT/DSP)")

def device_tree_consistent():
    h = L("hierarchy.json"); nodes = len(h["nodes"])
    dt = len(glob.glob(os.path.join(ROOT, "device_tree", "**", "node.json"), recursive=True))
    red(f"device_tree {dt} node.json ≠ hierarchy {nodes} nodes") if dt and dt != nodes else ok(f"device_tree == hierarchy ({dt} nodes)")

def zero_untracked():
    # sh() runs at cwd=ROOT (v3_staging) -> paths are RELATIVE to it ("tools device"), NOT
    # "v3_staging/tools" (which would resolve to v3_staging/v3_staging/ and silently match nothing).
    out = sh("git status --porcelain tools device 2>/dev/null").stdout.strip()
    n = len([l for l in out.splitlines() if l.startswith("??")])
    red(f"{n} untracked files in tools/device") if n else ok("0 untracked tool/device files")

def all_committed():
    out = sh("git status --porcelain tools device 2>/dev/null").stdout.strip()
    red(f"{len(out.splitlines())} uncommitted changes") if out else ok("working tree clean (tools/device)")

def clean_layout():
    stray = [f for f in ("container_gen.h", "container_post.c", "library.json", "container.json")
             if os.path.exists(os.path.join(HERE, f))]
    red(f"generated artifacts in tools/: {stray}") if stray else ok("tools/ has no generated artifacts")

def library_validates():
    r = subprocess.run("python3 netc.py", shell=True, cwd=HERE, capture_output=True, text=True)
    ok("library passes netc") if r.returncode == 0 and "OK" in r.stdout else red(f"netc fail: {r.stdout.strip()[-80:]}")

def no_ai_attribution():
    out = sh("git log -30 --format=%s%n%b").stdout
    red("AI attribution found in recent log") if re.search(r'co-authored-by|anthropic|claude|copilot', out, re.I) else ok("no AI attribution in recent commits")

CHECKS = {k: v for k, v in globals().items() if callable(v) and not k.startswith(("L", "ok", "red", "sh"))}
if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if name in CHECKS:
        try: CHECKS[name]()
        except SystemExit: raise
        except Exception as e: red(f"{name} errored: {e}")
    else:
        print("checks:", ", ".join(sorted(CHECKS))); sys.exit(2)
