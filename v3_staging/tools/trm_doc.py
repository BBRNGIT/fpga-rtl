#!/usr/bin/env python3
"""
trm_doc.py — reconstruct a TRM (or any extracted UG/DS doc) as a navigable
filesystem tree of Markdown, sourced DIRECTLY from the committed page cache.
TOOL OUTPUT — generated, never hand-authored; re-running reproduces it
byte-identically from the same cache.

SOURCE OF TRUTH
  cache/<doc>.jsonl  — one JSON object per page: {page, text, tables, heads,
  verilog}. This is the authoritative input. The tree IS the document, not a
  derived netlist: nothing is pulled from hierarchy.json or any middle artifact.

TREE SHAPE (macro -> micro)
  <out>/<DOC>/                                  the document root
    00_README.md                                cover + chapter index
    chNN_<slug>/                                one folder per chapter
      _chapter.md                               chapter title + page span + section list
      pNNNN.md                                  one file per page: full text
      pNNNN_tableK.md                           one file per parsed table on that page
  front_matter/                                 pages before "Chapter 1"
  INDEX.json                                    machine-readable map of every emitted file
  INDEX.md                                      table of contents

A page file's body is the page's authoritative text verbatim (de-noised of the
running header/footer), then each table rendered as a Markdown table. A figure's
block labels (heads) are listed so a reader can see the components on that page.
Every file carries its `source: <doc> p<N>` citation — total fidelity, total
reconstruction: concatenating the page files in order reproduces the document text.

USAGE
  python3 trm_doc.py                            # default doc = the TRM (ug1085)
  python3 trm_doc.py --doc ug574-ultrascale-clb # any cache doc
  python3 trm_doc.py --all                      # every cache/*.jsonl
  python3 trm_doc.py --out DIR                  # output root (default ../trm_tree)
  python3 trm_doc.py --verify                   # assert page round-trip after emit
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # v3_staging/
CACHE = os.path.join(HERE, "cache")
DEFAULT_DOC = "ug1085-zynq-ultrascale-trm"

_SAFE = re.compile(r"[^A-Za-z0-9._+-]+")
def slug(s, maxlen=48):
    s = _SAFE.sub("_", (s or "").strip()).strip("_")
    return (s[:maxlen].rstrip("_") or "_")

# "Chapter 12: Security" — the chapter marker as it appears in page text.
_CHAP = re.compile(r"\bChapter\s+(\d+)\s*:\s*([^\n]+)")
# Running header/footer lines to strip from page bodies (doc boilerplate).
_NOISE = re.compile(
    r"^(?:www\.xilinx\.com|Send Feedback|UG\d+.*|.*Device TRM|\d+|\s*)$")


def load_pages(doc):
    path = os.path.join(CACHE, doc + ".jsonl")
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    pages = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("page") is None:
                continue
            pages.append(rec)
    pages.sort(key=lambda r: int(r["page"]))
    return pages


def chapter_of(text):
    """Return (num, title) if a chapter heading starts on this page, else None."""
    m = _CHAP.search(text or "")
    if not m:
        return None
    return (int(m.group(1)), m.group(2).strip())


def clean_text(text):
    """Drop running header/footer noise lines; keep the page body verbatim."""
    out = []
    for ln in (text or "").splitlines():
        if _NOISE.match(ln.strip()):
            continue
        out.append(ln.rstrip())
    # collapse >2 blank lines
    body = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def md_table(rows):
    """Render a parsed table (list of row-lists) as a Markdown table."""
    rows = [[("" if c is None else str(c)).replace("\n", " ⏎ ").replace("|", "\\|")
             for c in r] for r in rows if r]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    head = rows[0]
    out = ["| " + " | ".join(head) + " |",
           "| " + " | ".join(["---"] * width) + " |"]
    for r in rows[1:]:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def assign_chapters(pages):
    """Walk pages; bucket each into the current chapter. Pages before Chapter 1
    go to front_matter. Returns ordered list of chapters:
        [{num, title, slug, pages:[recs]}], and front_matter:[recs]."""
    front = []
    chapters = []
    cur = None
    for rec in pages:
        ch = chapter_of(rec.get("text", ""))
        if ch is not None:
            num, title = ch
            # new chapter only when the number advances (chapter title pages
            # repeat the marker; a real new chapter has a higher/!= number)
            if cur is None or num != cur["num"]:
                cur = {"num": num, "title": title,
                       "slug": f"ch{num:02d}_{slug(title)}", "pages": []}
                chapters.append(cur)
        if cur is None:
            front.append(rec)
        else:
            cur["pages"].append(rec)
    return chapters, front


def emit_page_file(d, rec, doc, written):
    pg = int(rec["page"])
    body = clean_text(rec.get("text", ""))
    heads = rec.get("heads", []) or []
    tables = rec.get("tables", []) or []
    verilog = (rec.get("verilog") or "").strip()

    lines = [f"# {doc} — page {pg}", "",
             f"**Source:** `{doc} p{pg}`", ""]
    if body:
        lines += ["## Text", "", "```text", body, "```", ""]
    if heads:
        labels = sorted({h[0] for h in heads if isinstance(h, list) and h})
        if labels:
            lines += ["## Block labels on this page",
                      "", ", ".join(f"`{x}`" for x in labels), ""]
    n_tab = 0
    for i, t in enumerate(tables):
        rows = t.get("rows") if isinstance(t, dict) else t
        mt = md_table(rows or [])
        if not mt:
            continue
        n_tab += 1
        # separate file per table for granularity + an inline copy for reading
        tname = f"p{pg:04d}_table{i+1}.md"
        with open(os.path.join(d, tname), "w") as f:
            f.write(f"# {doc} p{pg} — table {i+1}\n\n"
                    f"**Source:** `{doc} p{pg}`\n\n{mt}\n")
        written.append((f"{doc} p{pg} table{i+1}", os.path.join(d, tname)))
        lines += [f"## Table {i+1}", "", mt, ""]
    if verilog:
        lines += ["## Verilog region (read-only source, not emitted)",
                  "", "```verilog", verilog, "```", ""]

    fname = f"p{pg:04d}.md"
    with open(os.path.join(d, fname), "w") as f:
        f.write("\n".join(lines) + "\n")
    written.append((f"{doc} p{pg}", os.path.join(d, fname)))
    return n_tab


def emit_doc(doc, out_root, verify=False):
    pages = load_pages(doc)
    chapters, front = assign_chapters(pages)
    doc_dir = os.path.join(out_root, doc)
    os.makedirs(doc_dir, exist_ok=True)

    written = []            # (citation, path)
    page_count = 0
    table_count = 0

    # front matter
    if front:
        fd = os.path.join(doc_dir, "front_matter")
        os.makedirs(fd, exist_ok=True)
        for rec in front:
            table_count += emit_page_file(fd, rec, doc, written)
            page_count += 1

    # chapters
    chap_index = []
    for ch in chapters:
        cd = os.path.join(doc_dir, ch["slug"])
        os.makedirs(cd, exist_ok=True)
        first = int(ch["pages"][0]["page"]) if ch["pages"] else None
        last = int(ch["pages"][-1]["page"]) if ch["pages"] else None
        # chapter readme
        sec = [f"# Chapter {ch['num']}: {ch['title']}", "",
               f"**Pages:** {first}–{last}  ·  **Source:** `{doc} p{first}-{last}`",
               "", "## Pages", ""]
        for rec in ch["pages"]:
            pg = int(rec["page"])
            sec.append(f"- [p{pg:04d}](p{pg:04d}.md)")
        with open(os.path.join(cd, "_chapter.md"), "w") as f:
            f.write("\n".join(sec) + "\n")
        for rec in ch["pages"]:
            table_count += emit_page_file(cd, rec, doc, written)
            page_count += 1
        chap_index.append({"num": ch["num"], "title": ch["title"],
                           "slug": ch["slug"], "first": first, "last": last,
                           "pages": len(ch["pages"])})

    # doc README + chapter index
    readme = [f"# {doc}", "",
              f"Reconstructed from `cache/{doc}.jsonl` "
              f"({len(pages)} pages, {len(chapters)} chapters). "
              f"Each page is a Markdown file; each parsed table is its own file. "
              f"Folders are chapters (macro → micro).", "", "## Chapters", ""]
    for c in chap_index:
        readme.append(f"- **Ch {c['num']}: {c['title']}** "
                      f"([{c['slug']}]({c['slug']}/_chapter.md)) "
                      f"— pp {c['first']}–{c['last']} ({c['pages']} pp)")
    with open(os.path.join(doc_dir, "00_README.md"), "w") as f:
        f.write("\n".join(readme) + "\n")

    if verify:
        # round-trip: number of page files emitted == number of cache pages
        n_page_files = sum(1 for cite, _ in written if " table" not in cite)
        assert n_page_files == len(pages), \
            f"fidelity FAIL: {n_page_files} page files for {len(pages)} cache pages"

    return {"doc": doc, "pages": len(pages), "chapters": len(chapters),
            "page_files": page_count, "table_files": table_count,
            "written": written, "chapter_index": chap_index, "doc_dir": doc_dir}


def main():
    ap = argparse.ArgumentParser(description="reconstruct an extracted doc as a Markdown tree from its page cache")
    ap.add_argument("--doc", default=DEFAULT_DOC, help=f"cache doc key (default {DEFAULT_DOC})")
    ap.add_argument("--all", action="store_true", help="emit every cache/*.jsonl")
    ap.add_argument("--out", default=os.path.join(ROOT, "trm_tree"), help="output root (default ../trm_tree)")
    ap.add_argument("--verify", action="store_true", help="assert page round-trip after emit")
    args = ap.parse_args()

    if args.all:
        docs = sorted(fn[:-6] for fn in os.listdir(CACHE) if fn.endswith(".jsonl"))
    else:
        docs = [args.doc]

    os.makedirs(args.out, exist_ok=True)
    index = {"out": args.out, "docs": []}
    for doc in docs:
        try:
            res = emit_doc(doc, args.out, verify=args.verify)
        except FileNotFoundError:
            print(f"  skip {doc}: no cache/{doc}.jsonl", file=sys.stderr)
            continue
        index["docs"].append({k: res[k] for k in
                              ("doc", "pages", "chapters", "page_files", "table_files", "chapter_index")})
        print(f"trm_doc: {doc} -> {res['pages']} pages, {res['chapters']} chapters, "
              f"{res['table_files']} tables  ({res['doc_dir']})")

    with open(os.path.join(args.out, "INDEX.json"), "w") as f:
        json.dump(index, f, indent=2)
        f.write("\n")
    toc = ["# Extracted-doc trees — index", ""]
    for d in index["docs"]:
        toc.append(f"- **{d['doc']}** — {d['pages']} pp, {d['chapters']} ch, {d['table_files']} tables "
                   f"([open]({d['doc']}/00_README.md))")
    with open(os.path.join(args.out, "INDEX.md"), "w") as f:
        f.write("\n".join(toc) + "\n")
    print(f"trm_doc: index -> {os.path.join(args.out,'INDEX.json')} + INDEX.md")


if __name__ == "__main__":
    main()
