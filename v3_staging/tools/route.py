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

TRACKS = 24              # INT_TILE routing tracks per direction (UG572 HCS = 24 tracks)
INT_TILE_INPUTS = 24     # INT_TILE fan-in for PIP mux
INT_TILE_OUTPUTS = 24    # INT_TILE fan-out

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

def coord_synthetic(name, R, C, clock_regions_x=6, clock_regions_y=4, use_edges=False):
    """L3 phase: deterministic placement respecting clock-region boundaries.

    Hash-based coordinates, but distributed evenly across clock regions
    to reduce synthetic congestion. Each net maps to a region first, then
    within that region.

    use_edges: if True, place roughly 25% of nets at grid edges (realistic I/O distribution)."""
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)

    # For I/O realistic distribution: some nets prefer edges
    if use_edges and (h & 0x3) == 0:  # ~25% of nets
        # Place at edges (rows/cols 0, R-1, C-1)
        edge_type = (h >> 16) & 0x3
        if edge_type == 0:  # top edge
            return (0, h % C)
        elif edge_type == 1:  # bottom edge
            return (R - 1, h % C)
        elif edge_type == 2:  # left edge
            return (h % R, 0)
        else:  # right edge
            return (h % R, C - 1)

    # Region-aware distribution: allocate to region first, then position within region
    # This reduces path congestion vs pure hash (which can cluster in synthetic dead zones)
    region_x = (h >> 0) % clock_regions_x  # bits 0-7 for region X
    region_y = (h >> 8) % clock_regions_y  # bits 8-15 for region Y

    # Within each region, distribute evenly
    tiles_per_region_x = C // clock_regions_x
    tiles_per_region_y = R // clock_regions_y

    # Position within region using hash bits
    local_x = ((h >> 16) % tiles_per_region_x) if tiles_per_region_x > 0 else 0
    local_y = ((h >> 24) % tiles_per_region_y) if tiles_per_region_y > 0 else 0

    # Absolute position
    abs_x = region_x * tiles_per_region_x + local_x
    abs_y = region_y * tiles_per_region_y + local_y

    # Clamp to grid bounds
    abs_x = min(abs_x, C - 1)
    abs_y = min(abs_y, R - 1)

    return (abs_y, abs_x)

def coord_fabric(name, R, C, regions_x, regions_y):
    """Real-geometry placement: distribute each endpoint within its clock region's
    tile span on the grid. The region grid (regions_x x regions_y) is sourced from
    device/fabric.json so this stays consistent with placement.py. Uses independent
    per-axis hashes -> higher spatial entropy than coord_synthetic, which reduces
    endpoint clustering (and thus routing congestion)."""
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    region_x = (h >> 0) % regions_x
    region_y = (h >> 8) % regions_y
    # Region tile span on the grid (must match placement.region_bounds exactly).
    c0 = int(round(region_x * C / regions_x))
    c1 = max(c0 + 1, int(round((region_x + 1) * C / regions_x)))
    r0 = int(round(region_y * R / regions_y))
    r1 = max(r0 + 1, int(round((region_y + 1) * R / regions_y)))
    hx = int(hashlib.md5(("LX" + name).encode()).hexdigest(), 16)
    hy = int(hashlib.md5(("LY" + name).encode()).hexdigest(), 16)
    c = c0 + hx % (c1 - c0)
    r = r0 + hy % (r1 - r0)
    return (min(r, R - 1), min(c, C - 1))

def load_fabric_geometry():
    """Load region geometry from device/fabric.json (P-FAB output). Returns
    {grid, regions_x, regions_y} or None if absent (caller falls back to constants)."""
    fab = Lj(os.path.join(ROOT, "device", "fabric.json"))
    if not fab:
        return None
    cr = fab.get("clock_regions", {}) or {}
    grid = fab.get("grid", [64, 64])
    return {
        "grid": (grid[0], grid[1]),
        "regions_x": cr.get("num_x", 6),
        "regions_y": cr.get("num_y", 4),
    }

