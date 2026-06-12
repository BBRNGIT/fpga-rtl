#!/usr/bin/env python3
"""check_module_contract.py — System-Contract enforcer (the project gate).

Validates that a module's CONSTRUCTION matches its declared FUNCTIONAL contract
in module_contracts.yaml — so the system model (adapter self-paces, nic on MAC +
stamps TAI, dom on internal, tai is passive, indicators keep history, ...) is
enforced codebase-wide and never depends on memory or re-explanation.

Robust structural invariants checked (build-phase; no addresses/mapping):
  * the module is DECLARED in module_contracts.yaml (undeclared => fail).
  * has_history  <=>  a record store (history_ring) is present in the netlist.
  * clock_domain == 'mac' | 'internal'  =>  netlist clock == that domain string.
  * clock_domain == 'self_paced'        =>  netlist owns a clock generator (dict).
  * role == 'passive_time'              =>  has_history is false (a time value,
                                            not a historian) and data_push false.
Other domains (oscillator / cdc / counter / none) carry structural variance and
are required only to be DECLARED (their clock law is checked by check_clock_rule).

Usage: check_module_contract.py <component_dir> [--strict]
Without --strict: report-only (exit 0). With --strict: any finding fails (exit 1).
"""
import sys, os, glob, json
try:
    import yaml
except Exception:
    sys.stderr.write("check_module_contract: PyYAML required\n"); sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(HERE, "..", "module_contracts.yaml")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    strict = "--strict" in sys.argv
    if not args:
        sys.stderr.write("usage: check_module_contract.py <component_dir> [--strict]\n"); sys.exit(2)
    comp = args[0].rstrip("/"); name = os.path.basename(comp)

    reg = (yaml.safe_load(open(REGISTRY)) or {}).get("modules", {})
    if name not in reg:
        print(f"check_module_contract: FAIL {name}: not declared in module_contracts.yaml "
              f"— every module must declare its functional contract.")
        sys.exit(1)
    c = reg[name]

    nets = glob.glob(os.path.join(comp, "*.net.json"))
    # pick the module's own netlist (name match) else the first
    own = [n for n in nets if os.path.basename(n).startswith(name)] or nets
    if not own:
        print(f"check_module_contract: {name}: no netlist — skipped"); sys.exit(0)
    net = json.load(open(own[0]))

    findings = []
    has_hist = bool(net.get("history_ring"))
    clk = net.get("clock")
    cd = c.get("clock_domain")

    # has_history must match the presence of a record store
    if bool(c.get("has_history")) != has_hist:
        findings.append(f"has_history={c.get('has_history')} but record store "
                        f"{'present' if has_hist else 'absent'} in netlist")

    # clock-domain consistency (the robust cases)
    if cd in ("mac", "internal"):
        # active reference to a clock domain: netlist names it as its clock.
        if clk != cd:
            findings.append(f"clock_domain '{cd}' but netlist clock = {clk!r}")
    elif cd == "self_paced":
        # owns a clock generator (clock dict with its own counter/step/power).
        if not isinstance(clk, dict):
            findings.append(f"clock_domain 'self_paced' but netlist has no own clock "
                            f"generator (clock = {clk!r})")
    elif cd in ("internal_passive", "passive"):
        # clocked BY the fabric — must own NO clock section.
        if clk is not None:
            findings.append(f"clock_domain '{cd}' (fabric-clocked consumer) but netlist "
                            f"declares its own clock ({clk!r}) — passive modules own none")
    # oscillator / cdc / counter / none: structural variance; declaration is
    # enough here (their power+start/stop is enforced by check_clock_rule).

    # passive_time discipline (tai just exists)
    if c.get("role") == "passive_time":
        if has_hist:
            findings.append("role 'passive_time' must not keep history")
        if c.get("data_push"):
            findings.append("role 'passive_time' must not push data (declare data_push: false)")

    if findings:
        tag = "FAIL" if strict else "REPORT"
        print(f"check_module_contract: {tag} {name}: {len(findings)} contract finding(s) "
              f"[role={c.get('role')}, clock_domain={cd}, has_history={c.get('has_history')}]:")
        for f in findings:
            print(f"  [CONTRACT] {f}")
        sys.exit(1 if strict else 0)

    print(f"check_module_contract: PASS {name}: construction matches contract "
          f"[role={c.get('role')}, clock_domain={cd}, has_history={c.get('has_history')}]")
    sys.exit(0)


if __name__ == "__main__":
    main()
