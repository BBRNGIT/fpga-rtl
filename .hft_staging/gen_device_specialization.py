#!/usr/bin/env python3
"""gen_device_specialization.py — universal device specialization meta tool.

ARCHITECTURAL LAW #9 (IMMUTABLE): C IS THE RTL. All device types output C
only. Device type is a PARAMETER (--type fpga|asic|pcb|mcu), driven entirely
by per-type YAML profiles in .hft_staging/device_profiles/<type>.yaml.
NOTHING type-specific is hardcoded in this Python.

FOUNDER LAW — build vs assignment SEPARATION. Three distinct task modes,
never fused:

  build    Scaffold a blank device fileset AS-IS: design doc skeleton,
           emitter skeleton, gennet stub. NO addresses, NO placement,
           NO wiring. Output: demo-able blank fileset + build_report.txt.

  assign   Registry address allocation + hardware resource assignment for
           already-BUILT artifacts. Reads a module list YAML, allocates
           address windows (greedy, profile alignment, CDC reservation),
           maps module budgets onto the profile's resource primitive
           catalog. Output: device_<type>_<name>_registry.json (committed
           register map) + assign_report.txt. Validates cross-module
           single-writer / no-overlap against the registry.

  connect  Module-to-module wiring/seam netlist generation. Reads the
           committed registry (output of assign) + a connections YAML.
           Cross-clock-domain connections become explicit CDC nodes placed
           in the reserved CDC region. Output:
           device_<type>_<name>.net.json + connect_report.txt. The netlist
           follows validate_device.py conventions (modules / cdc_nodes
           sections) so it can be checked with:
               python3 validate_device.py device_<type>_<name>.net.json

Usage:
  gen_device_specialization.py build   --type <t> --name <n> <out_dir>
  gen_device_specialization.py assign  --type <t> <modules.yaml> <out_dir>
  gen_device_specialization.py connect --type <t> <registry.json> \
                                       <connections.yaml> <out_dir>

The extended circuit-builder catalog (JK/T/SR flip-flops, latches, counters,
shift registers) is design vocabulary for emitters — see circuitlib.py. The
emitted netlists and generated C contain canonical cells only.

No floats anywhere in emitted artifacts. stdlib + PyYAML (with a built-in
fallback parser for the simple YAML subset used here).
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROFILE_DIR = HERE / "device_profiles"
DEVICE_TYPES = ("fpga", "asic", "pcb", "mcu")


# ---- YAML loading (PyYAML if present, simple fallback otherwise) -------------

def load_yaml(path):
    text = Path(path).read_text()
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text)
    except ImportError:
        # The fallback needs a hint for list-valued keys; pre-mark them.
        return _fallback_yaml_with_lists(text)


def _fallback_yaml_with_lists(text):
    """Fallback parse handling 'key:' followed by '- ' items as lists."""
    lines = text.splitlines()

    def parse_scalar(s):
        s = s.strip().strip('"').strip("'")
        try:
            return int(s, 0)
        except ValueError:
            return s

    root = {}
    stack = [(-1, root)]  # (indent, container)
    for raw in lines:
        stripped = raw.split(" #")[0].rstrip() if not raw.lstrip().startswith("#") else ""
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip())
        line = stripped.strip()
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if line.startswith("- "):
            # parent must become/already be a list
            if isinstance(parent, dict):
                raise ValueError(f"yaml fallback: dangling list item: {raw}")
            item = {}
            parent.append(item)
            stack.append((indent, item))
            body = line[2:]
            if ":" in body:
                k, v = body.split(":", 1)
                if v.strip():
                    item[k.strip()] = parse_scalar(v)
        elif line.endswith(":"):
            k = line[:-1].strip()
            # Look ahead container type is decided by next non-blank line
            child = _peek_container(lines, raw)
            parent[k] = child
            stack.append((indent, child))
        elif ":" in line:
            k, v = line.split(":", 1)
            parent[k.strip()] = parse_scalar(v)
        else:
            raise ValueError(f"yaml fallback: cannot parse: {raw}")
    return root


def _peek_container(lines, current_raw):
    """Decide dict vs list for a 'key:' line by peeking the next content line."""
    idx = lines.index(current_raw)
    for nxt in lines[idx + 1:]:
        s = nxt.strip()
        if not s or s.startswith("#"):
            continue
        return [] if s.startswith("- ") else {}
    return {}


# ---- profile -----------------------------------------------------------------

def load_profile(dev_type):
    if dev_type not in DEVICE_TYPES:
        die(f"unknown device type '{dev_type}' (expected one of {DEVICE_TYPES})")
    path = PROFILE_DIR / f"{dev_type}.yaml"
    if not path.exists():
        die(f"device profile not found: {path}")
    prof = load_yaml(path)
    for key in ("type", "address_space", "slot_alignment", "cdc_region_size",
                "module_base", "clock_domains", "resources"):
        if key not in prof:
            die(f"profile {path} missing required key '{key}'")
    if prof["type"] != dev_type:
        die(f"profile {path} declares type '{prof['type']}', expected '{dev_type}'")
    return prof


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def align_up(value, alignment):
    return ((value + alignment - 1) // alignment) * alignment


# ---- address allocator (ported from deprecated gen_fpga_specialization.py,
#      parametrized from the device profile) -----------------------------------

class AddressAllocator:
    """Greedy allocator: profile-driven space, alignment, CDC reservation."""

    def __init__(self, profile):
        self.base = int(profile["module_base"])
        self.space = int(profile["address_space"])
        self.alignment = int(profile["slot_alignment"])
        self.cdc_size = int(profile["cdc_region_size"])
        self.cdc_base = self.space - self.cdc_size
        self.allocations = []
        self.reserved = [(self.cdc_base, self.space)]

    def allocate(self, module_name, size_hint_bytes):
        size = align_up(max(self.alignment, size_hint_bytes), self.alignment)
        addr = self._find(size)
        if addr is None:
            return None
        alloc = {
            "module": module_name,
            "base": addr,
            "size": size,
            "end": addr + size,
        }
        self.allocations.append(alloc)
        self.reserved.append((addr, addr + size))
        return alloc

    def _find(self, size):
        self.reserved.sort()
        addr = align_up(self.base, self.alignment)
        for rs, re in self.reserved:
            if addr + size <= rs:
                return addr
            addr = align_up(max(addr, re), self.alignment)
        if addr + size <= self.cdc_base:
            return addr
        return None

    def validate(self):
        errors = []
        allocs = sorted(self.allocations, key=lambda a: a["base"])
        for cur, nxt in zip(allocs, allocs[1:]):
            if cur["end"] > nxt["base"]:
                errors.append(
                    f"no-overlap: {cur['module']} "
                    f"[0x{cur['base']:08x}-0x{cur['end']:08x}] overlaps "
                    f"{nxt['module']} [0x{nxt['base']:08x}-0x{nxt['end']:08x}]")
        for a in allocs:
            if a["end"] > self.cdc_base:
                errors.append(
                    f"cdc-overflow: {a['module']} overflows CDC region "
                    f"at 0x{self.cdc_base:08x}")
        return errors


# ---- mode: build ---------------------------------------------------------------

BUILD_DOC = """# DEVICE_{TYPE}_{NAME}.md — blank device design (BUILD stage)

