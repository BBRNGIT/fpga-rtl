#!/usr/bin/env python3
"""
derive.py — Query-based derivation from cache.db (T1.2).

Extracts primitives, ports, attributes, and connections directly from the SQLite
cache database (cache.db, built by cachedb.py from cached extraction).

PRINCIPLE: Every fact cites a source (doc + page). Derive by querying table
signatures (not text search). Maintain conservation: placed + residual == total.

KNOWN ISSUE (T1.2 MVP): Primitive classification heuristic (uppercase, short,
alphanumeric) over-extracts internal signal names (CEB, CLK, etc.) as primitives.
Solution: refine by matching document context (restrict to UG974, etc.) or use
known UNISIM name list.

Output: primitives.json (query-derived catalog with full citations)
Usage: python3 derive.py [--db cache.db] [--out primitives.json] [--stats]
"""
import sqlite3, json, sys, os, re, argparse
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.path.join(ROOT, "cache.db")

# Table signature patterns (regex) -> data type
SIGS = {
    # Port descriptions (multiple variants)
    r"^port\|direction\|width\|function$": "ports_basic",
    r"^port\|direction\|width$": "ports_widthonly",
    r"^port\|dir\|clock domain\|description$": "ports_clk",
    r"^port\|direction\|width\|domain\|sense\|handling if unused\|function$": "ports_full",
    # Attribute/DRP descriptions
    r"^attribute\|type\|allowed values\|default\|description$": "attrs_full",
    r"^attribute\|type\|description$": "attrs_basic",
    r"^drp address": "drp",
    # Instantiation
    r"^instantiation\|yes$": "instantiation",
}

def match_sig(sig):
    """Return the category for a table signature."""
    for pattern, cat in SIGS.items():
        if re.search(pattern, sig):
            return cat
    return None

