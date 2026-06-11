#!/usr/bin/env python3
"""circuitlib.py — circuit-builder catalog: extended primitives lowered to canonical cells.

The canonical cell set (cells.h, immutable):
    buf, not, and, or, xor, mux, eqmask, fa, gate, addsub, dff

This library adds DESIGN VOCABULARY on top — JK/T/SR flip-flops, latches,
counters, shift registers — implemented as pure lowering functions that expand
each extended primitive into a netlist fragment of canonical cells only.
The emitted netlist (and therefore the generated *_gen.h C) never contains an
extended primitive: the catalog exists at netlist-authoring time only.

Netlist fragment format (matches validate_device.py conventions):
    {
      "comb_nodes": [ {"name": n, "cell": c, "inputs": [..]} , ... ],
      "dff_nodes":  [ {"name": n, "cell": "dff", "d": <comb node>,
                       "en": <node>, "init": int} , ... ],
      "outputs":    [ q-node names ],
    }

Inputs are referenced by node NAME. The constant nodes "ZERO" and "ONE" may be
referenced; the device emitter declares them once as config nodes.

All functions are pure (no I/O, no state). `simulate()` is a reference
tick-evaluator used by unit tests to verify the lowered truth tables — it is a
test instrument, not part of any device.

No floats, no heap concepts, integers only.
"""

from typing import Dict, List

CANONICAL_CELLS = (
    "buf", "not", "and", "or", "xor", "mux", "eqmask", "fa", "gate",
    "addsub", "dff",
)

EXTENDED_CATALOG = (
    "sr_ff", "jk_ff", "t_ff", "d_latch", "counter", "shift_register",
)


def _frag(comb=None, dff=None, outputs=None) -> Dict:
    return {
        "comb_nodes": list(comb or []),
        "dff_nodes": list(dff or []),
        "outputs": list(outputs or []),
    }


def _merge(*frags) -> Dict:
    out = _frag()
    for f in frags:
        out["comb_nodes"] += f["comb_nodes"]
        out["dff_nodes"] += f["dff_nodes"]
        out["outputs"] += f["outputs"]
    return out


# ---- canonical wrappers ----------------------------------------------------

def lower_dff(name: str, d: str, en: str = "ONE", init: int = 0) -> Dict:
    """Canonical D flip-flop: q' = en ? d : q."""
    return _frag(
        dff=[{"name": name, "cell": "dff", "d": d, "en": en, "init": init}],
        outputs=[name],
    )


# ---- extended primitives → canonical lowering -------------------------------

def lower_sr_ff(name: str, s: str, r: str, init: int = 0) -> Dict:
    """SR flip-flop. q' = S | (q & ~R).  (S=1,R=1 resolves as set-dominant.)

    Lowering: not(r) → and(q, ~r) → or(s, hold) → dff.
    """
    n_notr = f"{name}__notr"
    n_hold = f"{name}__hold"
    n_d = f"{name}__d"
    return _frag(
        comb=[
            {"name": n_notr, "cell": "not", "inputs": [r]},
            {"name": n_hold, "cell": "and", "inputs": [name, n_notr]},
            {"name": n_d, "cell": "or", "inputs": [s, n_hold]},
        ],
        dff=[{"name": name, "cell": "dff", "d": n_d, "en": "ONE", "init": init}],
        outputs=[name],
    )


def lower_jk_ff(name: str, j: str, k: str, init: int = 0) -> Dict:
    """JK flip-flop. q' = (J & ~q) | (~K & q).

    J=K=1 → toggle; J=1,K=0 → set; J=0,K=1 → reset; J=K=0 → hold.
    """
    n_notq = f"{name}__notq"
    n_notk = f"{name}__notk"
    n_set = f"{name}__setterm"
    n_hold = f"{name}__holdterm"
    n_d = f"{name}__d"
    return _frag(
        comb=[
            {"name": n_notq, "cell": "not", "inputs": [name]},
            {"name": n_notk, "cell": "not", "inputs": [k]},
            {"name": n_set, "cell": "and", "inputs": [j, n_notq]},
            {"name": n_hold, "cell": "and", "inputs": [n_notk, name]},
            {"name": n_d, "cell": "or", "inputs": [n_set, n_hold]},
        ],
        dff=[{"name": name, "cell": "dff", "d": n_d, "en": "ONE", "init": init}],
        outputs=[name],
    )


def lower_t_ff(name: str, t: str, init: int = 0) -> Dict:
    """T flip-flop. q' = q ^ T.  Lowering: xor(q, t) → dff."""
    n_d = f"{name}__d"
    return _frag(
        comb=[{"name": n_d, "cell": "xor", "inputs": [name, t]}],
        dff=[{"name": name, "cell": "dff", "d": n_d, "en": "ONE", "init": init}],
        outputs=[name],
    )


def lower_d_latch(name: str, d: str, en: str, init: int = 0) -> Dict:
    """Transparent-when-enabled latch, registered at the tick boundary.

    In the single-tick C-as-RTL model the latch is a dff whose enable IS the
    latch enable: q' = en ? d : q — exactly cell_dff(q, d, en).
    """
    return _frag(
        dff=[{"name": name, "cell": "dff", "d": d, "en": en, "init": init}],
        outputs=[name],
    )