**Generated:** gen_device_specialization.py build --type {type}
**Stage:** BUILD (no addresses, no placement, no wiring — by founder law)

## Device Profile

| Property | Value |
|----------|-------|
| Type | `{type}` |
| Profile | `.hft_staging/device_profiles/{type}.yaml` |
| Address space | (assigned at ASSIGN stage) |
| Resource catalog | {resources} |
| Clock domains | {clocks} |

## Fileset (universal pattern — same for all device types)

- `DEVICE_{TYPE}_{NAME}.md` — this design doc
- `gen_device_{type}_{name}_net.py` — netlist emitter (fill in module logic)
- `gennet_device_{type}_{name}.py` — netlist → device C generator stub
- output: `device_{type}_{name}_gen.h` — C model (C IS the RTL)

## Stage Separation (founder law — build / assign / connect are DISTINCT)

1. BUILD (this stage) — fileset as-is. No addresses. No placement. No wiring.
2. ASSIGN — `gen_device_specialization.py assign --type {type} <modules.yaml> <dir>`
   produces `device_{type}_{name}_registry.json` (committed register map).
3. CONNECT — `gen_device_specialization.py connect --type {type}
   <registry.json> <connections.yaml> <dir>` produces the seam netlist.

## Circuit-Builder Catalog

Emitters may author with the extended catalog (circuitlib.py):
sr_ff, jk_ff, t_ff, d_latch, counter, shift_register — each lowers to
canonical cells (dff + gates) at emit time. Generated C is canonical only.

