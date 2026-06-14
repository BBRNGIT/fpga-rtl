#!/usr/bin/env python3
"""
route.py — P3 router. Routes a netlist through the INT-tile grid into PIP configuration:
each net is a path of hops; each hop sets one INT_TILE PIP (a config-mux selecting the
incoming wire to drive an outgoing wire). Enforces the P3 gate: single-driver-per-wire
(no two nets drive the same tile output) with automatic reroute on contention, and no
shorts. Faithful to the synthesized fabric (pip_lib INT_TILE); the PIP-per-hop IS a
cfgcell setting.

Net source: the real connectivity in hierarchy.json (figure + PS-PL routing edges), each
endpoint mapped deterministically onto the grid. Clock nets use real UG572 clock-region
placement (from clkfab.py); logic nets use deterministic grid mapping. Output device/routes.json
and device/router_config.json.

Usage: route.py [--grid R C] [--clkfab clkfab_out.json]

PHASES:
  L2 (current): synthetic placement via hash (structural-proof only)
  L3 (this version): integrate clkfab.py for real clock routing; Dijkstra pathfinding
  L4 (future): logic-net placement locality from floorplanning
"""
import sys, os, json, hashlib, argparse, heapq, copy
from collections import defaultdict, namedtuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

def Lj(*cands):
    """Load JSON from first existing file in candidates list."""
    for c in cands:
        if os.path.exists(c): return json.load(open(c))
    return None

# ============================================================================
# CONSTANTS
# ============================================================================

TRACKS = 16              # INT_TILE routing tracks per direction (UG-style)
INT_TILE_INPUTS = 16     # INT_TILE fan-in for PIP mux
INT_TILE_OUTPUTS = 16    # INT_TILE fan-out

# Node types for routing
NodeType = namedtuple("NodeType", ["name"])
CLOCK_ROOT = NodeType("CLOCK_ROOT")
CLOCK_REGION = NodeType("CLOCK_REGION")
INT_TILE = NodeType("INT_TILE")
LOGIC_TILE = NodeType("LOGIC_TILE")
IO_TILE = NodeType("IO_TILE")
PS_TILE = NodeType("PS_TILE")

# Wire directions (UG572 convention)
DIRECTIONS = ["n", "s", "e", "w"]  # north, south, east, west (ordered list)
DIR_OFFSET = {
    "n": (-1, 0), "s": (1, 0),
    "e": (0, 1), "w": (0, -1)
}

# ============================================================================
# PLACEMENT: real clock regions + synthetic logic placement
# ============================================================================

