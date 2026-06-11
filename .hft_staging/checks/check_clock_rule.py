#!/usr/bin/env python3
"""check_clock_rule.py — founder clock law validator (the project gate).

The reviewer for C-as-RTL work — semgrep/CVE/npm do NOT apply. Enforces the
founder clock law on <module>.net.json:

  EVERY clock the netlist defines or owns must have:
    (a) a POWER bit  — the clock self-runs from this bit (no external step);
    (b) a start/stop control — RUN_UNTIL bound, START/STOP pair, or a
        consumption-bounded position counter (adapter pattern).

A netlist OWNS a clock when it declares any of:
  - "clock" as a dict (clock generator: counter/power/step — adapter style)
  - top-level "counter" or "edge" (oscillator/counter style — taiosc, tai, mac)
  - top-level "run" dict or "run_power"/"run_bound" (self-run tick machinery)

Netlists with none of these (passive bus, pure modules) define no clock and
pass quietly.

Accepted POWER evidence (any one):
  clock.power | counter.power | edge.power | run_power | run.power |
  top-level "power" | a declared node whose name contains POWER.
The named power register must also be a declared node.

Accepted start/stop evidence (any one):
  run_bound {count, limit} | run {count, limit} | a declared node whose name
  contains RUN_UNTIL | declared START and STOP nodes | pos {counter, increment}
  (adapter pattern: the run is bounded by consuming a finite buffer).

Usage: check_clock_rule.py <netlist.json>
Exit 0 = PASS (conforms, or no clock); 1 = FAIL with the absences named.
"""
import json
import sys


def all_nodes(net):
    """Every declared node/register name in the netlist."""
    names = []
    for grp in ("config_nodes", "buffer_nodes", "dff_nodes", "comb_nodes",
                "const_nodes", "tables", "bus_nodes", "seam_nodes",
                "out_nodes"):
        for n in net.get(grp, []):
            if isinstance(n, dict) and n.get("name"):
                names.append(n["name"])
            elif isinstance(n, str):
                names.append(n)
    return set(names)


def owns_clock(net):
    """Does this netlist define or own a clock? Returns list of reasons."""
    reasons = []
    if isinstance(net.get("clock"), dict):
        reasons.append("clock generator section ('clock' dict)")
    if isinstance(net.get("counter"), dict):
        reasons.append("oscillator/counter section ('counter')")
    if isinstance(net.get("edge"), dict):
        reasons.append("oscillator edge section ('edge')")
    if isinstance(net.get("run"), dict):
        reasons.append("self-run section ('run')")
    if net.get("run_power") or isinstance(net.get("run_bound"), dict):
        reasons.append("self-run bound ('run_power'/'run_bound')")
    return reasons


def find_power(net, declared):
    """Return (name, source) of the clock power bit, or (None, None)."""
    candidates = []
    clk = net.get("clock")
    if isinstance(clk, dict) and clk.get("power"):
        candidates.append((clk["power"], "clock.power"))
    for sect in ("counter", "edge", "run"):
        s = net.get(sect)
        if isinstance(s, dict) and s.get("power"):
            candidates.append((s["power"], f"{sect}.power"))
    if isinstance(net.get("run_power"), str) and net["run_power"]:
        candidates.append((net["run_power"], "run_power"))
    if isinstance(net.get("power"), str) and net["power"]:
        candidates.append((net["power"], "power"))
    for name, src in candidates:
        if name in declared:
            return name, src
    # Fallback: any declared register flagged by name.
    for name in sorted(declared):
        if "POWER" in name.upper():
            return name, "node name"
    if candidates:
        # Named but not declared — report the first as undeclared.
        return candidates[0][0], "UNDECLARED"
    return None, None


def find_startstop(net, declared):
    """Return (description) of the start/stop mechanism, or None."""
    rb = net.get("run_bound")
    if isinstance(rb, dict) and rb.get("count") and rb.get("limit"):
        if rb["count"] in declared and rb["limit"] in declared:
            return f"run_bound ({rb['count']} < {rb['limit']})"
    run = net.get("run")
    if isinstance(run, dict) and run.get("count") and run.get("limit"):
        if run["count"] in declared and run["limit"] in declared:
            return f"run ({run['count']} < {run['limit']})"
    for name in sorted(declared):
        if "RUN_UNTIL" in name.upper():
            return f"RUN_UNTIL register ({name})"
    starts = [n for n in declared if "START" in n.upper()]
    stops = [n for n in declared if "STOP" in n.upper()]
    if starts and stops:
        return f"START/STOP pair ({starts[0]}, {stops[0]})"
    pos = net.get("pos")
    if isinstance(pos, dict) and pos.get("counter") and pos.get("increment"):
        return (f"consumption-bounded position counter "
                f"(pos: {pos['counter']} += {pos['increment']})")
    return None


def check(path):
    with open(path) as f:
        net = json.load(f)
    device = net.get("device", "?")
    reasons = owns_clock(net)
    if not reasons:
        # No clock defined/owned — nothing to enforce, pass quietly.
        return 0

    declared = all_nodes(net)
    errors = []

    power, src = find_power(net, declared)
    if power is None:
        errors.append("no power register (need a POWER bit the clock "
                      "self-runs from)")
    elif src == "UNDECLARED":
        errors.append(f"power register '{power}' is referenced but not "
                      f"declared as a node")

    startstop = find_startstop(net, declared)
    if startstop is None:
        errors.append("no start/stop control (need RUN_UNTIL bound, "
                      "START/STOP pair, or run/run_bound count+limit)")

    if errors:
        print(f"CLOCK-RULE {path}: FAIL — device '{device}' owns a clock "
              f"({'; '.join(reasons)}) but violates the founder clock law:")
        for e in errors:
            print(f"  ERROR: {e}")
        return 1
    return 0


def main():
    if len(sys.argv) != 2:
        print("Usage: check_clock_rule.py <netlist.json>")
        sys.exit(2)
    try:
        sys.exit(check(sys.argv[1]))
    except FileNotFoundError:
        print(f"CLOCK-RULE: file not found: {sys.argv[1]}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"CLOCK-RULE: invalid JSON in {sys.argv[1]}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