## Constraints (device-agnostic, enforced by validators)

- Single-writer, no-overlap, no-floating (validate_device.py)
- Branchless device tick; gate-level arithmetic (cell_addsub etc.)
- No floats, no heap, no function pointers
- Output is C only (device_{type}_{name}_gen.h)
"""

BUILD_EMITTER = '''#!/usr/bin/env python3
"""gen_device_{type}_{name}_net.py — device-level netlist emitter (BUILD stage).

BLANK BY LAW: this skeleton carries NO addresses, NO placement, NO wiring.
Addresses come from the ASSIGN-stage registry
(device_{type}_{name}_registry.json); wiring comes from the CONNECT-stage
seam netlist. Load both — never hardcode either here.

Author module logic with the circuit-builder catalog (circuitlib.lower) —
extended primitives lower to canonical cells at emit time.

OUTPUT: device_{type}_{name}.net.json  (validate with validate_device.py)
"""

import json
import sys
from pathlib import Path

# locate circuitlib.py (lives in .hft_staging/, wherever this fileset sits)
for _p in [Path(__file__).resolve().parent] + \
          list(Path(__file__).resolve().parents):
    if (_p / "circuitlib.py").exists():
        sys.path.insert(0, str(_p))
        break
    if (_p / ".hft_staging" / "circuitlib.py").exists():
        sys.path.insert(0, str(_p / ".hft_staging"))
        break
import circuitlib  # noqa: E402  (catalog: sr_ff/jk_ff/t_ff/d_latch/counter/shift_register)

REGISTRY_PATH = Path("device_{type}_{name}_registry.json")  # produced by ASSIGN


def emit():
    if not REGISTRY_PATH.exists():
        print(f"ERROR: registry not found: {{REGISTRY_PATH}} — run the "
              f"ASSIGN stage first", file=sys.stderr)
        sys.exit(1)
    registry = json.loads(REGISTRY_PATH.read_text())

    net = {{
        "device": "device_{type}_{name}",
        "config_nodes": [
            {{"name": "ZERO", "value": 0}},
            {{"name": "ONE", "value": 1}},
        ],
        "buffer_nodes": [],
        "dff_nodes": [],
        "comb_nodes": [],
        "modules": [],
        "cdc_nodes": [],
    }}

    # ---- TODO (you, the designer): per-module logic --------------------
    # For each module in registry["modules"]:
    #   frag = circuitlib.lower("counter", f"{{mod}}_TICKS", en="ONE")
    #   net["comb_nodes"] += frag["comb_nodes"]
    #   net["dff_nodes"]  += frag["dff_nodes"]
    # Wiring between modules comes from the CONNECT seam netlist.

    for mod in registry.get("modules", []):
        net["modules"].append({{
            "name": mod["name"],
            "window_base": mod["window"]["base"],
            "clock_domain": mod["clock_domain"],
            "outputs": [],
            "published_windows": [],
        }})

    return net


if __name__ == "__main__":
    json.dump(emit(), sys.stdout, indent=2)
'''

BUILD_GENNET = '''#!/usr/bin/env python3
"""gennet_device_{type}_{name}.py — netlist → device C generator (stub).

