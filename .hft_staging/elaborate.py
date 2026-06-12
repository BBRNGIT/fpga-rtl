#!/usr/bin/env python3
"""elaborate.py — THE elaborator (description + library -> flip-flop netlist).

The single front-end of the EDA-scale pipeline. Reads a DESCRIPTION (a composition
of library components — *.desc.yaml) and the COMPONENT LIBRARY (atoms + composites,
single-rooted in the flip-flop), and recursively FLATTENS every instance through
the library until only atoms remain — exactly as a Verilog elaborator flattens to
gates/FFs. Emits a flat netlist of atoms in the schema the generic generator
(gennet.py) lowers to flip-flop C. So the one pipeline is:

    elaborate.py  (description + library -> flat atom netlist)
        -> gennet.py  (netlist -> flip-flop C)

This is a TOOL. It DESIGNS NOTHING: it can only instantiate library components and
wire ports; there is no path by which a value, field, or logic not present in the
description+library can enter the output. Output is a pure function of its inputs
(byte-match reproducible).

Usage:
    python3 elaborate.py <design>.desc.yaml > <design>.net.json
"""
import glob
import json
import os
import sys

try:
    import yaml
except ImportError:
    sys.stderr.write("elaborate: PyYAML required\n")
    sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "library")


def die(msg):
    sys.stderr.write("elaborate: " + msg + "\n")
    sys.exit(2)


def load_library():
    """The library has THREE primitive classes (founder law): gate/boolean atoms +
    the dff flip-flop atom (cells), conductors (wire — carried through, NOT a
    flip-flop), and composites. Returns (atoms, conductors, comps)."""
    a = yaml.safe_load(open(os.path.join(LIB, "atoms.yaml"))) or {}
    atoms = {**(a.get("gates") or {}), **(a.get("flip_flops") or {})}
    cond_path = os.path.join(LIB, "conductors.yaml")
    conductors = ((yaml.safe_load(open(cond_path)) or {}).get("conductors", {})
                  if os.path.exists(cond_path) else {})
    comps = {}
    for f in glob.glob(os.path.join(LIB, "components", "*.comp.yaml")):
        c = yaml.safe_load(open(f))
        comps[c["component"]] = c
    return atoms, conductors, comps


def atom_reader_driver(atoms, t):
    """(reader ports, driver ports) for an atom. A port in BOTH in and out (dff.q)
    is self-driven feedback — a driver, not a net-reader."""
    a = atoms[t]
    outs = list(a.get("out", []))
    readers = [p for p in a.get("in", []) if p not in outs]
    return readers, outs


def sanitize(path):
    return path.replace("/", "_").replace(".", "_").replace("::", "_")


def resolve_params(params, env):
    out = {}
    for k, v in (params or {}).items():
        out[k] = env[v] if isinstance(v, str) and v in env else v
    return out


