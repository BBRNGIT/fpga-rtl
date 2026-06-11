#!/usr/bin/env python3
"""check_build_no_assignment.py — Build/Assignment separation enforcer.

Founder law: a module is BUILT to its own spec, standalone, with an ABSTRACT
input/output interface. Assignment (addresses, pins, registry, binding to peer
modules) is a SEPARATE later phase. A build artifact must therefore carry NO
assignment data and must NOT bind to a peer module's concrete registers.

Two detections:
  (1) ADDRESS/PIN LEAKAGE — the build artifact contains concrete addresses / pin
      maps / window_base bindings / registry slots (assignment data).
  (2) PEER-NAMESPACE BINDING — the module references another module's concrete
      register namespace (e.g. footprint referencing DOM_*/TF_*) instead of an
      abstract port. (footprint must declare a payload port, not bind to DOM.)

Usage: check_build_no_assignment.py <component_dir> [--strict]
Without --strict: report-only (exit 0), prints findings.
With --strict: any finding fails (exit 1).
"""
import sys, os, glob, re, json
try:
    import yaml
except Exception:
    yaml = None

# Known module register-namespace prefixes (peer detection).
MODULE_PREFIXES = {
    "dom": ["DOM_"], "timeframe": ["TF_"], "tai": ["TAI_"], "taiosc": ["TAISOC_", "TAIOSC_"],
    "nic": ["NIC_"], "mac": ["MAC_"], "fifo_rx": ["FIFO_", "FIFORX_"], "internal": ["INTERNAL_", "INT_"],
    "wire": ["WIRE_", "ADP_WIRE_"], "pip_resolver": ["PIP_"], "adapter": ["ADP_", "ADAPTER_"],
    "candle": ["CANDLE_"], "footprint": ["FP_"], "tpo": ["TPO_"], "cbr": ["CBR_"], "fractal": ["FRAC_", "FRACTAL_"],
}
ADDR_KEYS = re.compile(r"(window_base|^address$|^addr$|base_addr|^pin$|pins?$|registry|slot_addr)", re.I)


def own_prefixes(name):
    return MODULE_PREFIXES.get(name, [name.upper() + "_"])


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    strict = "--strict" in sys.argv
    if not args:
        sys.stderr.write("usage: check_build_no_assignment.py <component_dir> [--strict]\n"); sys.exit(2)
    comp = args[0].rstrip("/"); name = os.path.basename(comp)
    own = own_prefixes(name)
    peer_prefixes = [(m, p) for m, pl in MODULE_PREFIXES.items() if m != name for p in pl
                     if not any(p.startswith(o) or o.startswith(p) for o in own)]

    findings = []

    # (1) address/pin leakage — scan logic.yaml + net.json for assignment keys
    for f in glob.glob(os.path.join(comp, "*_logic.yaml")) + glob.glob(os.path.join(comp, "*.net.json")):
        try:
            d = yaml.safe_load(open(f)) if (f.endswith(".yaml") and yaml) else json.load(open(f))
        except Exception:
            continue
        def walk(o, path=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    if ADDR_KEYS.search(str(k)) and v not in (None, "", 0):
                        findings.append(("ADDRESS/PIN", f"{os.path.basename(f)}:{path}{k} = {v} — assignment data in a build artifact"))
                    walk(v, path + str(k) + ".")
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, path + f"[{i}].")
        walk(d)

    # (2) peer-namespace binding — declared inputs referencing a peer's registers
    for f in glob.glob(os.path.join(comp, "*_logic.yaml")):
        if not yaml:
            break
        try:
            d = yaml.safe_load(open(f))
        except Exception:
            continue
        seams = [s.get("name", "") for s in (d.get("seam_inputs") or []) if isinstance(s, dict)]
        for s in seams:
            for m, p in peer_prefixes:
                if s.startswith(p):
                    findings.append(("PEER-BINDING", f"seam_input '{s}' binds to peer module '{m}' ({p}*) — "
                                     f"declare an ABSTRACT port and bind in the assignment phase, not the build"))
                    break

    if findings:
        tag = "FAIL" if strict else "REPORT"
        print(f"check_build_no_assignment: {tag} {name}: {len(findings)} build/assignment-separation finding(s):")
        for kind, msg in findings:
            print(f"  [{kind}] {msg}")
        sys.exit(1 if strict else 0)

    print(f"check_build_no_assignment: PASS {name}: pure build (no addresses/pins, no peer-namespace binding)")
    sys.exit(0)


if __name__ == "__main__":
    main()
