#!/usr/bin/env python3
"""gen_module_net.py — GENERIC module-netlist EMITTER (meta-tool).

Phase-2 rebuild-path tool. Consumes ANY ``<module>_logic.yaml`` and emits a
complete ``<module>.net.json`` in the schema the generator (gennet.py) consumes
— INCLUDING comb_nodes and wiring (the precise thing the WAVE-1 emitters
omitted, which produced stub device C).

Usage:
    python3 gen_module_net.py <module>_logic.yaml > <module>.net.json

This is a TOOL. It is hand-written Python. Its OUTPUT (the .net.json) is the
hardware artifact and is NEVER hand-edited — it is produced by running this
tool. Likewise gennet.py turns the netlist into the device C.

Input YAML schema (see candle_logic.yaml for a worked example):
    module          : str   (device name)
    kind            : str
    window_base     : hex string (optional, default "0x00000000")
    clock           : {power: <const/dff name>}              (optional)
    seam_inputs     : [{name,type,source,comment}]           -> config_nodes
    const_nodes     : [{name,type,value,comment}]            -> const_nodes
    dff_nodes       : [{name,type,fed_by,enable,comment}]    -> dff_nodes
    history_ring    : {name,depth,index,write_enable,fields:[{name,source}]}
    comb_nodes      : [{name,cell,inputs,invert,sub,shift_right,comment}]
    wiring          : {signal: [consumers]}                  (doc, copied through)
    seam_outputs    : [{name,source,type,comment}]           -> seam_nodes

Emitted netlist schema (consumed by gennet.py):
    device, window_base, kind, comment
    config_nodes      (seam inputs — read-only published lanes)
    const_nodes       (reset-latched constants, incl. clock power bit)
    dff_nodes         (registered state; each carries fed_by + optional enable)
    comb_nodes        (combinational cell chain — the actual RTL logic)
    history_ring      (ring snapshot, depth power-of-two)
    seam_nodes        (relay outputs)
    wiring            (traceability map)
    clock             (power bit)

The emitter performs structural validation BEFORE emitting so that a malformed
spec fails here (loudly) rather than silently producing a stub:
  * every comb_node cell is a recognised primitive
  * every comb_node input resolves to a known node (config/const/dff/comb)
  * every dff.fed_by resolves to a comb_node, a dff, or an input/const
  * every dff.enable (if present) resolves to a known node
  * history_ring.depth is a power of two; every ring field source resolves
  * there is at least one comb_node (otherwise the device would be a stub)
"""
import json
import re
import sys

try:
    import yaml
except ImportError:
    sys.stderr.write("gen_module_net: PyYAML required (pip install pyyaml)\n")
    sys.exit(2)

# --- per-index unrolling -----------------------------------------------------
# A price-indexed projection (Index Doctrine) declares lane-templated nodes with
# an `_i` suffix and `unroll: true` (uses the spec-level `width`) or `unroll: N`.
# Each is expanded into concrete lanes 0..n-1 with `_i` -> `_<k>` everywhere it
# appears as an identifier suffix (word-boundary, so `_idx`/`_inc` are untouched).
# Templated nodes must be listed in dependency order; expansion preserves it
# (all of lane-group A, then all of lane-group B) so B_k still follows A_k.
_IRE = re.compile(r"_i\b")


def _sub_i(s, k):
    return _IRE.sub(f"_{k}", s) if isinstance(s, str) else s


def expand_unroll(items, width):
    out = []
    for it in items or []:
        u = it.get("unroll")
        if u in (None, False):
            out.append(it)
            continue
        n = width if u is True else int(u)
        if not n or n <= 0:
            sys.stderr.write(f"gen_module_net: node {it.get('name')} unroll needs a positive width\n")
            sys.exit(2)
        for k in range(n):
            c = dict(it)
            c.pop("unroll", None)
            if "name" in c:
                c["name"] = _sub_i(c["name"], k)
            if isinstance(c.get("inputs"), list):
                c["inputs"] = [_sub_i(x, k) for x in c["inputs"]]
            for fld in ("fed_by", "enable", "source"):
                if c.get(fld) is not None:
                    c[fld] = _sub_i(c[fld], k)
            out.append(c)
    return out