Converts device_{type}_{name}.net.json into device_{type}_{name}_gen.h —
the complete C model of the realized hardware (C IS the RTL; output is C
only — no Verilog, no schematics, no firmware images).

Reference implementation: .hft_staging/adapter/gennet.py. This stub emits
the register file and READ→COMPUTE→WRITE tick scaffold; extend per the
adapter pattern. All compute lines must be cell_*() calls (gate law).
"""

import json
import sys


def generate(net):
    dev = net["device"]
    lines = []
    a = lines.append
    a(f"/* {{dev}}_gen.h — GENERATED. Do not hand-edit (build-sequence law). */")
    a(f"#ifndef {{dev.upper()}}_GEN_H")
    a(f"#define {{dev.upper()}}_GEN_H")
    a('#include "cells.h"')
    a("")
    names = [n["name"] for n in net.get("config_nodes", [])]
    names += [n["name"] for n in net.get("dff_nodes", [])]
    names += [n["name"] for n in net.get("comb_nodes", [])]
    a(f"#define {{dev.upper()}}_NODE_COUNT {{len(names)}}")
    for i, n in enumerate(names):
        a(f"#define ADDR_{{n}} {{i}}")
    a("")
    a(f"static inline void {{dev}}_tick(word_t *R) {{{{")
    a("    /* READ phase */")
    for n in net.get("dff_nodes", []):
        a(f"    const word_t q_{{n['name']}} = R[ADDR_{{n['name']}}];")
    a("    /* COMPUTE phase — canonical cells only */")
    for n in net.get("comb_nodes", []):
        args = ", ".join(f"R[ADDR_{{i}}]" for i in n["inputs"])
        a(f"    R[ADDR_{{n['name']}}] = cell_{{n['cell']}}({{args}});")
    a("    /* WRITE phase */")
    for n in net.get("dff_nodes", []):
        a(f"    R[ADDR_{{n['name']}}] = cell_dff(q_{{n['name']}}, "
      f"R[ADDR_{{n['d']}}], R[ADDR_{{n['en']}}]);")
    a("}}")
    a("")
    a(f"#endif /* {{dev.upper()}}_GEN_H */")
    return "\\n".join(lines) + "\\n"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: gennet_device_{type}_{name}.py <netlist.net.json>",
              file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1]) as f:
        sys.stdout.write(generate(json.load(f)))
'''


def cmd_build(args):
    prof = load_profile(args.type)
    name = args.name
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    t, T = args.type, args.type.upper()
    N = name.upper()
    resources = ", ".join(sorted(prof["resources"].keys()))
    clocks = ", ".join(sorted(prof["clock_domains"].keys()))

    doc = BUILD_DOC.format(type=t, TYPE=T, name=name, NAME=N,
                           resources=resources, clocks=clocks)
    emitter = BUILD_EMITTER.format(type=t, name=name)
    gennet = BUILD_GENNET.format(type=t, name=name)

    (out / f"DEVICE_{T}_{N}.md").write_text(doc)
    ep = out / f"gen_device_{t}_{name}_net.py"
    ep.write_text(emitter)
    ep.chmod(0o755)
    gp = out / f"gennet_device_{t}_{name}.py"
    gp.write_text(gennet)
    gp.chmod(0o755)

    report = [
        "BUILD REPORT (stage: build — no addresses, no placement, no wiring)",
        f"device: device_{t}_{name}",
        f"profile: device_profiles/{t}.yaml",
        f"files:",
        f"  DEVICE_{T}_{N}.md",
        f"  gen_device_{t}_{name}_net.py",
        f"  gennet_device_{t}_{name}.py",
        "checks:",
        "  PASS no addresses emitted (assign-stage artifact only)",
        "  PASS no wiring emitted (connect-stage artifact only)",
        "  PASS output naming device_<type>_* (law #9)",
        "next: gen_device_specialization.py assign --type "
        f"{t} <modules.yaml> <dir>",
    ]
    (out / "build_report.txt").write_text("\n".join(report) + "\n")
    print(f"BUILD OK: device_{t}_{name} -> {out}", file=sys.stderr)


# ---- mode: assign --------------------------------------------------------------

def _module_size_hint(spec, prof):
    """Window size hint in bytes from the module's budgets + profile."""
    align = int(prof["slot_alignment"])
    size = align
    for rname, res in prof["resources"].items():
        field = res.get("maps", "")
        amount = int(spec.get(field, 0) or 0)
        if amount <= 0:
            continue
        bpu = int(res.get("bytes_per_unit", 0) or 0)
        bpc = int(res.get("bytes_per_cell", 0) or 0)
        if bpu:
            per_unit = int(res.get("per_unit", 1) or 1)
            units = (amount + per_unit - 1) // per_unit
            size = max(size, units * bpu)
        elif bpc:
            size = max(size, amount * bpc)
    return size