def lower_counter(name: str, en: str = "ONE", init: int = 0) -> Dict:
    """Up-counter (64-bit word). q' = q + (en ? 1 : 0).

    Lowering: gate(ONE, en) → addsub(q, inc, ZERO) → dff. The addsub is the
    structural carry-chain primitive — no native '+' reaches the device.
    """
    n_inc = f"{name}__inc"
    n_sum = f"{name}__sum"
    return _frag(
        comb=[
            {"name": n_inc, "cell": "gate", "inputs": ["ONE", en]},
            {"name": n_sum, "cell": "addsub", "inputs": [name, n_inc, "ZERO"]},
        ],
        dff=[{"name": name, "cell": "dff", "d": n_sum, "en": "ONE", "init": init}],
        outputs=[name],
    )


def lower_shift_register(name: str, din: str, stages: int,
                         en: str = "ONE", init: int = 0) -> Dict:
    """Serial-in shift register: chain of `stages` dffs. Output = last stage.

    Stage i latches stage i-1 (stage 0 latches din) each enabled tick.
    """
    if stages < 1:
        raise ValueError("shift_register requires stages >= 1")
    dffs = []
    prev = din
    last = ""
    for i in range(stages):
        stage = f"{name}__s{i}" if i < stages - 1 else name
        dffs.append({"name": stage, "cell": "dff", "d": prev, "en": en,
                     "init": init})
        prev = stage
        last = stage
    return _frag(dff=dffs, outputs=[last])


# ---- dispatcher --------------------------------------------------------------

def lower(kind: str, name: str, **kw) -> Dict:
    """Lower an extended-catalog (or canonical dff) node to canonical cells."""
    table = {
        "dff": lower_dff,
        "sr_ff": lower_sr_ff,
        "jk_ff": lower_jk_ff,
        "t_ff": lower_t_ff,
        "d_latch": lower_d_latch,
        "counter": lower_counter,
        "shift_register": lower_shift_register,
    }
    if kind not in table:
        raise ValueError(f"unknown catalog primitive '{kind}'")
    return table[kind](name, **kw)


# ---- reference tick simulator (TEST INSTRUMENT ONLY) -------------------------

MASK64 = (1 << 64) - 1


def _eval_cell(cell: str, vals: List[int]) -> int:
    """Evaluate one canonical cell exactly as cells.h defines it."""
    if cell == "buf":
        return vals[0] & MASK64
    if cell == "not":
        return ~vals[0] & MASK64
    if cell == "and":
        return (vals[0] & vals[1]) & MASK64
    if cell == "or":
        return (vals[0] | vals[1]) & MASK64
    if cell == "xor":
        return (vals[0] ^ vals[1]) & MASK64
    if cell == "mux":  # (a, b, sel): sel ? b : a
        a, b, sel = vals
        m = (-(sel & 1)) & MASK64
        return (a ^ ((a ^ b) & m)) & MASK64
    if cell == "eqmask":
        return 1 if (vals[0] & MASK64) == (vals[1] & MASK64) else 0
    if cell == "gate":  # (val, en)
        m = (-(vals[1] & 1)) & MASK64
        return vals[0] & m
    if cell == "addsub":  # (a, b, sub)
        a, b, sub = vals
        s = sub & 1
        bm = (b ^ ((-s) & MASK64)) & MASK64
        carry = s
        total = 0
        for i in range(64):
            aa = (a >> i) & 1
            bb = (bm >> i) & 1
            sm = aa ^ bb ^ carry
            carry = (aa & bb) | (carry & (aa ^ bb))
            total |= sm << i
        return total
    if cell == "fa":
        aa, bb, cc = vals[0] & 1, vals[1] & 1, vals[2] & 1
        s = aa ^ bb ^ cc
        co = (aa & bb) | (cc & (aa ^ bb))
        return s | (co << 1)
    raise ValueError(f"unknown canonical cell '{cell}'")


def simulate(frag: Dict, ticks: List[Dict[str, int]]) -> List[Dict[str, int]]:
    """Tick-simulate a lowered fragment.

    `ticks` is a list of per-tick input maps (node name → value). Returns the
    dff state after each tick. Constants ZERO/ONE are provided automatically.
    Combinational nodes are evaluated in dependency order each tick (READ →
    COMPUTE), then all dffs commit simultaneously (WRITE), matching the
    generated *_tick() phase structure.
    """
    state = {d["name"]: int(d.get("init", 0)) for d in frag["dff_nodes"]}
    history = []
    for inputs in ticks:
        env = {"ZERO": 0, "ONE": 1}
        env.update(state)
        env.update(inputs)
        # COMPUTE — iterate until fixed point (fragments are acyclic in comb)
        pending = list(frag["comb_nodes"])
        guard = len(pending) + 1
        while pending and guard:
            guard -= 1
            rest = []
            for node in pending:
                if all(i in env for i in node["inputs"]):
                    env[node["name"]] = _eval_cell(
                        node["cell"], [env[i] for i in node["inputs"]])
                else:
                    rest.append(node)
            if len(rest) == len(pending):
                missing = [n["name"] for n in rest]
                raise ValueError(f"unresolvable comb nodes: {missing}")
            pending = rest
        # WRITE — all dffs commit from pre-write env
        nxt = {}
        for d in frag["dff_nodes"]:
            q = state[d["name"]]
            dv = env.get(d["d"], state.get(d["d"], 0))
            en = env.get(d["en"], 1)
            m = (-(en & 1)) & MASK64
            nxt[d["name"]] = (q ^ ((q ^ dv) & m)) & MASK64
        state = nxt
        history.append(dict(state))
    return history