KNOWN_CELLS = {"buf", "not", "and", "or", "xor", "mux", "eqmask", "addsub", "cmp_lt"}
# arg counts per cell (None = variadic/unary handled specially)
CELL_ARITY = {
    "buf": 1, "not": 1,
    "and": 2, "or": 2, "xor": 2, "eqmask": 2, "cmp_lt": 2,
    "mux": 3,
    "addsub": 2,
}


def die(msg):
    sys.stderr.write("gen_module_net: " + msg + "\n")
    sys.exit(2)


def main():
    if len(sys.argv) < 2:
        die("usage: gen_module_net.py <module>_logic.yaml > <module>.net.json")
    with open(sys.argv[1]) as f:
        spec = yaml.safe_load(f)

    module = spec.get("module")
    if not module:
        die("spec missing required field: module")
    # NOTE: build artifacts carry NO addresses (build-vs-assignment separation).
    # window_base / absolute placement is owned by the assignment phase (registry
    # toolbox), never baked into a module build netlist.

    # ---- passive bus (barrier medium): no clock, no compute, just lanes -------
    # A bus (kind: passive_bus, or a bus_nodes section) is the lock-free barrier a
    # producer dumps onto and a consumer samples (wire, dom_bus). It owns NO logic;
    # emit only its addressed lanes (unroll-expanded). No comb_nodes required.
    if spec.get("kind") == "passive_bus" or spec.get("bus_nodes"):
        width = int(spec.get("width", 0) or 0)
        bus = expand_unroll(spec.get("bus_nodes", []), width)
        if not bus:
            die("passive bus has no bus_nodes — a bus must declare its lanes")
        names = [b["name"] for b in bus]
        if len(names) != len(set(names)):
            die("passive bus has duplicate lane names")
        net = {
            "device": module,
            "kind": "passive_bus",
            "comment": (spec.get("comment") or
                        f"GENERATED by gen_module_net.py from {module}_logic.yaml — "
                        "passive lock-free barrier bus: addressed lanes only, no clock, "
                        "no compute. The producer DEPOSITS into these lanes (sole writer); "
                        "consumers SAMPLE them (a module never reads another's registers)."),
            "bus_nodes": [{"name": b["name"], "type": b.get("type", "u64"),
                           "comment": b.get("comment", "")} for b in bus],
        }
        json.dump(net, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return

    width = int(spec.get("width", 0) or 0)
    seam_inputs = expand_unroll(spec.get("seam_inputs", []), width)
    const_nodes_in = expand_unroll(spec.get("const_nodes", []), width)
    dff_nodes_in = expand_unroll(spec.get("dff_nodes", []), width)
    comb_nodes_in = expand_unroll(spec.get("comb_nodes", []), width)
    hist = spec.get("history_ring") or None
    if hist and hist.get("fields"):
        hist = dict(hist)
        hist["fields"] = expand_unroll(hist["fields"], width)
    seam_outputs = spec.get("seam_outputs", []) or []
    wiring = spec.get("wiring", {}) or {}
    clock = spec.get("clock") or None
    # A non-dict clock (e.g. "passive") means the module owns no clock — the
    # fabric clocks it. Only a dict declares a clock generator (power bit).
    if not isinstance(clock, dict):
        clock = None

    if not comb_nodes_in:
        die("spec has no comb_nodes — emitting this would produce a STUB "
            "device (the WAVE-1 failure). Add the combinational logic.")

    # ---- name universe for input resolution --------------------------------
    input_names = {n["name"] for n in seam_inputs}
    const_names = {n["name"] for n in const_nodes_in}
    dff_names = {n["name"] for n in dff_nodes_in}
    comb_names = {n["name"] for n in comb_nodes_in}
    # a comb input may reference: a config/const/dff register, or another comb
    # node's value (forward references are forbidden — must be declared earlier).
    resolvable = input_names | const_names | dff_names

    # ---- validate comb_nodes (cell type, arity, input resolution, order) ----
    seen_comb = set()
    for c in comb_nodes_in:
        nm = c.get("name")
        cell = c.get("cell")
        ins = c.get("inputs", [])
        if not nm:
            die("comb_node missing name")
        if cell not in KNOWN_CELLS:
            die(f"comb_node {nm}: unknown cell '{cell}' "
                f"(known: {sorted(KNOWN_CELLS)})")
        arity = CELL_ARITY[cell]
        if len(ins) != arity:
            die(f"comb_node {nm}: cell '{cell}' needs {arity} inputs, got {len(ins)}")
        for i in ins:
            if i not in resolvable and i not in seen_comb:
                die(f"comb_node {nm}: input '{i}' does not resolve to any "
                    f"declared input/const/dff or an EARLIER comb_node "
                    f"(forward reference / typo?)")
        seen_comb.add(nm)

    # ---- validate dff fed_by / enable ---------------------------------------
    feedable = comb_names | dff_names | input_names | const_names
    for d in dff_nodes_in:
        nm = d["name"]
        fed = d.get("fed_by")
        # default fed_by: same-named *_UPDATE comb, else hold.
        if fed is None:
            cand = nm + "_UPDATE"
            fed = cand if cand in comb_names else nm
            d["fed_by"] = fed
        if fed not in feedable:
            die(f"dff {nm}: fed_by '{fed}' does not resolve to a comb_node/"
                f"dff/input/const")
        en = d.get("enable")
        if en is not None and en not in feedable:
            die(f"dff {nm}: enable '{en}' does not resolve to a known node")

    # ---- validate history ring ---------------------------------------------
    if hist:
        depth = hist.get("depth")
        if not depth or depth <= 0 or (depth & (depth - 1)) != 0:
            die(f"history_ring.depth ({depth}) must be a power of two")
        for fld in hist.get("fields", []):
            src = fld.get("source")
            if src not in resolvable and src not in comb_names:
                die(f"history_ring field {fld.get('name')}: source '{src}' unresolved")
        we = hist.get("write_enable")
        if we is not None and we not in feedable:
            die(f"history_ring.write_enable '{we}' unresolved")

    # ---- validate seam outputs ----------------------------------------------
    for s in seam_outputs:
        if s.get("source") not in (resolvable | comb_names):
            die(f"seam_output {s.get('name')}: source '{s.get('source')}' unresolved")

    # ---- build the netlist ---------------------------------------------------
    net = {
        "device": module,
        "kind": spec.get("kind", "module"),
        "comment": (
            f"GENERATED by gen_module_net.py from {module}_logic.yaml — "
            "DO NOT EDIT BY HAND. Complete netlist: every register's update is a "
            "named comb_node chain of canonical cells; every dff names what feeds "
            "it and when it is enabled (mask-algebra gated write, no if). "
            "comb_nodes + wiring are present (the WAVE-1 omission is fixed)."
        ),
        "config_nodes": [
            {"name": n["name"], "type": n.get("type", "u64"),
             "source": n.get("source", ""), "comment": n.get("comment", "")}
            for n in seam_inputs
        ],
        "const_nodes": [
            {"name": n["name"], "type": n.get("type", "u64"),
             "value": int(n.get("value", 0)), "comment": n.get("comment", "")}
            for n in const_nodes_in
        ],
        "dff_nodes": [
            {k: v for k, v in [
                ("name", d["name"]),
                ("type", d.get("type", "u64")),
                ("fed_by", d["fed_by"]),
                ("enable", d.get("enable")),
                ("comment", d.get("comment", "")),
            ] if v is not None}
            for d in dff_nodes_in
        ],
        "comb_nodes": [
            {k: v for k, v in [
                ("name", c["name"]),
                ("cell", c["cell"]),
                ("inputs", c["inputs"]),
                ("invert", c.get("invert")),
                ("sub", c.get("sub")),
                ("shift_right", c.get("shift_right")),
                ("comment", c.get("comment", "")),
            ] if v is not None}
            for c in comb_nodes_in
        ],
        "seam_nodes": [
            {"name": s["name"], "source": s["source"], "type": s.get("type", "u64"),
             "comment": s.get("comment", "")}
            for s in seam_outputs
        ],
        "wiring": wiring,
    }
    if hist:
        # History is a record STORE (shift-in), not an index construct (Law #10):
        # no index register. Each record carries its own coordinates as fields.
        net["history_ring"] = {
            "name": hist["name"],
            "depth": hist["depth"],
            "write_enable": hist.get("write_enable"),
            "fields": [{"name": fl["name"], "source": fl["source"]}
                       for fl in hist["fields"]],
        }
    if clock:
        net["clock"] = {"power": clock.get("power"),
                        "comment": clock.get("comment", "")}

    json.dump(net, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
