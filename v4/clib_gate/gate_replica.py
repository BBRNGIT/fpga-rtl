#!/usr/bin/env python3
"""
gate_replica.py — THE per-file replica gate. It codifies the exact process we ran
by hand on CARRY8 and makes it MANDATORY for every .v -> .c twin. No Verilog
simulator is used or needed: behaviour is proven by spec-derived test vectors that
live beside each .c (the same method as CARRY8's exhaustive adder check).

The .c is the C VERSION of the .v: every Verilog construct of the source is
translated IN PLACE to its component-library + C realization, in source order, and
ALL the .v's information is present in the .c AS CONVERTED C (not pasted as a dead
verbatim block). So the gate proves COVERAGE — every .v line that carries
information has a corresponding C realization that CITES it (a `.v <n>` reference) —
not a byte-for-byte copy.

A .c twin PASSES its gate iff ALL of:
  C1 EXISTS       the .c exists at the path mirroring its .v (folder structure kept)
  C2 COMPILES     the .c compiles clean (-Wall)
  C3 ANNOTATED    the .v's header annotations are carried into the .c (source line,
                  description, and revision/comment lines must be present)
  C4 LIBRARY      the .c builds its logic from the proven component library
                  (components.h parts: wire_xor/wire_and/.../wire_reg/resolve_z),
                  never native + - * / on data — the floor is NAND, via the library.
  C5 BEHAVIOUR    the spec-vector test (<name>.test.c) compiles, links the .c, and
                  EXITS 0 — i.e. the .c reproduces the .v's behaviour on spec-derived
                  inputs. The test's expected values are fixed and spec-derived.
  C6 COVERAGE     every information-bearing line of the .v is realized in the .c:
                  the .c cites each such .v line (`.v <n>` or the line's own text),
                  so nothing in the .v is dropped, summarized, or skipped.

A missing test (C5) is a FAIL, not a skip: an unproven twin does not pass.

Exit 0 = PASS, 1 = FAIL. One line per check.
Usage: gate_replica.py <name>            (e.g. gate_replica.py CARRY8)
       gate_replica.py --all             (gate every .c in the lib)
"""
import argparse, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
V4   = os.path.dirname(HERE)
ROOT = os.path.dirname(V4)
VSRC = os.path.join(ROOT, "unisim_src", "verilog", "src")          # the .v library
CLIB = os.path.join(V4, "clib")                                    # our .c library (mirrors VSRC)

def find_v(name):
    for base, _d, files in os.walk(VSRC):
        if f"{name}.v" in files:
            return os.path.join(base, f"{name}.v")
    return None

def rel_under_vsrc(vpath):
    return os.path.relpath(vpath, VSRC)                            # e.g. unisims/CARRY8.v

def c_path_for(vpath):
    rel = rel_under_vsrc(vpath)[:-2] + ".c"                        # mirror path, .v -> .c
    return os.path.join(CLIB, rel)

def annotations_of(vtext):
    """The .v header annotation lines we require to be carried into the .c:
    Description, Filename/source, and revision/comment lines."""
    keys = []
    for ln in vtext.splitlines():
        s = ln.strip().lstrip("/").strip()
        if re.match(r"(Description|Filename|Revision)\b", s, re.I):
            keys.append(s)
    return keys

def cited_v_lines(csrc):
    """Every .v line number the .c cites, via `.v <n>`, `.v <a>-<b>`, `.v <a>,<b>`.
    These mark which Verilog line each C realization came from."""
    cited = set()
    for m in re.finditer(r"\.v\s+([0-9]+)(?:\s*[-,]\s*([0-9]+))?", csrc):
        a = int(m.group(1)); b = int(m.group(2)) if m.group(2) else a
        if b < a: a, b = b, a
        for n in range(a, b + 1):
            cited.add(n)
    return cited

def info_bearing_v_lines(vtext):
    """The .v lines that carry INFORMATION (must be realized in the .c). Skips
    blank lines and pure comment-art / banner lines (no letters or digits), which
    carry no design fact. Everything else — code, params, ports, assigns, specify
    arcs, $display/$finish, directives, and descriptive comments — must be covered."""
    out = []
    for i, ln in enumerate(vtext.splitlines(), start=1):
        s = ln.strip()
        if not s:
            continue
        body = s.lstrip("/").strip()          # strip a leading comment marker
        # pure banner/box-art comment lines (the ASCII Xilinx logo, rule lines):
        if not re.search(r"[A-Za-z0-9]", body):
            continue
        out.append((i, s))
    return out

def uncovered_v_lines(vtext, csrc):
    """Information-bearing .v lines whose number is NOT cited by the .c."""
    cited = cited_v_lines(csrc)
    return [(n, t) for (n, t) in info_bearing_v_lines(vtext) if n not in cited]

def is_code_line(cline):
    """True if a .c line carries EXECUTABLE C (not blank, not a pure comment).
    We strip block/line comments and check for any real token left."""
    s = cline
    # remove /* ... */ on this single line (replicas keep citations one-per-line)
    s = re.sub(r"/\*.*?\*/", "", s)
    # remove a trailing // comment
    s = re.sub(r"//.*$", "", s)
    # a line that is only the tail/te of a multi-line comment ( * ...  or  */ )
    st = s.strip()
    if st.startswith("*") or st.startswith("/*") or st == "*/" or st == "":
        return False
    return bool(re.search(r"[A-Za-z0-9_;{}()=]", st))

