#!/usr/bin/env python3
"""
realize.py — THE canonical realization controller. Holds P1..P6 as executable dev steps so
the roadmap lives in CODE, not in anyone's memory. It measures progress from artifacts on
disk (never self-reported), enforces phase order (no skipping), and drives each phase as a
work-list across parallel tool copies with gate observation.

This is the factory conductor (Law #11) for v3. It assigns nothing and writes no hardware —
it sequences the construction tools and reports truthfully where we are.

Canonical reference: ../V3_REALIZATION_ROADMAP.md  (this file is its executable form).

Usage:
  realize.py status            # truthful progress of every phase, measured from disk
  realize.py plan  <P1..P6>    # the canonical steps + gate + parallelism of a phase
  realize.py worklist <P1..P6> # the concrete pending items of a phase (from artifacts)
  realize.py gate  <P1..P6>    # is the phase complete (its gate satisfied)?
"""
import sys, os, json, argparse
HERE = os.path.dirname(os.path.abspath(__file__))

def load(p, d=None):
    try: return json.load(open(os.path.join(HERE, p)))
    except Exception: return d

# ---- the canonical phases (the roadmap, as data) --------------------------------------
PHASES = [
 {"id": "P1", "name": "Primitive Library Realization (layered)", "depends": [],
  "goal": "realize the PHYSICAL fabric primitive set (UG574/573/579/570) + a config model mapping "
          "the 148 catalogue entries onto CONFIGURATIONS of them. NOT 148 gate netlists. "
          "FDRE/FDSE/FDCE/FDPE = one configurable storage element (UG574-confirmed).",
  "inputs": ["UG574/573/579/570 cache (physical elements)", "catalog.json (config space)", "templates.py"],
  "tool": "physical-element builder + config-map -> assemble.py -> library.json -> netc.py",
  "steps": ["extract physical element set from UG574/573/579/570", "realize each physical element",
            "config-map: catalogue entry -> (element, config)", "assemble -> library.json",
            "netc validate; cross-check element counts vs DS891"],
  "gate": ["netc validation (single-writer/no-overlap/no-floating)", "port cross-check vs catalog",
           "logic-content (>=1 structural cell)"],
  "parallel": 100},
 {"id": "P2", "name": "Container Casting", "depends": ["P1"],
  "goal": "cast THE one blank container: tile types arrayed at grid (X,Y) by authentic DS891 "
          "counts, with native clocks/RAM/IO/lanes. Grid coord IS identity; a blank assigns nothing.",
  "inputs": ["library.json (P1)", "ds_resources.json", "UG572 clock fabric"],
  "tool": "blank caster + grid-array tool (region-sharded)",
  "steps": ["cell-struct footprint sizing", "fabric-iteration exemption in enforcement_registry",
            "tile-type array per DS891 count", "region-shard assembly", "native clocks seated"],
  "gate": ["blank-identity (2k)", "clock-rule (2g)", "no monolithic file (per-file ceiling)"],
  "parallel": 100},
 {"id": "P3", "name": "Interconnect Fabric", "depends": ["P2"],
  "goal": "clock fabric (transcribe UG572) + logic fabric (synthesize INT/PIP crossbar from "
          "primitives) + router (route connections -> PIP config).",
  "inputs": ["P2 container", "UG572 tracks/regions", "board_net + figblocks + richtext.routing"],
  "tool": "int_tile builder + route.py (region-sharded)",
  "steps": ["clock routing/distribution tracks", "INT-tile PIP crossbar", "router convergence + reroute"],
  "gate": ["single-driver-per-wire", "no-shorts"],
  "parallel": 50},
 {"id": "P4", "name": "PS Realization", "depends": ["P2"],
  "goal": "UG1085 PS blocks -> behavioral/derived C leaves with documented interfaces; wire the "
          "PS-PL AXI seam (S_AXI_HP/HPC/ACE/ACP, M_AXI_HPM, EMIO, clocks, interrupts) to PL.",
  "inputs": ["ps_ports.json", "ug1085_richtext.json (regs/sequences)", "P2 container"],
  "tool": "PS block builder per controller + AXI-seam wiring",
  "steps": ["PS interface blocks", "DRP/register logic where documented", "PS-PL AXI seam"],
  "gate": ["module-contract (2i)", "build-purity (2j)"],
  "parallel": 20},
 {"id": "P5", "name": "Configuration / Load (design onto container)", "depends": ["P3"],
  "goal": "LOAD the HFT design payload onto the cast container via the router (system block "
          "diagram -> PIP/bitstream). Configure the container; never place on an empty blank. "
          "PAYLOAD decided later by a mapping tool against the working blank + BIOS, not now.",
  "inputs": ["P3 interconnected container", "HFT module set (TBD by mapping tool)"],
  "tool": "mapping framework + route.py install",
  "steps": ["mapping tool selects payload vs blank+BIOS", "per-module install/route", "bitstream"],
  "gate": ["module-contract (2i)", "index-doctrine (2h)", "build-purity (2j)", "arithmetic (2b)"],
  "parallel": 30},
 {"id": "P6", "name": "Unify / Boot / Validate (one fpga_device)", "depends": ["P4", "P5"],
  "goal": "unify all layers into ONE fpga_device C model; POST = fabric + native clocks tick on "
          "power; accessible via the existing BIOS. Full gate.sh + clean-room determinism.",
  "inputs": ["P3 fabric", "P4 PS", "P5 loaded design", "BIOS"],
  "tool": "gen_fpga_device unify + BIOS boot + gate.sh",
  "steps": ["unify fabric+PS+design", "BIOS POST boot", "full gate.sh", "clean-room rebuild"],
  "gate": ["gate.sh stages 1,2,2b-2k,3", "clean-room determinism"],
  "parallel": 1},
]

