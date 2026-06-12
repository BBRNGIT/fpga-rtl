#!/usr/bin/env python3
"""install_system.py — the module-install CAMPAIGN. Synthesizes every on-fabric
module onto the locked blank (via synth.py), verifies each bit-exact vs its native
module, places them in DISJOINT partitions (sequential grid-positional tiles), and
emits the floorplan (the placement map, disjoint by construction).

adapter + wire are OFF-fabric (ingress); dom_bus is a conductor bus (lanes), not
cell-synthesized. The rest are bit-blasted onto LUT6 + FF BELs.

Usage: python3 install/install_system.py [system.yaml]
"""
import glob
import json
import os
import subprocess
import sys

try:
    import yaml
except Exception:
    sys.stderr.write("install_system: PyYAML required\n"); sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
FAB = os.path.join(ROOT, "fpga")
GEN = os.path.join(HERE, "gen")


def module_netlist(dirn):
    for n in sorted(glob.glob(os.path.join(ROOT, dirn, "*.net.json"))):
        d = json.load(open(n))
        if d.get("dff_nodes"):
            return n, d
    return None, None


def main():
    spec = yaml.safe_load(open(sys.argv[1])) if len(sys.argv) > 1 else \
        yaml.safe_load(open(os.path.join(HERE, "system.yaml")))
    next_tile = 0
    floor, results = {}, []
    for dirn in spec.get("synthesize", []):
        netp, d = module_netlist(dirn)
        if not netp:
            results.append((dirn, "— no netlist with dff_nodes")); continue
        mod = d["device"]
        r = subprocess.run([sys.executable, os.path.join(HERE, "synth.py"), netp, str(next_tile)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            results.append((mod, "SYNTH FAIL: " + (r.stderr.strip().splitlines() or [""])[-1])); continue
        cfg = json.load(open(os.path.join(HERE, "configs", f"{mod}.cell_synth.config.json")))
        tiles = cfg["tiles"]
        floor[mod] = {"start": tiles[0], "n_tiles": len(tiles),
                      "luts": cfg["n_gates"], "ff_bels": cfg["n_ff"], "dir": dirn}
        next_tile = tiles[-1] + 1
        vc = os.path.join(GEN, f"{mod}_synth_verify.c")
        exe = f"/tmp/vsys_{mod}"
        cc = subprocess.run(["cc", "-O0", "-std=c11", "-w", "-I" + FAB,
                             "-I" + os.path.join(ROOT, dirn), "-I" + GEN, vc, "-o", exe],
                            capture_output=True, text=True)
        if cc.returncode != 0:
            results.append((mod, "CC FAIL: " + (cc.stderr.strip().splitlines() or [""])[-1])); continue
        run = subprocess.run([exe], capture_output=True, text=True)
        results.append((mod, (run.stdout.strip() or run.stderr.strip() or "ran")))

    yaml.safe_dump({"blank": "vu9p", "note": "disjoint by construction (sequential placement)",
                    "off_fabric": spec.get("off_fabric", []), "conductor": spec.get("conductor", []),
                    "partitions": floor},
                   open(os.path.join(HERE, "floorplan.yaml"), "w"), sort_keys=False)

    print("=== module install campaign (cell-level synthesis onto the blank) ===")
    for m, res in results:
        print(f"  {m:13} {res}")
    ok = sum(1 for _, r in results if "bit-exact" in r and " 0/" not in r)
    print(f"--- {ok}/{len(results)} modules synthesized + verified; "
          f"floorplan: {len(floor)} partitions over tiles 0..{max(0,next_tile-1)} (disjoint) ---")


if __name__ == "__main__":
    main()