def main():
    if len(sys.argv) < 2:
        die("usage: elaborate.py <design>.desc.yaml > <design>.net.json")
    design = yaml.safe_load(open(sys.argv[1]))
    if "design" not in design or "instances" not in design:
        die("not a description (need 'design' + 'instances')")
    atoms, conductors, comps = load_library()

    nets = []           # each: list of fully-qualified endpoints
    atom_insts = {}     # ipath -> {type, params}

    def body_of(node):
        return node.get("body", node)

    def flatten(node, path, env):
        b = body_of(node)
        for conn in b.get("connections", []) or []:
            ep_q = []
            for ep in conn["net"]:
                if "." in ep:
                    inst, port = ep.split(".", 1)
                    ep_q.append(f"{path}/{inst}.{port}")
                else:
                    ep_q.append(f"{path}::{ep}")
            nets.append(ep_q)
        for inst in b.get("instances", []) or []:
            X, nm = inst["component"], inst["name"]
            ipath = f"{path}/{nm}"
            p = resolve_params(inst.get("params", {}), env)
            if X in atoms:
                atom_insts[ipath] = {"type": X, "params": p}
            elif X in conductors:
                # Conductor (wire): a passive carrier, NOT a flip-flop. Carry the
                # signal THROUGH — alias each tap (out) to each drive (in); emit no
                # logic node. The upstream driver flows to the readers unchanged.
                cdef = conductors[X]
                for op in cdef.get("out", []):
                    for ip in cdef.get("in", []):
                        nets.append([f"{path}/{nm}.{op}", f"{path}/{nm}.{ip}"])
            elif X in comps:
                cdef = comps[X]
                cin = cdef["ports"].get("in", [])
                cout = cdef["ports"].get("out", [])
                for port in list(cin) + list(cout):
                    nets.append([f"{path}/{nm}.{port}", f"{ipath}::{port}"])
                child_env = {**(cdef.get("params") or {}), **p}
                flatten(cdef, ipath, child_env)
            else:
                die(f"unknown component '{X}' (not a library atom, conductor, or "
                    f"composite) — add it to the library deliberately; descriptions compose only")

    design_name = design["design"]
    in_ports = design.get("ports", {}).get("in", [])
    out_ports = design.get("ports", {}).get("out", [])
    flatten(design, "top", {})

    # ---- union-find over all net endpoints ----------------------------------
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    for net in nets:
        for e in net:
            find(e)
        for e in net[1:]:
            union(net[0], e)

    groups = {}
    for e in list(parent):
        groups.setdefault(find(e), set()).add(e)

    # ---- resolve each net's single driver -> its signal name ----------------
    def is_top_in(e):
        return e == f"top::{e.split('::',1)[1]}" and e.startswith("top::") and e.split("::", 1)[1] in in_ports

    def driver_of(e):
        if e.startswith("top::") and e.split("::", 1)[1] in in_ports:
            return ("topin", e.split("::", 1)[1])
        if "/" in e and "." in e.rsplit("/", 1)[1]:
            atomid, port = e.rsplit(".", 1)
            if atomid in atom_insts:
                _, drivers = atom_reader_driver(atoms, atom_insts[atomid]["type"])
                if port in drivers:
                    return ("atom", atomid)
        return None

    sig = {}   # endpoint -> signal name
    for rep, group in groups.items():
        drivers = [driver_of(e) for e in group]
        drivers = [d for d in drivers if d]
        uniq = set(drivers)
        if len(uniq) == 0:
            die(f"floating net (no driver): {sorted(group)}")
        if len(uniq) > 1:
            die(f"multi-writer net (single-writer law): {sorted(group)} drivers={uniq}")
        kind, ref = drivers[0]
        signal = ref if kind == "topin" else sanitize(ref)
        for e in group:
            sig[e] = signal

    def sig_at(endpoint):
        if endpoint not in sig:
            die(f"unconnected port: {endpoint}")
        return sig[endpoint]

    # ---- build the flat atom netlist (schema consumed by gennet.py) ---------
    config_nodes = [{"name": p, "type": "u64", "source": "", "comment": "design input port"}
                    for p in in_ports]
    dff_nodes, comb_nodes = [], []
    for atomid, info in atom_insts.items():
        t = info["type"]
        name = sanitize(atomid)
        if t == "dff":
            dff_nodes.append({"name": name,
                              "fed_by": sig_at(f"{atomid}.d"),
                              "enable": sig_at(f"{atomid}.en")})
        else:
            readers, _ = atom_reader_driver(atoms, t)
            node = {"name": name, "cell": t,
                    "inputs": [sig_at(f"{atomid}.{port}") for port in readers]}
            if t == "addsub":
                node["sub"] = int(info["params"].get("sub", 0))
            if t in ("sar", "shl"):
                node["shift_right"] = int(info["params"]["n"])
            comb_nodes.append(node)

    # topo-sort comb nodes so each input that is another comb is declared earlier
    comb_by = {c["name"]: c for c in comb_nodes}
    order, seen = [], set()

    def visit(n, stack):
        if n in seen:
            return
        if n in stack:
            die(f"combinational cycle through {n}")
        stack.add(n)
        for inp in comb_by[n]["inputs"]:
            if inp in comb_by:
                visit(inp, stack)
        stack.discard(n)
        seen.add(n)
        order.append(n)

    for c in comb_nodes:
        visit(c["name"], set())
    comb_sorted = [comb_by[n] for n in order]

    seam_nodes = [{"name": f"OUT_{p}", "source": sig_at(f"top::{p}"), "type": "u64",
                   "comment": f"design output port {p}"} for p in out_ports]

    net = {
        "device": design_name,
        "kind": "elaborated",
        "comment": (f"GENERATED by elaborate.py from {os.path.basename(sys.argv[1])} — "
                    "DO NOT EDIT BY HAND. A description flattened through the component "
                    "library to atoms (flip-flops + gates in C). Composition only; "
                    "nothing designed by the tool."),
        "config_nodes": config_nodes,
        "const_nodes": [],
        "dff_nodes": dff_nodes,
        "comb_nodes": comb_sorted,
        "seam_nodes": seam_nodes,
        "wiring": {},
    }
    json.dump(net, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