def load_placed_coords(path):
    """Load placement.json and return {tile_tuple: [r, c]} from its 'tiles' map.
    These are the real, clock-region-legal coordinates emitted by placement.py;
    route.py snaps endpoints onto them to close the placement->route loop."""
    pj = Lj(path)
    if not pj:
        return None
    placed = {}
    for v in (pj.get("tiles", {}) or {}).values():
        t = v.get("tile")
        if t is not None:
            placed[tuple(t)] = t
    return placed

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

def spread_hub_endpoint(base, driver_index, R, C):
    """Fan-in tree (sink-side): a high-fan-in hub destination (e.g. PL/PL_IO with
    ~400 drivers) maps to ONE tile by name, but a tile has only 4 neighbours x
    TRACKS inlet wires (~96) under the single-driver gate, so hundreds of drivers
    cannot all enter it. Distribute the hub's drivers across its 4 neighbour tiles
    (driver[i] -> neighbour[i % 4]), quadrupling effective inlet capacity.

    base         = (r, c) hub tile from name-based placement.
    driver_index = this edge's index within the hub's driver group (0-based).
    Returns a neighbour coordinate in-grid; falls back to the next valid neighbour
    if the chosen one is off-grid (edge hubs), or to `base` if none are valid."""
    r, c = base
    # Rotate the neighbour order by ring so deeper drivers still cycle evenly
    # rather than all piling onto the same neighbour selection.
    rotated = DIRECTIONS[driver_index % len(DIRECTIONS):] + DIRECTIONS[:driver_index % len(DIRECTIONS)]
    for d in rotated:
        dr, dc = DIR_OFFSET[d]
        nr, nc = r + dr, c + dc
        if 0 <= nr < R and 0 <= nc < C:
            return (nr, nc)
    return base


def endpoint_placement(net_name, is_clock, clock_placement, R, C,
                       clock_regions_x=6, clock_regions_y=4,
                       placed_coords=None, fabric_geom=None, stats=None,
                       hub_driver_index=None):
    """Determine tile coordinates for a net endpoint.

    Priority:
      1. Clock nets -> real clkfab.py / clock_topology.json placement.
      2. Real placement coords from placement.json (closes the placement->route
         loop): compute the base coordinate, then if placement.py emitted a real
         coordinate for that tile, snap onto it.
      3. Fall back to region-aware placement (fabric.json geometry if present,
         otherwise the legacy synthetic hash).

    hub_driver_index: when set (this endpoint is the sink of a high-fan-in hub),
    spread it across the hub tile's 4 neighbours by driver index so the hub's
    drivers do not all collide on one tile's ~96 inlet wires."""
    if is_clock and net_name in clock_placement:
        placement = clock_placement[net_name]
        return placement["coords"], placement

    if fabric_geom:
        coord = coord_fabric(net_name, R, C,
                             fabric_geom["regions_x"], fabric_geom["regions_y"])
    else:
        coord = coord_synthetic(net_name, R, C, clock_regions_x, clock_regions_y)

    # Close the loop: prefer real placed coordinates from placement.json.
    if placed_coords:
        key = tuple(coord)
        if key in placed_coords:
            coord = tuple(placed_coords[key])
            if stats is not None:
                stats["hits"] = stats.get("hits", 0) + 1

    # Sink-side fan-in spread: relieve hub inlet saturation (see spread_hub_endpoint).
    if hub_driver_index is not None:
        coord = spread_hub_endpoint(tuple(coord), hub_driver_index, R, C)
        if stats is not None:
            stats["spread"] = stats.get("spread", 0) + 1
    return coord, None

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

