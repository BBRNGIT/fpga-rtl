#!/usr/bin/env python3
"""simnet.py — netlist-driven reference simulator (self-verification harness).

Reads <module>.net.json and evaluates the SAME node graph the generator
transcribes into <module>_gen.h, using Python equivalents of the canonical
cells. Mirrors gennet.py's evaluation order EXACTLY:
    READ  : snapshot every dff/const/config register value
    COMPUTE: evaluate each comb_node in declaration order (cell + modifiers)
    WRITE : r[dff] = cell_dff(q, fed_by, enable); seam relays; history ring

The C compiler is unavailable in this sandbox, so this proves the LOGIC the
device executes (the netlist the generator faithfully lowers cell-for-cell) is
real OHLC behaviour — not a stub. It drives synthetic quotes across a bar
boundary and asserts open/high/low/close, volume, true-range, completed-bar
latch and history-ring append.

Run: python3 simnet.py candle.net.json
"""
import json
import sys

MASK = (1 << 64) - 1


# ---- cell equivalents (bit-exact with cells.h) ----------------------------
def c_buf(a): return a & MASK
def c_not(a): return (~a) & MASK
def c_and(a, b): return (a & b) & MASK
def c_or(a, b): return (a | b) & MASK
def c_xor(a, b): return (a ^ b) & MASK
def c_mux(a, b, sel): return b if (sel & 1) else a            # sel?b:a
def c_eqmask(a, b): return 1 if (a & MASK) == (b & MASK) else 0
def c_addsub(a, b, sub):
    return ((a - b) & MASK) if (sub & 1) else ((a + b) & MASK)
def cmp_lt(a, b): return 1 if (a & MASK) < (b & MASK) else 0
def c_dff(q, d, en): return (d & MASK) if (en & 1) else (q & MASK)


def eval_comb(node, env):
    cell = node["cell"]
    ins = [env[i] for i in node["inputs"]]
    if cell == "buf":    v = c_buf(ins[0])
    elif cell == "not":  v = c_not(ins[0])
    elif cell == "and":  v = c_and(ins[0], ins[1])
    elif cell == "or":   v = c_or(ins[0], ins[1])
    elif cell == "xor":  v = c_xor(ins[0], ins[1])
    elif cell == "eqmask": v = c_eqmask(ins[0], ins[1])
    elif cell == "mux":  v = c_mux(ins[0], ins[1], ins[2])
    elif cell == "addsub": v = c_addsub(ins[0], ins[1], int(node.get("sub", 0)))
    elif cell == "cmp_lt": v = cmp_lt(ins[0], ins[1])
    else: raise SystemExit(f"simnet: unknown cell {cell}")
    if node.get("invert"):
        v ^= 1
    sr = node.get("shift_right")
    if sr:
        v = (v >> int(sr)) & MASK
    return v & MASK


class Sim:
    def __init__(self, net):
        self.net = net
        self.r = {}
        names = []
        for grp in ("config_nodes", "const_nodes", "dff_nodes"):
            for n in net.get(grp, []):
                names.append(n["name"])
        for n in net.get("comb_nodes", []):
            names.append(n["name"])
        for s in net.get("seam_nodes", []):
            names.append(s["name"])
        for nm in names:
            self.r[nm] = 0
        # const reset values
        for n in net.get("const_nodes", []):
            self.r[n["name"]] = int(n.get("value", 0)) & MASK
        # history ring storage
        self.hist = net.get("history_ring")
        if self.hist:
            # record store (shift-in): no index register; newest at slot 0.
            self.ring = [[0] * len(self.hist["fields"])
                         for _ in range(self.hist["depth"])]

    def tick(self):
        net, r = self.net, self.r
        # READ snapshot (every name resolvable as an input)
        env = dict(r)
        # COMPUTE in declaration order; comb values added to env as we go
        for c in net.get("comb_nodes", []):
            v = eval_comb(c, env)
            env[c["name"]] = v
        # WRITE dffs (gated)
        new = {}
        for d in net.get("dff_nodes", []):
            nm = d["name"]
            src = env[d["fed_by"]]
            en = env[d["enable"]] if d.get("enable") is not None else 1
            new[nm] = c_dff(r[nm], src, en)
        # diagnostic comb registers
        for c in net.get("comb_nodes", []):
            if c["name"] not in {d["name"] for d in net.get("dff_nodes", [])}:
                new[c["name"]] = env[c["name"]]
        # seam relays
        for s in net.get("seam_nodes", []):
            new[s["name"]] = env[s["source"]]
        # history record store (shift-in): on write_enable, shift down, newest at 0.
        if self.hist:
            we = env[self.hist["write_enable"]] if self.hist.get("write_enable") is not None else 1
            if we & 1:
                depth = self.hist["depth"]
                for s in range(depth - 1, 0, -1):
                    self.ring[s] = list(self.ring[s - 1])
                self.ring[0] = [env[fld["source"]] for fld in self.hist["fields"]]
        r.update(new)


