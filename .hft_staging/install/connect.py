#!/usr/bin/env python3
"""connect.py — the install/connect program (phase-4 assignment; the ONLY code
that binds). Reads system_map.yaml (the block diagram in machine form) and
resolves each consumer module's abstract seam_input (source:"") to a producer's
published lane. Emits system_bindings.json (the wired-board descriptor) + a report.

Guards (anti-tangle, per the founder's scar):
  * REFUSES to bind any data lane to a *_POWER / *_RUN_UNTIL input — those are
    set by the BIOS (power on), never wired to data. So this tool is structurally
    incapable of "data controls the clock".
  * Every binding's producer lane must EXIST (no invented constructs).
  * Reports UNBOUND inputs as GAPS — never fabricates a connection to look done.

Usage: python3 install/connect.py [system_map.yaml]
"""
import glob
import json
import os
import sys

try:
    import yaml
except Exception:
    sys.stderr.write("connect: PyYAML required\n"); sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))

FIFO_HEAD_FIELDS = {"BID_PX", "ASK_PX", "TIME", "SRC_TIME", "SYMBOL", "PIP", "COMMISSION", "SEQ"}
OFF_FABRIC = {"adapter"}     # writes its bus in off-fabric C, not via a fabric netlist
STATIC_CFG = ("PIP_CFG_TABLE_", "TF_PERIOD_NS")     # operator/BIOS-loaded config, not data-wired


def netlist(mod):
    for cand in (f"rebuild/{mod}.net.json", f"{mod}/{mod}.net.json"):
        p = os.path.join(ROOT, cand)
        if os.path.exists(p):
            return json.load(open(p))
    return None


def is_power(seam):
    return seam.endswith("_POWER") or seam.endswith("_RUN_UNTIL")


def published_lanes(mod, get):
    """A producer publishes either a passive BUS (bus_nodes) or module seam outputs.
    Either way a consumer reads a PUBLISHED lane, never an internal register."""
    d = get(mod)
    if not d:
        return set()
    buses = [n["name"] for n in d.get("bus_nodes", [])]
    if buses:
        return set(buses)                         # passive barrier bus (wire, dom_bus)
    return {n["name"] for n in d.get("seam_nodes", [])}   # module's published seam outputs


def main():
    mp = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "system_map.yaml")
    spec = yaml.safe_load(open(mp))
    conns = spec.get("connections", [])

    nets = {}
    def get(mod):
        if mod not in nets:
            nets[mod] = netlist(mod)
        return nets[mod]

    bindings, errors, edges, publish_gaps = [], [], [], []
    bound = {}      # (consumer, seam) -> source string

    for c in conns:
        kind = c.get("kind")
        if kind == "writes":                       # producer is sole writer of a bus
            prod, bus = c["producer"], c["bus"]
            edges.append(f"{prod} == writes ==> bus:{bus}")
            bindings.append({"kind": "writes", "producer": prod, "bus": bus})
            pnet = get(prod)
            # a fabric module must actually PUBLISH the bus's lanes to drive it.
            if prod not in OFF_FABRIC and pnet and not pnet.get("bus_nodes"):
                outs = {n["name"] for n in pnet.get("seam_nodes", [])}
                blanes = published_lanes(bus, get)
                missing = blanes - outs
                if missing:
                    publish_gaps.append(
                        f"{prod} -> {bus}: {len(blanes & outs)}/{len(blanes)} lanes published; "
                        f"{len(missing)} unpublished ({', '.join(sorted(missing)[:3])}, ...)")
            continue
        consumer, seam, producer = c.get("consumer"), c.get("seam"), c.get("producer")
        cnet = get(consumer)
        if not cnet:
            errors.append(f"{consumer}: no netlist"); continue
        cins = {n["name"] for n in cnet.get("config_nodes", [])}
        # GUARD: never wire data into a power/run input.
        if is_power(seam):
            errors.append(f"REFUSED: {consumer}.{seam} is a power/run input — set by BIOS, "
                          f"never wired to data"); continue
        if seam not in cins:
            errors.append(f"{consumer}.{seam}: not an input of {consumer}"); continue
        # validate the producer lane EXISTS (no invented constructs).
        if kind == "lane":
            lane = c["lane"]
            if lane not in published_lanes(producer, get):
                errors.append(f"{producer}.{lane}: not a published lane of {producer}"); continue
            src = f"{producer}.{lane}"
        elif kind == "head":
            field = c["field"]
            if producer != "fifo_rx" or field not in FIFO_HEAD_FIELDS:
                errors.append(f"{producer} head field {field}: not a fifo head lane"); continue
            src = f"{producer}.HEAD.{field}"
        else:
            errors.append(f"unknown connection kind '{kind}'"); continue
        bound[(consumer, seam)] = src
        bindings.append({"kind": kind, "consumer": consumer, "seam": seam, "source": src})
        edges.append(f"{src:28} --> {consumer}.{seam}")

    # ---- gap report: classify every input of every consumer in the chain -----
    consumers = sorted({c["consumer"] for c in conns if c.get("consumer")}
                       | {"timeframe", "candle", "footprint", "tpo", "fractal"})
    gaps = {}
    for mod in consumers:
        n = get(mod)
        if not n:
            continue
        for inp in (x["name"] for x in n.get("config_nodes", [])):
            if is_power(inp):
                continue                                   # BIOS-set
            if (mod, inp) in bound:
                continue                                   # wired
            if any(inp.startswith(s) for s in STATIC_CFG):
                continue                                   # static config
            gaps.setdefault(mod, []).append(inp)

    out = {"bindings": bindings, "gaps": gaps, "errors": errors}
    json.dump(out, open(os.path.join(HERE, "system_bindings.json"), "w"), indent=2)

    print("=== connect: wired graph (data flows one way; clocks powered by BIOS) ===")
    for e in edges:
        print("  " + e)
    print(f"\n--- {len(bound)} seams bound, {len(errors)} errors ---")
    for e in errors:
        print("  ERROR:", e)
    if publish_gaps:
        print("\n--- PUBLISH gaps (producer must drive its bus) ---")
        for g in publish_gaps:
            print("  " + g)
    if gaps:
        print("\n--- UNBOUND seams (gaps — NOT fabricated; need a producer lane or module change) ---")
        for mod, gg in gaps.items():
            print(f"  {mod}: {', '.join(gg)}")
    print("\nwrote install/system_bindings.json")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
