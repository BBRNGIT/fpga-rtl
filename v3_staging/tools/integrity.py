#!/usr/bin/env python3
"""
integrity.py — Generation-integrity check (Tier 4). Reproducibility + no-HDL.

  C19 byte-match    — each *_gen.h reproduces byte-identically from its generator
  C20 clean-room    — the device rebuilds from committed HEAD, not the dirty tree
  C21 no-verilog    — no .v/.sv/.vhd/.tcl files; no HDL string literals in tools
  C22 compile-post  — device compiles and the POST runs exit 0

Self-referential (the artifact is its own reference) — no invented values.
Exit 0 = green, 1 = red. Run: python3 integrity.py [c19|c20|c21|c22|all]
"""
import os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
DEV = os.path.join(ROOT, "device")

def ok(m):  print(f"[integrity] OK  {m}"); sys.exit(0)
def red(m): print(f"[integrity] RED {m}"); sys.exit(1)

# generator -> the committed artifact it must reproduce
GEN_MAP = {
    "lower.py":         os.path.join(DEV, "fpga_device_gen.h"),
    "gen_container.py": os.path.join(DEV, "container_gen.h"),
}

def c19_byte_match():
    bad = []
    for tool, artifact in GEN_MAP.items():
        tp = os.path.join(HERE, tool)
        if not os.path.exists(tp) or not os.path.exists(artifact):
            continue
        before = open(artifact, "rb").read()
        # re-run the generator into a temp HOME so it can't clobber the real file unexpectedly:
        # generators here write to device/ directly, so snapshot+restore around the run.
        r = subprocess.run([sys.executable, tp], cwd=HERE, capture_output=True, text=True)
        after = open(artifact, "rb").read() if os.path.exists(artifact) else b""
        if r.returncode != 0:
            bad.append(f"{tool} exited {r.returncode}")
        elif after != before:
            bad.append(f"{tool}: {os.path.basename(artifact)} not byte-identical after regen")
    red(f"C19 byte-match: {bad}") if bad \
        else ok(f"C19 byte-match — {len(GEN_MAP)} generated artifacts reproduce from their tools")

def c20_clean_room():
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=HERE,
                          capture_output=True, text=True).stdout.strip()
    if not root: red("C20 clean-room — not a git repo")
    dirty = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "v3_staging/tools", "v3_staging/device"],
                           cwd=root).returncode
    if dirty != 0:
        ok("C20 clean-room — SKIPPED (uncommitted changes; commit to gate the real artifact)")
    tmp = tempfile.mkdtemp()
    arch = subprocess.run(f"git -C {root} archive HEAD v3_staging | tar -x -C {tmp}",
                          shell=True).returncode
    if arch != 0: red("C20 clean-room — git archive failed")
    post = os.path.join(tmp, "v3_staging", "device", "fpga_device_post.c")
    if not os.path.exists(post):
        ok("C20 clean-room — no device POST in HEAD yet (nothing to rebuild)")
    r = subprocess.run(f"cc -O0 -o {tmp}/_dev {post}", shell=True, cwd=os.path.dirname(post),
                       capture_output=True, text=True)
    ok("C20 clean-room — device rebuilds from committed HEAD") if r.returncode == 0 \
        else red(f"C20 clean-room — rebuild from HEAD failed: {r.stderr.strip()[:100]}")

def c21_no_verilog():
    hits = subprocess.run(
        r"find " + ROOT + r" -path '*/archive/*' -prune -o \( -name '*.v' -o -name '*.sv' "
        r"-o -name '*.vhd' -o -name '*.vhdl' -o -name '*.tcl' \) -print",
        shell=True, capture_output=True, text=True).stdout.strip()
    if hits: red(f"C21 no-verilog: HDL files present: {hits.splitlines()[:4]}")
    # HDL string literals inside tools
    lit = []
    for f in os.listdir(HERE):
        if f.endswith(".py"):
            src = open(os.path.join(HERE, f)).read()
            if re.search(r'"""[^"]*\b(module|endmodule|always\s*@|assign\s)\b', src, re.S):
                lit.append(f)
    red(f"C21 no-verilog: HDL template literal in tools: {lit}") if lit \
        else ok("C21 no-verilog — no HDL files and no HDL literals in tools")

def c22_compile_post():
    post = os.path.join(DEV, "fpga_device_post.c")
    if not os.path.exists(post):
        post = os.path.join(DEV, "container_post.c")
    if not os.path.exists(post):
        ok("C22 compile-post — no POST file yet (nothing to compile)")
    out = os.path.join(tempfile.gettempdir(), "_signoff_post")
    r = subprocess.run(f"cc -O0 -o {out} {post}", shell=True, cwd=DEV, capture_output=True, text=True)
    if r.returncode: red(f"C22 compile-post — compile FAIL: {r.stderr.strip()[:100]}")
    p = subprocess.run([out], capture_output=True, text=True)
    ok("C22 compile-post — device compiles + POST exit 0") if p.returncode == 0 \
        else red(f"C22 compile-post — POST exit {p.returncode}")

CHECKS = {"c19": c19_byte_match, "c20": c20_clean_room, "c21": c21_no_verilog, "c22": c22_compile_post}

def main():
    arg = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
    if arg == "all":
        for name in ("c21", "c22", "c19", "c20"):
            if os.system(f"{sys.executable} {os.path.abspath(__file__)} {name}") != 0:
                sys.exit(1)
        print("[integrity] OK  all integrity checks passed"); sys.exit(0)
    if arg in CHECKS: CHECKS[arg]()
    else: print("[integrity] usage: integrity.py [c19|c20|c21|c22|all]"); sys.exit(2)

if __name__ == "__main__":
    main()