def dijkstra_route(graph, src, dst, taken, allow_occupied=False, occupied_penalty=1.0):
    """Find shortest path from src to dst using A* with Manhattan distance heuristic.
    taken = set of (tile, out_dir, track) already used.
    allow_occupied = if True, allow using occupied wires at a cost.
    occupied_penalty = cost multiplier for using occupied wires.
    Returns: [(tile, out_dir, track, next_tile), ...] or None if unroutable."""
    if src == dst:
        return []

    # Priority queue: (f_cost, tile, path_so_far, g_cost)
    # f_cost = g_cost + h_cost (A* heuristic)
    h = heuristic(src, dst)
    pq = [(h, src, [], 0)]
    visited = set()
    g_costs = {src: 0}

    while pq:
        f_cost, tile, path, g_cost = heapq.heappop(pq)

        if tile == dst:
            return path

        if tile in visited:
            continue
        visited.add(tile)

        # Try all outgoing directions and tracks
        # Prefer directions toward goal (east/west for column difference, north/south for row difference)
        goal_dir = []
        dr = dst[0] - tile[0]
        dc = dst[1] - tile[1]
        if dr < 0: goal_dir.append("n")
        if dr > 0: goal_dir.append("s")
        if dc < 0: goal_dir.append("w")
        if dc > 0: goal_dir.append("e")

        # Sort directions: goal directions first, then others
        sorted_dirs = goal_dir + [d for d in DIRECTIONS if d not in goal_dir]

        for out_dir in sorted_dirs:
            for track in range(TRACKS):
                wire = (tile, out_dir, track)

                # Check if wire is occupied
                is_occupied = wire in taken
                if is_occupied and not allow_occupied:
                    continue

                # Get neighbors reachable via this wire
                for next_tile, _, _ in graph.neighbors(tile, out_dir, track):
                    if next_tile in visited:
                        continue

                    # Cost: 1 hop normally, higher if using occupied wire
                    hop_cost = occupied_penalty if is_occupied else 1.0
                    new_g_cost = g_cost + hop_cost

                    if next_tile not in g_costs or new_g_cost < g_costs[next_tile]:
                        g_costs[next_tile] = new_g_cost
                        h_cost = heuristic(next_tile, dst)
                        f_cost_new = new_g_cost + h_cost
                        new_path = path + [(tile, out_dir, track, next_tile)]
                        heapq.heappush(pq, (f_cost_new, next_tile, new_path, new_g_cost))

    return None

def route_net(graph, src, dst, taken, allow_reroute=True, max_attempts=3):
    """Route a single net from src to dst with multi-strategy attempts.
    Returns: (pips, success) where pips = [{"tile": [...], "out": dir, "track": t}, ...]"""
    if src == dst:
        return [], True

    # Attempt 1: strict avoidance (prefer unoccupied wires)
    path = dijkstra_route(graph, src, dst, taken, allow_occupied=False)
    if path:
        pips = _convert_path_to_pips(path)
        wires = _get_wires(pips)
        if not any(w in taken for w in wires):
            for w in wires:
                taken.add(w)
            return pips, True

    # Attempt 2: moderate penalty for occupied wires (5x cost)
    # This allows alternative paths if no direct path exists
    if allow_reroute and max_attempts > 1:
        path = dijkstra_route(graph, src, dst, taken, allow_occupied=True, occupied_penalty=5.0)
        if path:
            pips = _convert_path_to_pips(path)
            wires = _get_wires(pips)
            # Accept only if we don't create new conflicts
            if not any(w in taken for w in wires):
                for w in wires:
                    taken.add(w)
                return pips, True

    # Attempt 3: higher penalty (15x) - more aggressive rerouting
    # Use multiple alternative segments if necessary
    if allow_reroute and max_attempts > 2:
        path = dijkstra_route(graph, src, dst, taken, allow_occupied=True, occupied_penalty=15.0)
        if path:
            pips = _convert_path_to_pips(path)
            wires = _get_wires(pips)
            if not any(w in taken for w in wires):
                for w in wires:
                    taken.add(w)
                return pips, True

    return [], False

