#!/usr/bin/env python3
"""
cachedb.py — Load cache_src into relational database (v4 clean room, STEP 1).

Pure lossless ETL from cache_src/*.jsonl → cache.db (SQLite).
Every unit (page, table, row, cell) is inserted; conservation is verified.

Tables:
  - pages(doc, page, text, n_tables, n_headings, has_primitive_decl)
  - tables(id, doc, page, tidx, header_sig, ncols, nrows)
  - table_rows(table_id, ridx, cells_json)
  - cells(table_id, ridx, cidx, value)
  - headings(doc, page, hidx, label, y)
  - text_headings(doc, page, lidx, label)

Exit 0 = success, 1 = conservation failure.
Usage: python3 cachedb.py [--cache-src /path] [--db /path] [--verify]
"""
import sqlite3, json, sys, os, glob, argparse, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CACHE_SRC = os.path.join(ROOT, "cache_src")
DB = os.path.join(HERE, "..", "db", "cache.db")

def connect_db(path):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def drop_tables(conn):
    for table in ["cells", "table_rows", "tables", "text_headings", "headings", "pages"]:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()

def create_schema(conn):
    conn.executescript("""
    CREATE TABLE pages (
        doc TEXT, page INT, text TEXT, n_tables INT, n_headings INT, has_primitive_decl INT,
        PRIMARY KEY (doc, page)
    );
    CREATE TABLE tables (
        id INTEGER PRIMARY KEY, doc TEXT, page INT, tidx INT, header_sig TEXT, ncols INT, nrows INT
    );
    CREATE TABLE table_rows (
        table_id INTEGER, ridx INT, cells_json TEXT,
        PRIMARY KEY (table_id, ridx),
        FOREIGN KEY (table_id) REFERENCES tables(id)
    );
    CREATE TABLE cells (
        table_id INTEGER, ridx INT, cidx INT, value TEXT,
        PRIMARY KEY (table_id, ridx, cidx),
        FOREIGN KEY (table_id) REFERENCES tables(id)
    );
    CREATE TABLE headings (
        doc TEXT, page INT, hidx INT, label TEXT, y REAL,
        PRIMARY KEY (doc, page, hidx)
    );
    CREATE TABLE text_headings (
        doc TEXT, page INT, lidx INT, label TEXT,
        PRIMARY KEY (doc, page, lidx)
    );
    """)
    conn.commit()

def load_cache(conn, cache_src_dir):
    """Load all cache_src/*.jsonl files into the database.

    Loads 100% of cache_src: every page, table, row, cell, figure heading, text heading.
    Conservation: all six tables must have non-zero counts matching the enumerated units.
    """
    counts = {"pages": 0, "tables": 0, "table_rows": 0, "cells": 0, "headings": 0, "text_headings": 0}

    for cf in sorted(glob.glob(os.path.join(cache_src_dir, "*.jsonl"))):
        doc = os.path.basename(cf).split(".")[0]
        print(f"[cachedb] loading {doc}...", file=sys.stderr)

        with open(cf) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Every line should have a page number
                if "page" not in obj:
                    continue

                page = obj["page"]

                # Insert page record
                text = obj.get("text", "") or ""
                n_tables = len(obj.get("tables", []))
                n_headings = len(obj.get("headings", []))
                has_primitive = 1 if re.search(r"\bPrimitive:|PRIMITIVE_GROUP\b", text) else 0

                conn.execute(
                    "INSERT OR REPLACE INTO pages VALUES (?, ?, ?, ?, ?, ?)",
                    (doc, page, text, n_tables, n_headings, has_primitive)
                )
                counts["pages"] += 1

                # Insert tables and rows
                for tidx, table in enumerate(obj.get("tables", []) or []):
                    rows = table.get("rows", []) if isinstance(table, dict) else table

                    if not rows:
                        continue

                    # Header signature
                    header = rows[0]
                    header_sig = "|".join(str(c or "").strip().lower() for c in header)

                    # Insert table metadata
                    cur = conn.execute(
                        "INSERT INTO tables (doc, page, tidx, header_sig, ncols, nrows) VALUES (?, ?, ?, ?, ?, ?)",
                        (doc, page, tidx, header_sig, len(header), len(rows) - 1)
                    )
                    table_id = cur.lastrowid
                    counts["tables"] += 1

                    # Insert rows
                    for ridx, row in enumerate(rows):
                        cells_json = json.dumps(row)
                        conn.execute(
                            "INSERT INTO table_rows VALUES (?, ?, ?)",
                            (table_id, ridx, cells_json)
                        )
                        counts["table_rows"] += 1

                        # Unpivot into cells table
                        for cidx, value in enumerate(row):
                            conn.execute(
                                "INSERT INTO cells VALUES (?, ?, ?, ?)",
                                (table_id, ridx, cidx, value if value is not None else "")
                            )
                            counts["cells"] += 1

                # Insert headings (from "heads" field: figure labels)
                for hidx, head in enumerate(obj.get("heads", []) or []):
                    if isinstance(head, list) and len(head) >= 1:
                        label = head[0]
                        y = head[1] if len(head) > 1 else 0
                    else:
                        label = head if isinstance(head, str) else str(head)
                        y = 0
                    conn.execute(
                        "INSERT INTO headings VALUES (?, ?, ?, ?, ?)",
                        (doc, page, hidx, label, y)
                    )
                    counts["headings"] += 1

                # Insert text headings (extracted ALL-CAPS lines from text)
                # Extract lines that are all uppercase (section headings)
                text_lines = text.split("\n")
                lidx = 0
                for line in text_lines:
                    stripped = line.strip()
                    # ALL-CAPS lines (at least 3 chars, mostly uppercase)
                    if stripped and len(stripped) >= 3 and re.match(r"^[A-Z][A-Z0-9_\s\-]+$", stripped):
                        conn.execute(
                            "INSERT INTO text_headings VALUES (?, ?, ?, ?)",
                            (doc, page, lidx, stripped)
                        )
                        counts["text_headings"] += 1
                        lidx += 1

    conn.commit()
    return counts