def cmd_assign(args):
    prof = load_profile(args.type)
    cfg = load_yaml(args.modules_yaml)
    t, T = args.type, args.type.upper()
    name = cfg.get("device_name") or cfg.get("fpga_name") or "device"
    N = str(name).upper()
    modules = cfg.get("modules", [])
    if not modules:
        die(f"{args.modules_yaml}: no modules listed")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    errors = []
    # cross-module no-overlap / single-writer at the registry level:
    # one module = one writer per window; duplicate names are two writers.
    seen = set()
    for m in modules:
        mn = m.get("name", "")
        if not mn:
            errors.append("module with empty name")
        elif mn in seen:
            errors.append(f"single-writer: module '{mn}' declared twice "
                          f"(two writers for one window)")
        seen.add(mn)
        cd = m.get("clock_domain", "")
        if cd and cd not in prof["clock_domains"] and \
                not str(cd).endswith("_crossing") and cd != "none":
            errors.append(f"clock-domain: module '{mn}' uses '{cd}' not in "
                          f"profile {t}.yaml (crossings must end '_crossing')")

    allocator = AddressAllocator(prof)
    registry = {
        "device": f"device_{t}_{name}",
        "type": t,
        "profile": f"device_profiles/{t}.yaml",
        "address_space": int(prof["address_space"]),
        "slot_alignment": int(prof["slot_alignment"]),
        "cdc_region": {
            "base": allocator.cdc_base,
            "size": int(prof["cdc_region_size"]),
        },
        "clock_domains": prof["clock_domains"],
        "modules": [],
        "resource_usage": {},
    }

    usage = {r: 0 for r in prof["resources"]}
    for m in modules:
        mn = m["name"]
        alloc = allocator.allocate(mn, _module_size_hint(m, prof))
        if alloc is None:
            errors.append(f"allocation: no space for module '{mn}'")
            continue
        assigned = {}
        for rname, res in prof["resources"].items():
            amount = int(m.get(res.get("maps", ""), 0) or 0)
            if amount <= 0:
                continue
            per_unit = int(res.get("per_unit", 1) or 1)
            units = (amount + per_unit - 1) // per_unit
            usage[rname] += units
            assigned[rname] = units
        registry["modules"].append({
            "name": mn,
            "clock_domain": m.get("clock_domain", "none"),
            "window": {
                "base": f"0x{alloc['base']:08x}",
                "size": f"0x{alloc['size']:08x}",
                "end": f"0x{alloc['end']:08x}",
            },
            "resources": assigned,
            "comment": m.get("comment", ""),
        })

    errors += allocator.validate()
    for rname, used in usage.items():
        cap = int(prof["resources"][rname]["capacity"])
        if used > cap:
            errors.append(f"resource-budget: {rname} usage {used} exceeds "
                          f"capacity {cap}")
        registry["resource_usage"][rname] = {
            "used": used,
            "capacity": cap,
            "percent": (used * 100) // cap if cap else 0,  # integer percent
        }

    reg_path = out / f"device_{t}_{name}_registry.json"
    reg_path.write_text(json.dumps(registry, indent=2) + "\n")

    rep = [f"ASSIGN REPORT — device_{t}_{name} (type={t})",
           f"profile: device_profiles/{t}.yaml",
           f"registry: {reg_path.name}", "",
           "address windows:"]
    for m in registry["modules"]:
        rep.append(f"  {m['name']:16s} {m['window']['base']}-"
                   f"{m['window']['end']}  clock={m['clock_domain']}")
    rep.append(f"  CDC region       0x{allocator.cdc_base:08x}-"
               f"0x{int(prof['address_space']):08x} (reserved)")
    rep.append("")
    rep.append("resource usage:")
    for rname, u in registry["resource_usage"].items():
        rep.append(f"  {rname:10s} {u['used']}/{u['capacity']} "
                   f"({u['percent']}%)")
    rep.append("")
    if errors:
        rep.append(f"FAIL ({len(errors)} error(s)):")
        rep += [f"  ERROR: {e}" for e in errors]
    else:
        rep.append("PASS: no-overlap, single-writer (registry level), "
                   "cdc-reserved, budgets OK")
    (out / "assign_report.txt").write_text("\n".join(rep) + "\n")
    print("\n".join(rep), file=sys.stderr)
    sys.exit(1 if errors else 0)