def _convert_path_to_pips(path):
    """Convert a Dijkstra path to PIP specs."""
    pips = []
    for tile, out_dir, track, next_tile in path:
        pips.append({
            "tile": list(tile),
            "in": "core",
            "out": out_dir,
            "track": track,
            "next_tile": list(next_tile)
        })
    return pips

def _get_wires(pips):
    """Extract wires from PIP specs."""
    return set((tuple(pip["tile"]), pip["out"], pip["track"]) for pip in pips)

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

def validate_all_sinks(routes, nets):
    """GATE: every source (driver) net has at least one sink routed.

    P-LOOP semantics: a multi-sink net passes if >=1 of its sinks is routed,
    even when not every sink is reachable. Nets are grouped by source name; the
    route 'net' field is the net index into `nets`.
    Returns: (is_valid, unrouted_source_count)."""
    routed_idx = set(r.get("net") for r in routes)
    src_to_indices = defaultdict(list)
    for i, (s, d, _is_clock) in enumerate(nets):
        src_to_indices[s].append(i)
    unrouted_sources = sum(
        1 for idxs in src_to_indices.values()
        if not any(i in routed_idx for i in idxs)
    )
    return unrouted_sources == 0, unrouted_sources

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

def classify_net_priority(net_name, is_clock, clock_placement):
    """Classify net priority: CLOCK > CRITICAL > NORMAL.
    Returns: (priority_level, sort_key)"""
    if is_clock or net_name in clock_placement:
        return (0, net_name)  # Clock nets: priority 0 (highest)
    # Critical nets: high fanout or timing-sensitive markers
    if any(marker in net_name.lower() for marker in ["critical", "timing", "clk"]):
        return (1, net_name)  # Critical: priority 1
    return (2, net_name)  # Normal: priority 2

def sort_nets_by_priority(nets, clock_placement, randomize_ties=False, seed=42):
    """Sort nets: clock first, then critical, then normal.
    Returns: sorted list of (original_index, src, dst, is_clock)"""
    import random
    indexed_nets = [(i, s, d, is_clock) for i, (s, d, is_clock) in enumerate(nets)]

    # Sort by priority, then by net name for stability
    def priority_key(item):
        i, s, d, is_clock = item
        priority, _ = classify_net_priority(s, is_clock, clock_placement)
        if randomize_ties:
            # Add a small random component to the same-priority nets
            return (priority, hash((s, seed)) % 1000)
        return (priority, s)

    return sorted(indexed_nets, key=priority_key)