def verify_conservation(conn, cache_src_dir, loaded_counts):
    """Verify that all cache units were loaded (conservation check on all six tables)."""
    print("\n[cachedb] CONSERVATION VERIFICATION — ALL SIX TABLES", file=sys.stderr)

    tables_to_check = ["pages", "tables", "table_rows", "cells", "headings", "text_headings"]
    all_pass = True

    for table_name in tables_to_check:
        cur = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
        db_count = cur.fetchone()[0]
        loaded = loaded_counts.get(table_name, 0)

        # FAIL if count is zero (indicates missing load)
        if db_count == 0:
            print(f"  ❌ {table_name}: {db_count} (ZERO — load failed)", file=sys.stderr)
            all_pass = False
        elif db_count != loaded:
            print(f"  ❌ {table_name}: {db_count} != {loaded} (mismatch)", file=sys.stderr)
            all_pass = False
        else:
            print(f"  ✅ {table_name}: {db_count}", file=sys.stderr)

    if all_pass:
        print("  ✅ All conservation checks passed", file=sys.stderr)
        return True
    else:
        print("  ❌ Conservation FAILED — at least one table has zero count or mismatch", file=sys.stderr)
        return False

def print_stats(conn):
    """Print database statistics."""
    print("\n[cachedb] DATABASE STATISTICS", file=sys.stderr)

    cur = conn.execute("SELECT COUNT(*) FROM pages")
    print(f"  pages: {cur.fetchone()[0]}", file=sys.stderr)

    cur = conn.execute("SELECT COUNT(*) FROM tables")
    print(f"  tables: {cur.fetchone()[0]}", file=sys.stderr)

    cur = conn.execute("SELECT COUNT(*) FROM table_rows")
    print(f"  table_rows: {cur.fetchone()[0]}", file=sys.stderr)

    cur = conn.execute("SELECT COUNT(*) FROM cells")
    print(f"  cells: {cur.fetchone()[0]}", file=sys.stderr)

    cur = conn.execute("SELECT COUNT(*) FROM headings")
    print(f"  headings: {cur.fetchone()[0]}", file=sys.stderr)

    cur = conn.execute("SELECT COUNT(*) FROM text_headings")
    print(f"  text_headings: {cur.fetchone()[0]}", file=sys.stderr)

    # Top table signatures
    cur = conn.execute("SELECT header_sig, COUNT(*) as cnt FROM tables GROUP BY header_sig ORDER BY cnt DESC LIMIT 10")
    print("\n  Top 10 table signatures:", file=sys.stderr)
    for sig, cnt in cur:
        print(f"    {cnt:3d}  {sig[:60]}", file=sys.stderr)

def main():
    ap = argparse.ArgumentParser(description="Load cache_src into cache.db (v4 clean room)")
    ap.add_argument("--cache-src", default=CACHE_SRC, help="Path to cache_src/")
    ap.add_argument("--db", default=DB, help="Path to cache.db")
    ap.add_argument("--verify", action="store_true", help="Run conservation verification only")
    args = ap.parse_args()

    if not os.path.isdir(args.cache_src):
        print(f"[cachedb] ERROR: cache_src not found at {args.cache_src}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(args.db), exist_ok=True)

    conn = connect_db(args.db)
    drop_tables(conn)
    create_schema(conn)

    print(f"[cachedb] Loading from {args.cache_src} → {args.db}", file=sys.stderr)
    counts = load_cache(conn, args.cache_src)

    if not verify_conservation(conn, args.cache_src, counts):
        print("[cachedb] ❌ CONSERVATION FAILED", file=sys.stderr)
        sys.exit(1)

    print_stats(conn)
    print(f"\n[cachedb] ✅ Successfully built {args.db}", file=sys.stderr)
    conn.close()

if __name__ == "__main__":
    main()
