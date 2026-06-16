#!/usr/bin/env python3
"""
datasheet.py — Stage 2 of Timeline-1: ORGANIZE the database into the datasheet.

This is a PARTITION, not a query. Every table in cache.db is assigned to a logical
group — by its KIND (what it is) and by its OWNER (the primitive it belongs to, or
its document). Every row lands in exactly one place. Nothing is selected, nothing
is searched-for, nothing is dropped. Conservation: total tables == sum over groups.

ORGANIZATION (two keys, both read from the row's own columns):
  KIND  — from header_sig: ports | attributes | drp | registers | connections |
          instantiation | revision_history | other.  (every table gets exactly one)
  OWNER — the primitive declared on the nearest page <= the table's page in the same
          doc (interval assignment). Tables before any declaration belong to their
          DOCUMENT (a subsystem-level owner). (every table gets exactly one)

OUTPUT (../datasheet/):
  datasheet.json     the full organized structure: owner -> kind -> [tables(cited)]
  by_kind/<kind>.md  every table of that kind, listed with owner + cite
  by_owner/<owner>.md every table under that primitive/doc, grouped by kind
  INDEX.md           the conservation proof (total == sum of all groups)

USAGE
  python3 datasheet.py [--db ../db/cache.db] [--out ../datasheet] [--verify]
"""
import argparse, bisect, json, os, re, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)

def safe(s):
    return "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in str(s)).strip("_") or "_"

def kind_of(sig):
    s = (sig or "").lower()
    if "port" in s and ("direction" in s or "dir" in s): return "ports"
    if "attribute" in s and "drp" not in s:              return "attributes"
    if "drp" in s:                                        return "drp"
    if "register" in s:                                   return "registers"
    if "source" in s and "destination" in s:             return "connections"
    if "instantiation" in s:                             return "instantiation"
    if "date" in s and "revision" in s:                  return "revision_history"
    return "other"

def declarations(cur):
    """doc -> sorted [(page, primitive_name)] for every declaring page."""
    decl = {}
    for doc, page, text in cur.execute("SELECT doc,page,text FROM pages WHERE has_primitive_decl=1"):
        m = re.search(r"^([A-Z][A-Z0-9_]+)\s*\n.*?(?:Primitive:|PRIMITIVE_GROUP)", text or "", re.M | re.S)
        if m:
            decl.setdefault(doc, []).append((int(page), m.group(1)))
    for d in decl: decl[d].sort()
    return decl

def owner_of(decl, doc, page):
    """The primitive whose declaration page is the greatest <= page (same doc),
    else the document itself (a subsystem-level owner). Never None — total."""
    lst = decl.get(doc, [])
    pages = [p for p, _ in lst]
    i = bisect.bisect_right(pages, int(page)) - 1
    return lst[i][1] if i >= 0 else f"(doc) {doc}"

def organize(db, out, verify=False):
    con = sqlite3.connect(db); cur = con.cursor()
    decl = declarations(cur)

    # PARTITION every table -> (owner, kind), recording its cite. Nothing dropped.
    sheet = {}            # owner -> kind -> [ {table_id, doc, page, header_sig} ]
    total = 0
    for tid, doc, page, sig in cur.execute("SELECT id,doc,page,header_sig FROM tables"):
        k = kind_of(sig)
        o = owner_of(decl, doc, int(page))
        sheet.setdefault(o, {}).setdefault(k, []).append(
            {"table_id": tid, "doc": doc, "page": int(page), "header_sig": sig})
        total += 1

    os.makedirs(out, exist_ok=True)
    json.dump({"owners": len(sheet), "tables": total, "sheet": sheet},
              open(os.path.join(out, "datasheet.json"), "w"), indent=2)

    # by_kind/  — every kind, all its tables with owner + cite
    bk = os.path.join(out, "by_kind"); os.makedirs(bk, exist_ok=True)
    from collections import defaultdict
    kind_tally = defaultdict(int)
    by_kind = defaultdict(list)
    for o, kinds in sheet.items():
        for k, items in kinds.items():
            kind_tally[k] += len(items)
            for it in items: by_kind[k].append((o, it))
    for k, lst in by_kind.items():
        with open(os.path.join(bk, f"{safe(k)}.md"), "w") as f:
            f.write(f"# {k} — {len(lst)} tables\n\n| owner | doc p page | header |\n|---|---|---|\n")
            for o, it in lst:
                f.write(f"| {o} | {it['doc']} p{it['page']} | {it['header_sig'][:50]} |\n")

    # by_owner/ — every owner, its tables grouped by kind
    bo = os.path.join(out, "by_owner"); os.makedirs(bo, exist_ok=True)
    for o, kinds in sheet.items():
        with open(os.path.join(bo, f"{safe(o)}.md"), "w") as f:
            f.write(f"# {o}\n\n")
            for k, items in sorted(kinds.items()):
                f.write(f"## {k} ({len(items)})\n\n")
                for it in items:
                    f.write(f"- `{it['doc']} p{it['page']}` — {it['header_sig'][:50]}\n")
                f.write("\n")

    # INDEX + conservation
    summed = sum(kind_tally.values())
    with open(os.path.join(out, "INDEX.md"), "w") as f:
        f.write("# Datasheet — the database organized into logical groups\n\n")
        f.write("Every table partitioned by KIND and OWNER. Nothing queried, nothing dropped.\n\n")
        f.write(f"**Owners:** {len(sheet)}  ·  **Tables:** {total}\n\n## By kind\n\n| kind | tables |\n|---|---|\n")
        for k, n in sorted(kind_tally.items(), key=lambda x:-x[1]):
            f.write(f"| {k} | {n} |\n")
        f.write(f"\n**Conservation:** sum of all kind groups = {summed}, total tables = {total} — "
                f"{'BALANCES' if summed==total else 'MISMATCH'}\n")

    con.close()
    if verify:
        assert summed == total, f"CONSERVATION FAIL: groups sum {summed} != {total} tables"
        print(f"verify: OK — {total} tables partitioned into {len(sheet)} owners; "
              f"kind groups sum to {summed} (== total). Nothing dropped.")
    return total, len(sheet), kind_tally

def main():
    ap = argparse.ArgumentParser(description="organize the database into the datasheet (partition, not query)")
    ap.add_argument("--db", default=os.path.join(ROOT, "db", "cache.db"))
    ap.add_argument("--out", default=os.path.join(ROOT, "datasheet"))
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    if not os.path.exists(a.db):
        print(f"error: {a.db} not found", file=sys.stderr); sys.exit(2)
    total, owners, kt = organize(a.db, a.out, a.verify)
    print(f"datasheet: {total} tables -> {owners} owners -> {a.out}")

if __name__ == "__main__":
    main()