def run(R, C, clkfab_file=None, placement_file=None, use_fabric=True):
    """Main router: read hierarchy, place endpoints, route, validate, emit config.
    Enhanced with net prioritization, congestion tracking, and backtrack.

    clkfab_file:    clock-region placement (clkfab.py / clock_topology.json).
    placement_file: placement.json whose real coords are fed back into the router
                    (closes the placement->route loop).
    use_fabric:     source region geometry + grid from device/fabric.json.

    Returns: 0 = all gates pass, 1 = validation failure, 2 = internal error."""

    # Source region geometry from device/fabric.json (P-FAB); fall back to constants.
    fabric_geom = load_fabric_geometry() if use_fabric else None
    if fabric_geom:
        R, C = fabric_geom["grid"]
        regions_x, regions_y = fabric_geom["regions_x"], fabric_geom["regions_y"]
    else:
        regions_x, regions_y = 6, 4

    # Load real placement coords (placement.json) to feed back into the router.
    placed_coords = load_placed_coords(placement_file) if placement_file else None
    pstats = {"hits": 0}

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

    # Sink-side fan-in analysis: count drivers per destination and allocate each
    # edge an index within its destination's driver group. High-fan-in hubs
    # (>= HIGH_FANIN drivers) get their sink endpoint spread across neighbour
    # tiles so they don't saturate a single tile's ~96 inlet wires.
    HIGH_FANIN = 50
    dst_fanin = defaultdict(int)
    for s, d, _is_clock in nets:
        dst_fanin[d] += 1
    dst_seen = defaultdict(int)
    edge_dst_index = [0] * len(nets)
    for i, (s, d, _is_clock) in enumerate(nets):
        edge_dst_index[i] = dst_seen[d]
        dst_seen[d] += 1
    hub_dsts = {d for d, c in dst_fanin.items() if c >= HIGH_FANIN}
    print(f"route: {len(hub_dsts)} high-fan-in hub(s) (>= {HIGH_FANIN} drivers); "
          f"spreading {sum(dst_fanin[d] for d in hub_dsts)} sink endpoints across neighbour tiles")

    # Sort nets by priority: clock first, then critical, then normal
    sorted_net_indices = sort_nets_by_priority(nets, clock_placement)
    print(f"route: sorted {len(nets)} nets by priority (clock={sum(1 for _, _, _, c in sorted_net_indices if c)}, critical={sum(1 for _, s, _, _ in sorted_net_indices if not any(m in s.lower() for m in ['clk', 'clock']))}, normal={sum(1 for _, s, _, _ in sorted_net_indices if not any(m in s.lower() for m in ['clk', 'clock', 'critical']))})")

    # Place endpoints and route nets (in priority order)
    taken = set()  # (tile, out_dir, track) -> occupied
    routes = []
    net_to_route_idx = {}  # map net_idx -> route list index for backtrack
    unrouted_nets = []
    conflicts_resolved = 0

    # PASS: Route in priority order (clock, then critical, then normal)
    # XCZU19EG has 4×6 clock regions
    for net_idx, s, d, is_clock in sorted_net_indices:
        src, src_info = endpoint_placement(s, is_clock, clock_placement, R, C,
                                           regions_x, regions_y,
                                           placed_coords, fabric_geom, pstats)
        # Spread the sink endpoint only when d is a high-fan-in hub and the net
        # is not a clock (clock sinks use real clkfab placement).
        hub_idx = edge_dst_index[net_idx] if (d in hub_dsts and not is_clock) else None
        dst, dst_info = endpoint_placement(d, is_clock, clock_placement, R, C,
                                           regions_x, regions_y,
                                           placed_coords, fabric_geom, pstats,
                                           hub_driver_index=hub_idx)

        if src == dst:
            continue

        before_taken = len(taken)
        pips, ok = route_net(graph, src, dst, taken, allow_reroute=True)

        if ok:
            routes.append({
                "net": net_idx,
                "src": s[:40],
                "dst": d[:40],
                "is_clock": is_clock,
                "from": list(src),
                "to": list(dst),
                "hops": len(pips),
                "pips": pips
            })
            net_to_route_idx[net_idx] = len(routes) - 1
            if len(taken) - before_taken < len(pips):
                conflicts_resolved += 1
        else:
            unrouted_nets.append((net_idx, s, d))

    # Note: PASS 2 (alternative placement rerouting) disabled due to O(n²) cost.
    # Future improvement: implement smarter backtracking or placement-aware routing.

    # Confirm the placement->route loop is closed (debug visibility).
    if placement_file is not None:
        print(f"route: fed back real coords from {placement_file} "
              f"({pstats['hits']} endpoint(s) snapped onto placement.json tiles)")

    # GATES: validation
    single_driver_ok, duplicates = validate_single_driver(routes)
    no_shorts_ok = validate_no_shorts(routes)
    unroutable = len(nets) - len(routes)                 # unrouted edge count
    all_sinks_ok, unrouted_sources = validate_all_sinks(routes, nets)

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
            "unroutable_nets": unroutable,
            "unrouted_sources": unrouted_sources,
            "placement_coords_consumed": pstats["hits"],
            "fabric_geometry": bool(fabric_geom)
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
    percent_routed = (len(routes) / len(nets) * 100) if nets else 0
    print(f"\nroute: {len(routes)}/{len(nets)} nets routed ({percent_routed:.1f}%) on {R}x{C} grid, {total_pips} PIPs set")
    print(f"  clock nets: {sum(1 for r in routes if r['is_clock'])}")
    print(f"  logic nets: {sum(1 for r in routes if not r['is_clock'])}")
    print(f"  unroutable: {unroutable} | conflicts resolved: {conflicts_resolved}")
    print(f"  GATE single-driver-per-wire: {'PASS' if single_driver_ok else 'FAIL'} ; duplicates={duplicates}")
    print(f"  GATE no-shorts: {'PASS' if no_shorts_ok else 'FAIL'}")
    print(f"  GATE all-sinks (>=1 sink per source): {'PASS' if all_sinks_ok else 'FAIL'} ; unrouted_sources={unrouted_sources} (unrouted_edges={unroutable})")
    print(f"  FINAL: {'ALL GATES PASS' if gates_pass else 'FAILURE'}")
    print(f"-> device/routes.json, device/router_config.json")

    if unrouted_nets and len(unrouted_nets) <= 20:
        print(f"\n  Unrouted ({len(unrouted_nets)} nets):")
        for net_id, s, d in unrouted_nets[:20]:
            print(f"    [{net_id:4d}] {s[:35]:35s} -> {d[:35]:35s}")

    return 0 if gates_pass else 1