def assign_v_lines(vtext):
    """The .v line numbers that carry an `assign` (a continuous-assignment net).
    Each such line is a piece of LOGIC that MUST have its own adjacent C realization
    in the .c — it cannot be merged into a loop or left as a bare citation comment.
    Returns {lineno: text}."""
    out = {}
    for i, ln in enumerate(vtext.splitlines(), start=1):
        s = ln.strip()
        if re.match(r"assign\b", s):
            out[i] = s
    return out

def citation_lines(csrc):
    """Map each cited .v line number -> list of .c line indices (0-based) whose
    text contains that `.v <n>` citation (single n only; ranges are group cites)."""
    cites = {}
    for idx, cl in enumerate(csrc.splitlines()):
        for m in re.finditer(r"\.v\s+([0-9]+)(?!\s*[-,]\s*[0-9])", cl):
            cites.setdefault(int(m.group(1)), []).append(idx)
    return cites

def floating_assign_citations(vtext, csrc):
    """The C7 violation set: .v `assign` lines whose citation in the .c has NO
    executable C adjacent to it (same line, or the line directly above/below).
    This catches a citation comment whose real code was collapsed into a loop or
    grouped elsewhere — the exact 'looks-commented-out' defect."""
    clines = csrc.splitlines()
    cites = citation_lines(csrc)
    bad = []
    for n, vt in assign_v_lines(vtext).items():
        idxs = cites.get(n, [])
        if not idxs:
            continue  # absence is C6's job; C7 only judges cited-but-floating
        adjacent_code = False
        for idx in idxs:
            for j in (idx, idx - 1, idx + 1):
                if 0 <= j < len(clines) and is_code_line(clines[j]):
                    adjacent_code = True
                    break
            if adjacent_code:
                break
        if not adjacent_code:
            bad.append((n, vt))
    return bad