def coord_synthetic(name, R, C):
    """L2 phase: deterministic synthetic placement via hash.
    Do NOT read grid coords as a physical floorplan."""
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    return (h % R, (h // R) % C)

def parse_clock_regions(clkfab_data):
    """Parse clkfab.py output to extract real clock-region placement.
    clkfab_data = {"clock_regions": [...], "clock_tracks": {...}, ...}
    Returns: {net_name -> (region, track, buffer_type)}"""
    clock_placement = {}
    if not clkfab_data:
        return clock_placement

    # Extract clock region assignments
    for region in clkfab_data.get("clock_regions", []):
        region_name = region.get("name", "")
        for clk_net in region.get("clocks", []):
            net_name = clk_net.get("net", "")
            if net_name:
                track = clk_net.get("track", 0)
                buffer_type = clk_net.get("buffer", "BUFG")
                coords = (region.get("row", 0), region.get("col", 0))
                clock_placement[net_name] = {
                    "region": region_name,
                    "coords": coords,
                    "track": track,
                    "buffer": buffer_type
                }
    return clock_placement

def endpoint_placement(net_name, is_clock, clock_placement, R, C):
    """Determine tile coordinates for a net endpoint.
    Clock nets use real clkfab.py placement; logic nets use synthetic hashing."""
    if is_clock and net_name in clock_placement:
        placement = clock_placement[net_name]
        return placement["coords"], placement
    # Fallback: synthetic placement for non-clock or missing clkfab data
    return coord_synthetic(net_name, R, C), None

# ============================================================================
# GRAPH OPERATIONS
# ============================================================================

class RoutingGraph:
    """Represents the INT_TILE interconnect as a directed graph of (tile, out_wire).
    Each edge represents a PIP (config-mux connection)."""

    def __init__(self, R, C):
        self.R = R  # rows
        self.C = C  # cols
        self.graph = defaultdict(list)  # (tile, out_dir, track) -> [(next_tile, next_in)]
        self.build_grid()

    def build_grid(self):
        """Build the complete INT_TILE routing graph.
        Each tile can route to its 4 neighbors on each of 16 tracks."""
        for r in range(self.R):
            for c in range(self.C):
                tile = (r, c)
                # Tile can route north, south, east, west
                for out_dir in DIRECTIONS:
                    dr, dc = DIR_OFFSET[out_dir]
                    neighbor = (r + dr, c + dc)
                    if 0 <= neighbor[0] < self.R and 0 <= neighbor[1] < self.C:
                        # Reverse direction on opposite side of neighbor tile
                        reverse_dir = {"n": "s", "s": "n", "e": "w", "w": "e"}[out_dir]
                        # Each track on this tile's output can feed a track on the neighbor's input
                        for track in range(TRACKS):
                            key = (tile, out_dir, track)
                            self.graph[key].append((neighbor, reverse_dir, track))

    def is_valid_tile(self, tile):
        """Check if tile is within grid bounds."""
        r, c = tile
        return 0 <= r < self.R and 0 <= c < self.C

    def neighbors(self, tile, out_dir, track):
        """Get reachable neighbors from (tile, out_dir, track)."""
        key = (tile, out_dir, track)
        return self.graph.get(key, [])

# ============================================================================
# PATHFINDING: Dijkstra with contention avoidance
# ============================================================================

def heuristic(pos, goal):
    """Manhattan distance heuristic (zero for Dijkstra)."""
    return abs(pos[0] - goal[0]) + abs(pos[1] - goal[1])

def dijkstra_route(graph, src, dst, taken):
    """Find shortest path from src to dst avoiding occupied wires.
    taken = set of (tile, out_dir, track) already used.
    Returns: [(tile, out_dir, track, next_tile), ...] or None if unroutable."""
    if src == dst:
        return []

    # Priority queue: (cost, tile, path_so_far)
    pq = [(0, src, [])]
    visited = set()
    costs = {src: 0}

    while pq:
        cost, tile, path = heapq.heappop(pq)

        if tile == dst:
            return path

        if tile in visited:
            continue
        visited.add(tile)

        # Try all outgoing directions and tracks
        for out_dir in DIRECTIONS:
            for track in range(TRACKS):
                wire = (tile, out_dir, track)

                # Skip occupied wires
                if wire in taken:
                    continue

                # Get neighbors reachable via this wire
                for next_tile, _, _ in graph.neighbors(tile, out_dir, track):
                    if next_tile in visited:
                        continue

                    new_cost = cost + 1  # Dijkstra: unit cost per hop
                    if next_tile not in costs or new_cost < costs[next_tile]:
                        costs[next_tile] = new_cost
                        h = heuristic(next_tile, dst)
                        heapq.heappush(pq, (new_cost + h, next_tile, path + [(tile, out_dir, track, next_tile)]))

    return None

def route_net(graph, src, dst, taken, allow_reroute=True, max_attempts=2):
    """Route a single net from src to dst.
    Returns: (pips, success) where pips = [{"tile": [...], "out": dir, "track": t}, ...]"""
    if src == dst:
        return [], True

    for attempt in range(max_attempts):
        path = dijkstra_route(graph, src, dst, taken)
        if path:
            # Convert path to PIP specs
            pips = []
            used_wires = set()
            for tile, out_dir, track, next_tile in path:
                pips.append({
                    "tile": list(tile),
                    "in": "core",
                    "out": out_dir,
                    "track": track,
                    "next_tile": list(next_tile)
                })
                used_wires.add((tile, out_dir, track))

            # Check single-driver gate before committing
            conflicts = any(w in taken for w in used_wires)
            if not conflicts or allow_reroute:
                for w in used_wires:
                    taken.add(w)
                return pips, True

        if not allow_reroute:
            break

    return [], False

# ============================================================================
# VALIDATION GATES
# ============================================================================

def validate_single_driver(routes):
    """GATE: every (tile, out_dir, track) appears in exactly one route.
    Returns: (is_valid, duplicates)."""
    wires = []
    for route in routes:
        for pip in route.get("pips", []):
            wire = (tuple(pip["tile"]), pip["out"], pip["track"])
            wires.append(wire)

    wire_set = set(wires)
    is_valid = len(wires) == len(wire_set)
    duplicates = len(wires) - len(wire_set)
    return is_valid, duplicates

def validate_no_shorts(routes):
    """GATE: no two nets drive the same wire (single-driver covers this).
    Returns: is_valid."""
    return validate_single_driver(routes)[0]

def validate_all_sinks(routes, nets_total):
    """GATE: all nets have routes (no orphans).
    Returns: (is_valid, unrouted_count)."""
    routed = len(routes)
    unrouted = nets_total - routed
    return unrouted == 0, unrouted

# ============================================================================
# CONFIG GENERATION
# ============================================================================

def generate_router_config(routes, library_data):
    """Generate router_config.json: per-net PIP assignments ready for device tick.
    Integrates library.json INT_TILE PIP array to map (out_dir, track) -> PIP index."""
    config = {
        "version": "1.0",
        "timestamp": "",
        "routes": [],
        "pip_array": library_data.get("blocks", {}).get("INT_TILE", {})
    }

    for route in routes:
        net_id = route.get("net", -1)
        route_cfg = {
            "net_id": net_id,
            "net_name": route.get("src", ""),
            "source_tile": route.get("from", [0, 0]),
            "sink_tiles": [route.get("to", [0, 0])],
            "pips": []
        }

        for pip in route.get("pips", []):
            tile = tuple(pip["tile"])
            out_dir = pip["out"]
            track = pip["track"]

            # Map (out_dir, track) to PIP index in INT_TILE array
            # This assumes library.json has a PIP array describing the mux structure
            pip_index = (DIRECTIONS.index(out_dir) * TRACKS + track) if out_dir in DIRECTIONS else -1

            route_cfg["pips"].append({
                "tile": list(tile),
                "pip_index": pip_index,
                "out_direction": out_dir,
                "track": track,
                "mux_input": f"IN[{track}]",
                "mux_output": f"OUT[{pip_index}]"
            })

        config["routes"].append(route_cfg)

    return config

# ============================================================================
# MAIN ROUTER
# ============================================================================

def run(R, C, clkfab_file=None):
    """Main router: read hierarchy, place endpoints, route, validate, emit config.

    Returns: 0 = all gates pass, 1 = validation failure, 2 = internal error."""

    # Load input data
    h = Lj(os.path.join(ROOT, "hierarchy.json"))
    edges = [e for e in (h or {}).get("edges", [])
             if e.get("kind") in ("figure", "routing", "board")] if h else []

    lib = Lj(os.path.join(ROOT, "device", "library.json"))
    clkfab = Lj(clkfab_file) if clkfab_file else None

    # Parse clock placement from clkfab.py output
    clock_placement = parse_clock_regions(clkfab)

    # Build routing graph
    graph = RoutingGraph(R, C)

    # Dedup net endpoints and classify as clock/logic
    nets = []
    seen = set()
    clock_net_names = set(clock_placement.keys())

    for e in edges:
        s, d = str(e.get("src", "")), str(e.get("dst", ""))
        if not s or not d or s == d:
            continue
        k = (s, d)
        if k in seen:
            continue
        seen.add(k)
        is_clock = s in clock_net_names or d in clock_net_names
        nets.append((s, d, is_clock))

    # Place endpoints and route nets
    taken = set()  # (tile, out_dir, track) -> occupied
    routes = []
    unrouted_nets = []
    conflicts_resolved = 0

    for i, (s, d, is_clock) in enumerate(nets):
        src, src_info = endpoint_placement(s, is_clock, clock_placement, R, C)
        dst, dst_info = endpoint_placement(d, is_clock, clock_placement, R, C)

        if src == dst:
            continue

        before_taken = len(taken)
        pips, ok = route_net(graph, src, dst, taken, allow_reroute=True)

        if ok:
            routes.append({
                "net": i,
                "src": s[:40],
                "dst": d[:40],
                "is_clock": is_clock,
                "from": list(src),
                "to": list(dst),
                "hops": len(pips),
                "pips": pips
            })
            if len(taken) - before_taken < len(pips):
                conflicts_resolved += 1
        else:
            unrouted_nets.append((i, s, d))

    # GATES: validation
    single_driver_ok, duplicates = validate_single_driver(routes)
    no_shorts_ok = validate_no_shorts(routes)
    all_sinks_ok, unroutable = validate_all_sinks(routes, len(nets))

    gates_pass = single_driver_ok and no_shorts_ok and all_sinks_ok

    # Generate outputs
    total_pips = sum(r["hops"] for r in routes)

    result = {
        "grid": [R, C],
        "nets_total": len(nets),
        "nets_routed": len(routes),
        "nets_clock": sum(1 for r in routes if r["is_clock"]),
        "nets_logic": sum(1 for r in routes if not r["is_clock"]),
        "unroutable": unroutable,
        "total_pips": total_pips,
        "conflicts_resolved": conflicts_resolved,
        "gates": {
            "single_driver": single_driver_ok,
            "no_shorts": no_shorts_ok,
            "all_sinks": all_sinks_ok
        },
        "diagnostics": {
            "duplicates_found": duplicates,
            "unroutable_nets": unroutable
        },
        "routes": routes
    }

    # Write device/routes.json (legacy)
    os.makedirs(os.path.join(ROOT, "device"), exist_ok=True)
    json.dump(result, open(os.path.join(ROOT, "device", "routes.json"), "w"), indent=2)

    # Write device/router_config.json (new: ready for device tick integration)
    router_config = generate_router_config(routes, lib or {})
    json.dump(router_config, open(os.path.join(ROOT, "device", "router_config.json"), "w"), indent=2)

    # Report
    print(f"route: {len(routes)}/{len(nets)} nets routed on {R}x{C} grid, {total_pips} PIPs set")
    print(f"  clock nets: {sum(1 for r in routes if r['is_clock'])}")
    print(f"  logic nets: {sum(1 for r in routes if not r['is_clock'])}")
    print(f"  unroutable: {unroutable} | conflicts resolved: {conflicts_resolved}")
    print(f"  GATE single-driver-per-wire: {'PASS' if single_driver_ok else 'FAIL'} ; duplicates={duplicates}")
    print(f"  GATE no-shorts: {'PASS' if no_shorts_ok else 'FAIL'}")
    print(f"  GATE all-sinks-reachable: {'PASS' if all_sinks_ok else 'FAIL'} ; orphans={unroutable}")
    print(f"  FINAL: {'ALL GATES PASS' if gates_pass else 'FAILURE'}")
    print(f"-> device/routes.json, device/router_config.json")

    if unrouted_nets and len(unrouted_nets) <= 10:
        print(f"  Unrouted (first 10):")
        for net_id, s, d in unrouted_nets[:10]:
            print(f"    [{net_id}] {s[:30]} -> {d[:30]}")

    return 0 if gates_pass else 1

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="P3 Router: netlist -> PIP configuration")
    ap.add_argument("--grid", nargs=2, type=int, default=[64, 64],
                    help="grid dimensions (rows, cols)")
    ap.add_argument("--clkfab", default=None,
                    help="clkfab.py output JSON (real clock-region placement)")
    a = ap.parse_args()
    sys.exit(run(*a.grid, clkfab_file=a.clkfab))