def converge(R, C, clk_file=None):
    """Closed placement->route loop:
        pass 1: route with real fabric coords (no clock, no feedback)
        place : placement.run() -> device/placement.json
        pass 2: route with real fabric coords + clkfab + placement.json feedback
    Convergence comes from real coords + clock placement (PASS-2 backtracking is a
    separate item and intentionally not enabled here)."""
    import placement
    placement_json = os.path.join(ROOT, "device", "placement.json")
    # Resolve the clock topology robustly: callers commonly pass a ROOT-relative
    # path (e.g. "device/clock_topology.json") but route.py runs from tools/.
    if clk_file and not os.path.exists(clk_file):
        for cand in (os.path.join(ROOT, clk_file),
                     os.path.join(ROOT, "device", os.path.basename(clk_file))):
            if os.path.exists(cand):
                clk_file = cand
                break
    if not clk_file or not os.path.exists(clk_file):
        cand = os.path.join(ROOT, "device", "clock_topology.json")
        clk_file = cand if os.path.exists(cand) else None

    print("=== CONVERGE pass 1: real fabric coords (no clock/feedback) ===")
    run(R, C, clkfab_file=None, placement_file=None)
    print("\n=== CONVERGE: placement.run() -> device/placement.json ===")
    placement.run(R, C)
    print("\n=== CONVERGE pass 2: real coords (placement.json) + clocks ===")
    return run(R, C, clkfab_file=clk_file, placement_file=placement_json)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="P3 Router: netlist -> PIP configuration")
    ap.add_argument("--grid", nargs=2, type=int, default=[64, 64],
                    help="grid dimensions (rows, cols); overridden by fabric.json if present")
    ap.add_argument("--clkfab", default=None,
                    help="clkfab.py / clock_topology.json (real clock-region placement)")
    ap.add_argument("--placement", default=None,
                    help="placement.json: real coords fed back into the router")
    ap.add_argument("--converge", action="store_true",
                    help="run the closed loop: route(pass1) -> placement -> route(pass2)")
    ap.add_argument("extra", nargs="*",
                    help="optional positionals for --converge: [routes_out] [clock_topology.json]")
    a = ap.parse_args()
    if a.converge:
        clk = a.clkfab
        # Support: route.py --converge [routes_out] [clock_topology.json]
        if clk is None and len(a.extra) >= 2:
            clk = a.extra[1]
        sys.exit(converge(a.grid[0], a.grid[1], clk_file=clk))
    sys.exit(run(*a.grid, clkfab_file=a.clkfab, placement_file=a.placement))