def connect_db(path):
    """Connect to cache.db."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"cache.db not found at {path}")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def find_primitive_for_table(conn, doc, page, tidx):
    """Find the primitive name for a table by looking up headings on the same page.

    Filters to likely UNISIM primitive names: all-uppercase, <= 25 chars, from library docs.
    """
    # Query headings on the same page
    cur = conn.execute("""
        SELECT label FROM headings WHERE doc = ? AND page = ?
        ORDER BY hidx DESC LIMIT 10
    """, (doc, page))

    headings = [row[0] for row in cur]

    # Use the most recent heading as the primitive name
    # Filter: must be from a library doc, be uppercase, be short, not be a section marker
    for heading in headings:
        heading = str(heading or "").strip()

        # Skip structural headings
        if any(x in heading.lower() for x in ["chapter", "contents", "section", "page",
                                                "table", "figure", "note", "description"]):
            continue

        # Primitive names should be reasonably short, alphanumeric+underscore
        if not heading or len(heading) > 25:
            continue

        # Should contain uppercase letters (UNISIM names are uppercase)
        if not any(c.isupper() for c in heading):
            continue

        # Should be alphanumeric + underscore only
        if not re.match(r'^[A-Z][A-Z0-9_]*$', heading):
            continue

        return heading

    return None

def query_port_tables(conn):
    """Query all port-description tables from cache.db and associate with primitives.

    Returns: {primitive_name: [{name: ..., dir: ..., width: ..., source: ...}, ...]}
    """
    prims = defaultdict(list)

    # Find all port tables
    cur = conn.execute("""
        SELECT id, doc, page, tidx, header_sig FROM tables
        WHERE header_sig LIKE '%port%' AND header_sig LIKE '%direction%'
        ORDER BY doc, page, tidx
    """)

    for row in cur:
        table_id, doc, page, tidx, sig = row['id'], row['doc'], row['page'], row['tidx'], row['header_sig']
        cite = f"{doc} p{page}"

        # Find which primitive this table belongs to
        prim_name = find_primitive_for_table(conn, doc, page, tidx)
        if not prim_name:
            prim_name = f"_UNKNOWN_{doc}_{page}_{tidx}"

        # Get the rows for this table
        tcur = conn.execute(f"SELECT * FROM table_rows WHERE table_id = {table_id} ORDER BY ridx")
        all_rows = list(tcur)

        if not all_rows:
            continue

        # Parse header
        header_row = json.loads(all_rows[0]['cells_json'])
        header = [str(c or "").strip().lower() for c in header_row]

        # Find column indices
        port_col = next((i for i, h in enumerate(header) if h == "port" or h == "port name"), None)
        dir_col = next((i for i, h in enumerate(header) if "direction" in h or h == "dir"), None)
        width_col = next((i for i, h in enumerate(header) if h == "width"), None)

        if port_col is None or dir_col is None:
            continue

        # Extract ports
        for trow in all_rows[1:]:  # Skip header
            cells = json.loads(trow['cells_json'])
            if len(cells) <= max(port_col, dir_col):
                continue

            pname = str(cells[port_col] or "").strip().replace("\n", " ").split()[0]
            pdir = str(cells[dir_col] or "").strip().lower()
            pwidth = None

            if not pname or pname.startswith("(") or pname.startswith("["):
                continue

            # Normalize direction
            if "out" in pdir:
                pdir = "out"
            elif "inout" in pdir:
                pdir = "inout"
            else:
                pdir = "in"

            # Extract width
            if width_col is not None and width_col < len(cells):
                wmatch = re.match(r'^[\s<\[]*(\d+)', cells[width_col] or "")
                if wmatch:
                    pwidth = int(wmatch.group(1))

            port_dict = {"name": pname, "dir": pdir, "source": cite}
            if pwidth is not None:
                port_dict["width"] = pwidth

            prims[prim_name].append(port_dict)

    return dict(prims)

def query_attribute_tables(conn):
    """Query attribute/parameter tables from cache.db and associate with primitives.

    Returns: {primitive_name: [{name: ..., type: ..., default: ..., source: ...}, ...]}
    """
    attrs = defaultdict(list)

    # Find all attribute tables
    cur = conn.execute("""
        SELECT id, doc, page, tidx, header_sig FROM tables
        WHERE (header_sig LIKE '%attribute%' AND header_sig NOT LIKE '%drp%')
        ORDER BY doc, page, tidx
    """)

    for row in cur:
        table_id, doc, page, tidx, sig = row['id'], row['doc'], row['page'], row['tidx'], row['header_sig']
        cite = f"{doc} p{page}"

        # Find which primitive this table belongs to
        prim_name = find_primitive_for_table(conn, doc, page, tidx)
        if not prim_name:
            prim_name = f"_UNKNOWN_{doc}_{page}_{tidx}"

        # Get rows for this table
        tcur = conn.execute(f"SELECT * FROM table_rows WHERE table_id = {table_id} ORDER BY ridx")
        all_rows = list(tcur)

        if not all_rows:
            continue

        # Parse header
        header_row = json.loads(all_rows[0]['cells_json'])
        header = [str(c or "").strip().lower() for c in header_row]

        # Find column indices
        attr_col = next((i for i, h in enumerate(header) if "attribute" in h), None)
        type_col = next((i for i, h in enumerate(header) if h == "type"), None)
        default_col = next((i for i, h in enumerate(header) if h == "default"), None)

        if attr_col is None:
            continue

        # Extract attributes
        for trow in all_rows[1:]:
            cells = json.loads(trow['cells_json'])
            if len(cells) <= attr_col:
                continue

            # Clean up newlines and extra whitespace
            aname = str(cells[attr_col] or "").strip().replace("\n", " ")
            aname = re.sub(r'\s+', ' ', aname)  # Collapse multiple spaces

            if not aname or aname.startswith("("):
                continue

            atype = str(cells[type_col] or "").strip() if type_col and type_col < len(cells) else ""
            adefault = str(cells[default_col] or "").strip() if default_col and default_col < len(cells) else ""

            attr_dict = {"name": aname, "source": cite}
            if atype:
                attr_dict["type"] = atype
            if adefault:
                attr_dict["default"] = adefault

            attrs[prim_name].append(attr_dict)

    return dict(attrs)

def build_catalog(conn):
    """Build the complete primitive catalog from cache.db.

    Returns: {primitive_name: {ports: [...], attributes: [...], source: cite}}
    """
    catalog = {}
    ledger = {"total_ports": 0, "total_attrs": 0, "total_prims": 0, "pending": 0}

    print("[derive] building catalog from cache.db...")

    ports = query_port_tables(conn)
    attrs = query_attribute_tables(conn)

    # Merge ports and attributes by primitive
    all_prims = set(ports.keys()) | set(attrs.keys())

    for prim_name in sorted(all_prims):
        prim_ports = ports.get(prim_name, [])
        prim_attrs = attrs.get(prim_name, [])

        # Use first citation as source
        source = None
        if prim_ports:
            source = prim_ports[0].get("source")
        elif prim_attrs:
            source = prim_attrs[0].get("source")

        if not source:
            source = "unknown"

        catalog[prim_name] = {
            "name": prim_name,
            "ports": prim_ports,
            "attributes": prim_attrs,
            "source": source
        }

        ledger["total_ports"] += len(prim_ports)
        ledger["total_attrs"] += len(prim_attrs)

        # Track pending (primitives with no ports/attrs)
        if not prim_ports and not prim_attrs:
            ledger["pending"] += 1
        else:
            ledger["total_prims"] += 1

    print(f"[derive] found {len(ports)} port collections, {len(attrs)} attribute collections")
    print(f"[derive] derived {ledger['total_prims']} primitives with data, "
          f"{ledger['pending']} pending ({ledger['total_ports']} ports, {ledger['total_attrs']} attrs)")

    return catalog, ledger

def main():
    ap = argparse.ArgumentParser(description="Query-based derivation from cache.db")
    ap.add_argument("--db", default=DB, help="Path to cache.db")
    ap.add_argument("--out", default=os.path.join(ROOT, "primitives.json"), help="Output file")
    ap.add_argument("--stats", action="store_true", help="Print statistics only")
    args = ap.parse_args()

    conn = connect_db(args.db)

    catalog, ledger = build_catalog(conn)

    if args.stats:
        print(f"[derive] conservation: {ledger['total_prims']} placed, "
              f"{ledger['pending']} pending (total {ledger['total_prims'] + ledger['pending']})")
        print(f"[derive] ports: {ledger['total_ports']}, attributes: {ledger['total_attrs']}")
        return

    # Write output
    with open(args.out, 'w') as f:
        json.dump(catalog, f, indent=2)

    print(f"[derive] wrote {args.out} ({len(catalog)} primitives)")

    conn.close()

if __name__ == "__main__":
    main()