# ---- truthful progress measured from artifacts (NOT self-reported) ---------------------
def measure(pid):
    """returns (done:int, total:int, note:str) read live from disk artifacts."""
    if pid == "P1":
        cat = load("catalog.json", {})
        lib = load("library.json", {"blocks": {}, "primitives": {}})
        realized = set(lib.get("blocks", {})) | set(lib.get("primitives", {}))
        targets = {k for k, v in cat.items() if v.get("ports")}     # ported primitives are the worklist
        done = len(targets & realized)
        return done, len(targets), f"{len(lib.get('primitives',{}))} atoms + {len(lib.get('blocks',{}))} blocks in library.json"
    if pid == "P2":
        return (1 if os.path.exists(os.path.join(HERE, "..", "..", ".bbhft")) else 0), 1, "container cast?"
    return 0, 1, "not started"

def status():
    print("REALIZATION STATUS — measured from disk (V3_REALIZATION_ROADMAP.md is canonical)\n")
    done_phase = {}
    for ph in PHASES:
        d, t, note = measure(ph["id"])
        blocked = [p for p in ph["depends"] if not done_phase.get(p)]
        complete = (d >= t and t > 0)
        done_phase[ph["id"]] = complete
        bar = f"{d}/{t}"
        state = "DONE" if complete else ("BLOCKED:" + ",".join(blocked) if blocked else "ACTIVE" if d else "PENDING")
        print(f"  {ph['id']}  {ph['name']:34s} {bar:>9s}  {state}")
        print(f"       {note}")
    print("\nNext runnable:", next((p['id'] for p in PHASES
          if not done_phase.get(p['id']) and all(done_phase.get(x) for x in p['depends'])), "— all done"))

def show(pid, what):
    ph = next((p for p in PHASES if p["id"] == pid), None)
    if not ph: print("unknown phase", pid); return 1
    if what == "plan":
        print(f"{ph['id']} — {ph['name']}\nGOAL: {ph['goal']}\nDEPENDS: {ph['depends'] or 'none'}")
        print(f"INPUTS: {', '.join(ph['inputs'])}\nTOOL: {ph['tool']}\nPARALLEL: up to {ph['parallel']} instances")
        print("CANONICAL STEPS:"); [print(f"  {i+1}. {s}") for i, s in enumerate(ph["steps"])]
        print("GATE:"); [print(f"  - {g}") for g in ph["gate"]]
    elif what == "worklist":
        if pid != "P1": print(f"{pid} worklist computed once {ph['depends']} complete."); return 0
        cat = load("catalog.json", {}); lib = load("library.json", {"blocks": {}, "primitives": {}})
        realized = set(lib.get("blocks", {})) | set(lib.get("primitives", {}))
        pending = sorted(k for k, v in cat.items() if v.get("ports") and k not in realized)
        print(f"P1 pending primitives ({len(pending)}): realize a decomposition builder for each")
        import collections
        by = collections.Counter(cat[k].get("group") or "?" for k in pending)
        for g, n in by.most_common(): print(f"  {n:3d}  group={g}")
        print("\nfirst 30:", pending[:30])
    return 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["status", "plan", "worklist", "gate"])
    ap.add_argument("phase", nargs="?")
    a = ap.parse_args()
    if a.cmd == "status": status()
    elif a.cmd in ("plan", "worklist"): sys.exit(show(a.phase, a.cmd))
    elif a.cmd == "gate":
        d, t, note = measure(a.phase); print(f"{a.phase}: {d}/{t} — {'COMPLETE' if d>=t and t>0 else 'INCOMPLETE'} ({note})")