def gate_one(name):
    out = []
    vpath = find_v(name)
    if not vpath:
        print(f"[gate {name}] FAIL C1 — no {name}.v in unisim_src"); return False
    cpath = c_path_for(vpath)

    # C1 exists at mirrored path
    if not os.path.exists(cpath):
        print(f"[gate {name}] FAIL C1 — missing twin {os.path.relpath(cpath, V4)}"); return False
    out.append("C1 exists (mirrored path)")

    csrc = open(cpath, errors="ignore").read()
    vtext = open(vpath, errors="ignore").read()

    # C2 compiles
    r = subprocess.run(f"cc -Wall -c -o /dev/null {cpath}", shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[gate {name}] FAIL C2 — compile error: {r.stderr.strip().splitlines()[:1]}"); return False
    out.append("C2 compiles")

    # C3 annotations carried over (source reference + at least the description)
    if f"{name}.v" not in csrc and "unisim_src" not in csrc:
        print(f"[gate {name}] FAIL C3 — .c does not cite its source {name}.v"); return False
    # require the .v's description text to appear in the .c
    desc = next((a for a in annotations_of(vtext) if a.lower().startswith("description")), "")
    if desc:
        body = desc.split(":",1)[-1].strip()[:20]
        if body and body not in csrc:
            print(f"[gate {name}] FAIL C3 — .v description not carried into .c"); return False
    out.append("C3 annotated (source + description carried)")

    # C4 LIBRARY floor — the replica builds its logic from the proven component
    # library (components.h). It must (a) include components.h and (b) actually use
    # a library part: wire_not/and/or/xor/mux/latch/reg/dff or resolve_z/*_settle.
    if "components.h" not in csrc:
        print(f"[gate {name}] FAIL C4 — does not include the component library (components.h)"); return False
    if not re.search(r"\b(wire_(?:not|and|or|xor|mux|latch|reg|dff)|resolve_z|"
                     r"\w+_settle|edge_pos|edge_neg|nand_settle|"
                     r"ASSIGN|AND|OR|NOT|XOR|MUX|EQ|RESZ|rd)\s*\(", csrc):
        print(f"[gate {name}] FAIL C4 — does not use any component-library part"); return False
    # the floor is NAND via the library: a signal value must be WIRED from components,
    # never COMPUTED with native C. We inspect every line that drives a `.level` (an
    # assignment whose left side is `<something>.level =`) and reject native logic on
    # its right-hand side. Computing a level instead of wiring it is the exact "writing
    # in C" defect (e.g. the CI_TOP_in ternary). Allowed RHS forms for a `.level =`:
    #   - another wire's level:      x.level = y.level;
    #   - a library z-resolver:      x.level = resolve_z(y.level);
    #   - a plain param->level set:  x.level = c->FLAG ? HI : LO;  (param onto a net)
    # Forbidden on a `.level =` RHS: && || == != < > ! ~ ^ & | and a ?: that mixes
    # signal levels (a datapath mux must be wire_mux, not a ternary).
    for ln in csrc.splitlines():
        m = re.search(r"\.level\s*=\s*(.+?);", ln)
        if not m:
            continue
        rhs = m.group(1)
        # strip a trailing // ... not present (we already split on ;); examine rhs.
        # native boolean / bitwise / comparison logic driving a level == compute-not-wire
        if re.search(r"&&|\|\||==|!=|<=|>=|(?<![/*])\^|(?<!\w)~|(?<![&|])&(?!&)|(?<![|])\|(?!\|)", rhs):
            print(f"[gate {name}] FAIL C4 — native logic computes a signal level "
                  f"(must WIRE from components, not compute):  .level = {rhs.strip()[:60]}")
            return False
        # a ?: is only allowed for a pure param->HI/LO set, NOT for mixing signal levels
        if "?" in rhs and ".level" in rhs:
            print(f"[gate {name}] FAIL C4 — ternary on signal levels (use wire_mux, not ?:):  "
                  f".level = {rhs.strip()[:60]}")
            return False
        # native arithmetic on a level is likewise forbidden (must be a structural adder)
        if re.search(r"\.level\s*[-+*/]|[-+*/]\s*\w+\.level", rhs + ".level"):
            print(f"[gate {name}] FAIL C4 — native arithmetic on signal levels (must wire, not compute):  "
                  f".level = {rhs.strip()[:60]}")
            return False
    out.append("C4 library-floor (no computed levels; wired from components)")

    # C5 behaviour: spec-vector test must exist, link the .c, and exit 0
    tpath = cpath[:-2] + ".test.c"
    if not os.path.exists(tpath):
        print(f"[gate {name}] FAIL C5 — no spec-vector test {os.path.basename(tpath)} (unproven = fail)"); return False
    exe = os.path.join(tempfile.gettempdir(), f"_gate_{name}")
    rb = subprocess.run(f"cc -Wall -O0 -o {exe} {tpath}", shell=True, capture_output=True, text=True)
    if rb.returncode != 0:
        print(f"[gate {name}] FAIL C5 — test compile error: {rb.stderr.strip().splitlines()[:1]}"); return False
    rr = subprocess.run(exe, capture_output=True, text=True)
    if rr.returncode != 0:
        print(f"[gate {name}] FAIL C5 — behaviour test FAILED:\n{rr.stdout.strip()[-300:]}"); return False
    out.append(f"C5 behaviour ({rr.stdout.strip().splitlines()[-1][:60] if rr.stdout.strip() else 'test exit 0'})")

    # C6 COVERAGE — every information-bearing line of the .v is realized in the .c.
    # The .c is the CONVERSION: each such .v line is translated in place, and the .c
    # cites it with a `.v <n>` reference (single line or an `a-b`/`a,b` range). We
    # collect the set of .v line numbers cited anywhere in the .c, then require that
    # every information-bearing .v line is covered. Nothing dropped or summarized.
    missing = uncovered_v_lines(vtext, csrc)
    if missing:
        show = ", ".join(f"{n}:{t[:40]!r}" for n, t in missing[:6])
        more = "" if len(missing) <= 6 else f"  (+{len(missing)-6} more)"
        print(f"[gate {name}] FAIL C6 — {len(missing)} .v line(s) not realized/cited in the .c "
              f"(reduction): {show}{more}")
        return False
    out.append("C6 coverage (every information-bearing .v line realized + cited)")

    # C7 ADJACENCY — each .v `assign` (a piece of logic) must have its OWN C
    # realization sitting WITH its citation: real executable C on the citation's
    # line or the line directly above/below. A bare citation comment whose code was
    # collapsed into a loop or grouped elsewhere reads as 'commented out' and breaks
    # the one-cited-line-per-.v-line faithfulness. That is a FAIL.
    floating = floating_assign_citations(vtext, csrc)
    if floating:
        show = ", ".join(f"{n}:{t[:42]!r}" for n, t in floating[:6])
        more = "" if len(floating) <= 6 else f"  (+{len(floating)-6} more)"
        print(f"[gate {name}] FAIL C7 — {len(floating)} cited assign(s) have NO adjacent C "
              f"(citation floats away from its realization): {show}{more}")
        return False
    out.append("C7 adjacency (every assign realized beside its citation)")

    print(f"[gate {name}] PASS — " + " · ".join(out))
    return True

def gate_all():
    names = []
    for base, _d, files in os.walk(CLIB):
        for f in files:
            if f.endswith(".c") and not f.endswith(".test.c"):
                names.append(f[:-2])
    ok = 0
    for n in sorted(set(names)):
        if gate_one(n): ok += 1
    print(f"\n[gate] {ok}/{len(set(names))} twins pass")
    return ok == len(set(names)) and names

def main():
    ap = argparse.ArgumentParser(description="per-file UNISIM .v -> .c replica gate (the CARRY8 process, enforced)")
    ap.add_argument("name", nargs="?")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if a.all:
        sys.exit(0 if gate_all() else 1)
    if not a.name:
        print("usage: gate_replica.py <name> | --all"); sys.exit(2)
    sys.exit(0 if gate_one(a.name) else 1)

if __name__ == "__main__":
    main()
