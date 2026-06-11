#!/usr/bin/env python3
"""test_circuitlib.py — unit tests for circuitlib lowering functions.

Each extended primitive is lowered to canonical cells and tick-simulated to
verify its truth table. Runs under pytest OR plain python3.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import circuitlib as cl


def test_lowering_is_canonical_only():
    frags = [
        cl.lower("sr_ff", "Q", s="S", r="R"),
        cl.lower("jk_ff", "Q", j="J", k="K"),
        cl.lower("t_ff", "Q", t="T"),
        cl.lower("d_latch", "Q", d="D", en="EN"),
        cl.lower("counter", "CNT"),
        cl.lower("shift_register", "SR", din="DIN", stages=3),
    ]
    for f in frags:
        for n in f["comb_nodes"] + f["dff_nodes"]:
            assert n["cell"] in cl.CANONICAL_CELLS, n


def test_jk_toggle_set_reset_hold():
    f = cl.lower_jk_ff("Q", j="J", k="K", init=0)
    h = cl.simulate(f, [
        {"J": 1, "K": 0},   # set     -> 1
        {"J": 0, "K": 0},   # hold    -> 1
        {"J": 1, "K": 1},   # toggle  -> 0
        {"J": 1, "K": 1},   # toggle  -> 1
        {"J": 0, "K": 1},   # reset   -> 0
    ])
    assert [s["Q"] for s in h] == [1, 1, 0, 1, 0]


def test_t_toggle_and_hold():
    f = cl.lower_t_ff("Q", t="T", init=0)
    h = cl.simulate(f, [{"T": 1}, {"T": 0}, {"T": 1}, {"T": 1}])
    assert [s["Q"] for s in h] == [1, 1, 0, 1]


def test_sr_set_reset_hold():
    f = cl.lower_sr_ff("Q", s="S", r="R", init=0)
    h = cl.simulate(f, [
        {"S": 1, "R": 0},   # set   -> 1
        {"S": 0, "R": 0},   # hold  -> 1
        {"S": 0, "R": 1},   # reset -> 0
        {"S": 0, "R": 0},   # hold  -> 0
        {"S": 1, "R": 1},   # set-dominant -> 1
    ])
    assert [s["Q"] for s in h] == [1, 1, 0, 0, 1]


def test_counter_increments_and_gates():
    f = cl.lower_counter("CNT", en="EN", init=0)
    h = cl.simulate(f, [{"EN": 1}, {"EN": 1}, {"EN": 0}, {"EN": 1}])
    assert [s["CNT"] for s in h] == [1, 2, 2, 3]


def test_counter_wraps_64bit():
    f = cl.lower_counter("CNT", en="ONE", init=cl.MASK64)
    h = cl.simulate(f, [{}])
    assert h[0]["CNT"] == 0


def test_shift_register_pipeline():
    f = cl.lower_shift_register("SR", din="DIN", stages=3, init=0)
    h = cl.simulate(f, [{"DIN": 1}, {"DIN": 0}, {"DIN": 0}, {"DIN": 0}])
    # the 1 reaches the output (stage 3) after 3 ticks, gone on tick 4
    assert [s["SR"] for s in h] == [0, 0, 1, 0]


def test_d_latch_holds_when_disabled():
    f = cl.lower_d_latch("Q", d="D", en="EN", init=0)
    h = cl.simulate(f, [
        {"D": 5, "EN": 1},   # latch 5
        {"D": 9, "EN": 0},   # hold 5
        {"D": 9, "EN": 1},   # latch 9
    ])
    assert [s["Q"] for s in h] == [5, 5, 9]


def _main():
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                fails += 1
                print(f"FAIL {name}: {e}")
    print("ALL PASS" if fails == 0 else f"{fails} FAILURE(S)")
    sys.exit(0 if fails == 0 else 1)


if __name__ == "__main__":
    _main()