FAILS = 0
def chk(what, got, want):
    global FAILS
    ok = (got == want)
    print(f"  {'ok  ' if ok else 'FAIL'} {what:<28} got={got} want={want}")
    if not ok:
        FAILS += 1


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "candle.net.json"
    with open(path) as f:
        net = json.load(f)
    s = Sim(net)
    r = s.r

    def quote(bid, ask, bidq, askq, tf, tai):
        r["DOM_BEST_BID_PRICE_REG"] = bid; r["DOM_BEST_ASK_PRICE_REG"] = ask
        r["DOM_BEST_BID_QTY_REG"] = bidq;  r["DOM_BEST_ASK_QTY_REG"] = askq
        r["TF_BAR_SEQ"] = tf; r["TF_BAR_START"] = tai
        s.tick()

    print("== Bar 0 (tf_seq=1): quotes 100,105,98,103 ==")
    quote(100, 110, 5, 7, 1, 1000)
    quote(105, 112, 4, 9, 1, 1001)
    quote(98,  108, 6, 6, 1, 1002)
    quote(103, 109, 3, 8, 1, 1003)
    chk("BID_OPEN", r["CANDLE_BID_OPEN"], 100)
    chk("BID_HIGH", r["CANDLE_BID_HIGH"], 105)
    chk("BID_LOW", r["CANDLE_BID_LOW"], 98)
    chk("BID_CLOSE", r["CANDLE_BID_CLOSE"], 103)
    chk("TRUE_RANGE_BID", r["CANDLE_TRUE_RANGE_BID"], 7)
    chk("VOLUME_BID", r["CANDLE_VOLUME_BID"], 4)
    chk("ASK_OPEN", r["CANDLE_ASK_OPEN"], 110)
    chk("ASK_HIGH", r["CANDLE_ASK_HIGH"], 112)
    chk("ASK_LOW", r["CANDLE_ASK_LOW"], 108)
    chk("ASK_CLOSE", r["CANDLE_ASK_CLOSE"], 109)
    chk("BAR_SEQ(pre)", r["CANDLE_BAR_SEQ"], 0)
    chk("COMP_BID_OPEN(pre)", r["CANDLE_COMP_BID_OPEN"], 0)

    print("== Boundary tick (tf_seq=2): new bar seeds at 200 ==")
    quote(200, 210, 2, 4, 2, 2000)
    chk("COMP_BID_OPEN", r["CANDLE_COMP_BID_OPEN"], 100)
    chk("COMP_BID_HIGH", r["CANDLE_COMP_BID_HIGH"], 105)
    chk("COMP_BID_LOW", r["CANDLE_COMP_BID_LOW"], 98)
    chk("COMP_BID_CLOSE", r["CANDLE_COMP_BID_CLOSE"], 103)
    chk("COMP_VOLUME_BID", r["CANDLE_COMP_VOLUME_BID"], 4)
    chk("COMP_TAI", r["CANDLE_COMP_TAI"], 2000)
    chk("BAR_SEQ", r["CANDLE_BAR_SEQ"], 1)
    chk("BID_OPEN(bar1)", r["CANDLE_BID_OPEN"], 200)
    chk("BID_HIGH(bar1)", r["CANDLE_BID_HIGH"], 200)
    chk("BID_LOW(bar1)", r["CANDLE_BID_LOW"], 200)
    chk("VOLUME_BID(bar1)", r["CANDLE_VOLUME_BID"], 1)

    print("== Bar 1 continues (tf_seq=2): no double-seed ==")
    quote(205, 215, 1, 1, 2, 2001)
    chk("BID_OPEN(still200)", r["CANDLE_BID_OPEN"], 200)
    chk("BID_HIGH(bar1)", r["CANDLE_BID_HIGH"], 205)
    chk("BID_LOW(bar1)", r["CANDLE_BID_LOW"], 200)
    chk("BAR_SEQ(still1)", r["CANDLE_BAR_SEQ"], 1)

    print("== History ring slot 0 holds completed bar 0 ==")
    fnames = [f["name"] for f in s.hist["fields"]]
    chk("HIST[0].BID_HIGH", s.ring[0][fnames.index("BID_HIGH")], 105)
    chk("HIST[0].BID_LOW", s.ring[0][fnames.index("BID_LOW")], 98)
    chk("HIST[0].TAI(record time)", s.ring[0][fnames.index("TAI")], 2000)

    print(f"\nRESULT: {'ALL OHLC CHECKS PASS' if FAILS == 0 else str(FAILS)+' FAILURES'}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