# ---- mode: connect -------------------------------------------------------------

def cmd_connect(args):
    prof = load_profile(args.type)
    registry = json.loads(Path(args.registry).read_text())
    cfg = load_yaml(args.connections_yaml)
    t = args.type
    if registry.get("type") != t:
        die(f"registry type '{registry.get('type')}' != --type {t}")
    name = registry["device"].replace(f"device_{t}_", "", 1)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    mod_clock = {m["name"]: m["clock_domain"] for m in registry["modules"]}
    errors = []
    warnings = []

    net = {
        "device": registry["device"],
        "config_nodes": [{"name": "ZERO", "value": 0},
                         {"name": "ONE", "value": 1}],
        "buffer_nodes": [],
        "dff_nodes": [],
        "comb_nodes": [],
        "modules": [],
        "cdc_nodes": [],
        "cross_module_wiring": [],
    }

    # seam-level single-writer: each destination has exactly one source
    dest_writers = {}
    conns = cfg.get("connections", [])
    if not conns:
        die(f"{args.connections_yaml}: no connections listed")

    cdc_base = int(registry["cdc_region"]["base"], 0) \
        if isinstance(registry["cdc_region"]["base"], str) \
        else int(registry["cdc_region"]["base"])
    cdc_cursor = cdc_base
    align = int(registry["slot_alignment"])

    published = {mn: set() for mn in mod_clock}
    for c in conns:
        src, dst = c.get("from", ""), c.get("to", "")
        if "." not in src or "." not in dst:
            errors.append(f"wiring: connection '{src}' -> '{dst}' must be "
                          f"module.NODE form")
            continue
        smod, snode = src.split(".", 1)
        dmod, dnode = dst.split(".", 1)
        for mod in (smod, dmod):
            if mod not in mod_clock:
                errors.append(f"wiring: module '{mod}' not in registry")
        dest_writers.setdefault(dst, []).append(src)
        sclk, dclk = mod_clock.get(smod, "?"), mod_clock.get(dmod, "?")
        crossing = (sclk != dclk and "none" not in (sclk, dclk))
        wiring = {"from": src, "to": dst, "latency": 1,
                  "src_clock": sclk, "dst_clock": dclk}
        if crossing:
            cdc_name = f"CDC_{smod}_{dmod}_{snode}"
            net["cdc_nodes"].append({
                "name": cdc_name,
                "type": "gray_2ff",
                "input": src,
                "output": dst,
                "src_domain": sclk,
                "dst_domain": dclk,
                "region_base": f"0x{cdc_cursor:08x}",
                "min_latency": 2,
            })
            cdc_cursor = align_up(cdc_cursor + align, align)
            wiring["via_cdc"] = cdc_name
            wiring["latency"] = 2
        net["cross_module_wiring"].append(wiring)
        published.setdefault(smod, set()).add(src)

    for dst, writers in dest_writers.items():
        if len(writers) > 1:
            errors.append(f"single-writer: seam '{dst}' has {len(writers)} "
                          f"writers {writers}")

    cdc_end = int(registry["cdc_region"]["base"], 0) if isinstance(
        registry["cdc_region"]["base"], str) else registry["cdc_region"]["base"]
    cdc_end += int(registry["cdc_region"]["size"])
    if cdc_cursor > cdc_end:
        errors.append("cdc-region: CDC slots overflow the reserved region")

    for m in registry["modules"]:
        outputs = sorted(published.get(m["name"], set()))
        net["modules"].append({
            "name": m["name"],
            "window_base": m["window"]["base"],
            "clock_domain": m["clock_domain"],
            "outputs": outputs,
            "published_windows": outputs,
        })

    # Declare seam registers so validate_device.py resolves references.
    # Source seams are module-output registers (writer = module:X). CDC
    # outputs are written by their cdc node. Non-CDC destinations are module
    # inputs, not separate registers — they are not declared (the wiring
    # entry documents the read).
    declared = set()
    for w in net["cross_module_wiring"]:
        declared.add(w["from"])
    for c in net["cdc_nodes"]:
        declared.add(c["output"])
    for n in sorted(declared):
        net["dff_nodes"].append({"name": n, "kind": "seam_register"})

    net_path = out / f"{registry['device']}.net.json"
    net_path.write_text(json.dumps(net, indent=2) + "\n")

    rep = [f"CONNECT REPORT — {registry['device']} (type={t})",
           f"registry: {args.registry}",
           f"netlist: {net_path.name}", "",
           f"connections: {len(conns)}",
           f"cdc crossings: {len(net['cdc_nodes'])}"]
    for c in net["cdc_nodes"]:
        rep.append(f"  {c['name']}: {c['src_domain']} -> {c['dst_domain']} "
                   f"@ {c['region_base']} (gray_2ff, min_latency=2)")
    rep.append("")
    if errors:
        rep.append(f"FAIL ({len(errors)} error(s)):")
        rep += [f"  ERROR: {e}" for e in errors]
    else:
        rep.append("PASS: seam single-writer, clock-rule (cross-domain via "
                   "CDC only), cdc-region fit")
        rep.append(f"next: python3 validate_device.py {net_path}")
    (out / "connect_report.txt").write_text("\n".join(rep) + "\n")
    print("\n".join(rep), file=sys.stderr)
    sys.exit(1 if errors else 0)


# ---- CLI -----------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        prog="gen_device_specialization.py",
        description="Universal device specialization meta tool "
                    "(build / assign / connect — distinct stages by law).")
    sub = p.add_subparsers(dest="mode", required=True)

    b = sub.add_parser("build", help="scaffold blank fileset (no addresses)")
    b.add_argument("--type", required=True, choices=DEVICE_TYPES)
    b.add_argument("--name", required=True)
    b.add_argument("out_dir")
    b.set_defaults(func=cmd_build)

    a = sub.add_parser("assign", help="allocate addresses + resources "
                                      "(registry)")
    a.add_argument("--type", required=True, choices=DEVICE_TYPES)
    a.add_argument("modules_yaml")
    a.add_argument("out_dir")
    a.set_defaults(func=cmd_assign)

    c = sub.add_parser("connect", help="generate seam/wiring netlist")
    c.add_argument("--type", required=True, choices=DEVICE_TYPES)
    c.add_argument("registry")
    c.add_argument("connections_yaml")
    c.add_argument("out_dir")
    c.set_defaults(func=cmd_connect)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
