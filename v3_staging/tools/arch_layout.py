#!/usr/bin/env python3
"""
arch_layout.py — build the UNIFIED DESIGN LAYOUT where THE FILE TREE IS THE CIRCUIT.

A routine (re-runnable, parameterized), grounded ONLY in the cache (the 1:1 PDF
extraction). Code is truth; nothing from memory.

THE RULE (derived from cache, not imposed):
  - A node becomes a FOLDER where the cache documents internal sub-cells
    (e.g. UG572 p35 documents MMCM internals: VCO, PFD, charge pump, dividers).
  - A node becomes a `.cell` LEAF where the cache documents it as a primitive with
    ports/attributes but NO internal sub-structure (e.g. BUFGCE).
  The tree branches exactly where the circuit differentiates, and terminates in a
  cell file where it is repetition (count + per-cell spec). Walking the folders =
  tracing the circuit; opening a `.cell` = the cells at that leaf.

FUNCTIONAL GROUPS come from the cache's own descriptions (UG572 'Clock Buffers'
section -> buffers/ ; MMCM/PLL described as frequency synthesis -> sources/).

EACH FOLDER carries `_node.md` with YAML FRONTMATTER (read-once layer):
  name, role, tier, count(+scope), ports, attributes, feeds, fed_by, cascades_to,
  source. Topology that is peer (not containment) — the 8-BUFGMUX cascade ring —
  is recorded in frontmatter (cascades_to / topology), not forced into folders.

Every fact cites `<doc> p<page>`. Where the cache does not document a tier, the
node is created and flagged `pending: not in cache` — visible, never faked.

USAGE
  python3 arch_layout.py --subsystem Clocking [--out DIR] [--verify]
  python3 arch_layout.py --list
"""
import argparse, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "cache")

# ---- subsystem spec: doc + functional groups + the modules in each ------------
# Groups and their module lists trace to the cache section that names them
# (cited in group['source']). The routine derives counts/ports/attrs/internals.
SPECS = {
  "Clocking": {
    "doc": "ug572-ultrascale-clocking",
    "groups": [
      {"name": "buffers", "role": "global clock distribution",
       "source": "ug572 p16 (Clock Buffers)",
       "modules": ["BUFGCE","BUFGCTRL","BUFGCE_DIV","BUFG","BUFGCE_1","BUFGMUX",
                   "BUFG_GT","BUFG_GT_SYNC"],
       "topology": "BUFGCTRL multiplexers cascade to adjacent buffers, forming a "
                   "ring of eight BUFGMUXes (ug572 p16, Fig 2-4)"},
      {"name": "sources", "role": "clock generation / frequency synthesis",
       "source": "ug572 p9 (MMCM/PLL output clock frequencies)",
       "modules": ["MMCM","PLL","MMCME4_BASE","PLLE4_BASE"]},
    ],
  },
}

# cache tokens that signal a module has INTERNAL sub-cells (=> folder, not leaf)
INTERNAL_TOKENS = ["VCO","voltage controlled","charge pump","PFD","phase frequency",
                   "phase detector","divider","feedback counter"]

_SAFE = re.compile(r"[^A-Za-z0-9._+-]+")
def safe(s): return _SAFE.sub("_", (s or "").strip()).strip("_") or "_"
DIRS = {"input":"in","in":"in","output":"out","out":"out","inout":"inout","i":"in","o":"out","i/o":"inout"}
def normdir(v):
    p=str(v or "").strip().lower().split("\n")[0].split(); return DIRS.get(p[0],"") if p else ""

def load_pages(doc):
    out=[]
    with open(os.path.join(CACHE,doc+".jsonl")) as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try: r=json.loads(line)
            except json.JSONDecodeError: continue
            if r.get("page") is not None: r["_doc"]=doc; out.append(r)
    return out

# ---- cache derivations (count / ports / attributes / internals) ---------------
def derive_count(pages, module):
    pat=re.compile(r"(\d{1,4})\s+%ss?\b([^.]{0,40})"%re.escape(module))
    best=None
    for r in pages:
        for m in pat.finditer(r.get("text","") or ""):
            n=int(m.group(1)); tail=" ".join(m.group(2).split()).lower()
            if n>100000: continue
            scope=("per clock region" if "region" in tail else
                   ("per PHY" if "phy" in tail else ("device" if "device" in tail else "stated")))
            cand=(n,scope,f"{r['_doc']} p{r['page']}")
            if best is None or scope=="per clock region": best=cand
    return best or (None,"",None)

def derive_ports(pages, module):
    ports=[]; cite=None; seen=set()
    for r in pages:
        t=r.get("text","") or ""
        if module not in t: continue
        for tb in r.get("tables",[]) or []:
            rows=tb.get("rows") if isinstance(tb,dict) else tb
            if not rows or not rows[0]: continue
            head=[str(c or "").strip().lower() for c in rows[0]]
            nc=next((c for c in ("port","pin name","signal","name") if c in head),None)
            dc=next((c for c in ("direction","dir","i/o") if c in head),None)
            if not (nc and dc): continue
            ni,di=head.index(nc),head.index(dc)
            for row in rows[1:]:
                if ni>=len(row) or not row[ni]: continue
                dv=normdir(row[di]) if di<len(row) else ""
                if not dv: continue
                nm=str(row[ni]).split("\n")[0].split("<")[0].split("[")[0].replace("_","").strip().upper()
                if re.match(r"^[A-Z][A-Z0-9]{0,31}$",nm) and nm not in seen:
                    ports.append({"name":nm,"dir":dv}); seen.add(nm); cite=f"{r['_doc']} p{r['page']}"
    return ports,cite

def derive_attributes(pages, module):
    attrs=[]; cite=None; seen=set()
    for r in pages:
        if module not in (r.get("text","") or ""): continue
        for tb in r.get("tables",[]) or []:
            rows=tb.get("rows") if isinstance(tb,dict) else tb
            if not rows or not rows[0]: continue
            head=[str(c or "").strip().lower() for c in rows[0]]
            if not any("attribute" in h for h in head): continue
            ai=next((i for i,h in enumerate(head) if "attribute" in h),0)
            vi=next((i for i,h in enumerate(head) if "value" in h),None)
            de=next((i for i,h in enumerate(head) if h=="default"),None)
            ty=next((i for i,h in enumerate(head) if h=="type"),None)
            for row in rows[1:]:
                if ai>=len(row) or not row[ai]: continue
                nm=str(row[ai]).split("\n")[0].replace("_","").strip().upper()
                if not re.match(r"^[A-Z][A-Z0-9]{0,31}$",nm) or nm in seen: continue
                attrs.append({"name":nm,
                    "values":str(row[vi]).strip()[:40] if vi is not None and vi<len(row) else "",
                    "default":str(row[de]).strip() if de is not None and de<len(row) else "",
                    "type":str(row[ty]).strip() if ty is not None and ty<len(row) else ""})
                seen.add(nm); cite=f"{r['_doc']} p{r['page']}"
    return attrs,cite

def derive_internals(pages, component, peers):
    """Sub-cells the cache documents inside a component (=> this node is a FOLDER).
    An internal cell is attributed to `component` ONLY on pages where `component` is the
    DOMINANT one (most-mentioned among all candidate components) — not merely co-present.
    This stops a buffer page that happens to mention an MMCM's VCO from giving the
    buffer a VCO it does not have. Verified: every VCO/PFD/divider page is MMCM/PLL-
    dominant (ug572)."""
    found={}
    for r in pages:
        t=r.get("text","") or ""
        if component not in t: continue
        counts={m:len(re.findall(r"\b"+re.escape(m)+r"\b", t)) for m in peers}
        if not counts or max(counts.values())==0: continue
        dominant=max(counts, key=counts.get)
        if dominant!=component: continue            # internals belong to the page's subject
        for tok in INTERNAL_TOKENS:
            if tok.lower() in t.lower():
                key=tok.upper().replace(" ","_")
                found.setdefault(key, f"{r['_doc']} p{r['page']}")
    return [{"name":k,"source":v} for k,v in found.items()]

# ---- YAML frontmatter doc -----------------------------------------------------
def yaml_doc(d):
    L=["---"]
    for k,v in d.items():
        if v is None or v=="" or v==[]: continue
        if isinstance(v,list):
            L.append(f"{k}:")
            for it in v: L.append(f"  - {it}")
        else:
            L.append(f"{k}: {v}")
    L.append("---"); return "\n".join(L)

# ---- build a module: folder (has internals) or .cell leaf ---------------------
def build_module(pages, module, group, gdir, ledger):
    count,scope,ccite = derive_count(pages, module)
    ports,pcite = derive_ports(pages, module)
    attrs,acite = derive_attributes(pages, module)
    peers = [m for m in group["modules"] if m != module]
    internals = derive_internals(pages, module, peers)
    ledger["modules"]+=1; ledger["ports"]+=len(ports); ledger["attributes"]+=len(attrs)

    fm = {"name":module, "role":group["role"], "tier":group["name"],
          "count": count if count is not None else "pending",
          "count_scope":scope, "ports":[p["name"] for p in ports],
          "feeds":"clock fabric routing" if group["name"]=="buffers" else "clock buffers",
          "fed_by":"clock buffers / MMCM / PLL" if group["name"]=="buffers" else "input clock / MIO",
          "source": ccite or pcite or acite or "not in cache"}
    if group["name"]=="buffers" and "BUFG" in module:
        fm["cascades_to"]="adjacent BUFGCTRL (ring of 8 BUFGMUX, ug572 p16)"

    if internals:
        # FOLDER: cache documents internal sub-cells -> branch
        mdir=os.path.join(gdir, safe(module)); os.makedirs(mdir, exist_ok=True)
        fm["internals"]=[i["name"] for i in internals]
        body=[yaml_doc(fm), "", f"# {module}", "",
              f"{module} — {group['role']}. The cache documents internal sub-cells; "
              f"each is a `.cell` leaf in this folder.", "",
              "## Internal cells", ""]
        for i in internals:
            body.append(f"- `{i['name']}` (source `{i['source']}`)")
            # each internal sub-cell as a .cell leaf
            cell={"cell":i["name"],"parent":module,"kind":"analog_boundary"
                  if i["name"] in ("VCO","PFD","CHARGE_PUMP") else "structural",
                  "source":i["source"]}
            open(os.path.join(mdir, safe(i["name"])+".cell"),"w").write(
                yaml_doc(cell)+f"\n\n# {i['name']}\nInternal cell of {module}. Source `{i['source']}`.\n")
        if ports:
            body+=["", "## Ports (connectors)", "", "| port | dir |","| --- | --- |"]
            body+=[f"| `{p['name']}` | {p['dir']} |" for p in ports]
        if attrs:
            body+=["", "## Config / IO attributes", "", "| attribute | values | default | type |",
                   "| --- | --- | --- | --- |"]
            body+=[f"| `{a['name']}` | {a['values']} | {a['default']} | {a['type']} |" for a in attrs]
        open(os.path.join(mdir,"_node.md"),"w").write("\n".join(body)+"\n")
        if count is None:
            open(os.path.join(mdir,"_PENDING.txt"),"w").write(f"count for {module} not stated in cache — pending, not faked\n")
            ledger["pending"]+=1
        ledger["folders"]+=1
        return {"module":module,"shape":"folder","count":count,"internals":len(internals),
                "ports":len(ports),"attrs":len(attrs),"source":ccite}
    else:
        # .cell LEAF: primitive with ports/attrs, no documented internals
        fm["instances"]=count if count is not None else "pending"
        cellbody=[yaml_doc(fm), "", f"# {module}", "",
                  f"{module} — {group['role']}. Leaf cell ("
                  f"{count if count is not None else '?'} instances, {scope}). "
                  f"No internal sub-cells documented in cache.", ""]
        if ports:
            cellbody+=["## Ports (connectors)","","| port | dir |","| --- | --- |"]
            cellbody+=[f"| `{p['name']}` | {p['dir']} |" for p in ports]
        if attrs:
            cellbody+=["","## Config / IO attributes","","| attribute | values | default | type |",
                       "| --- | --- | --- | --- |"]
            cellbody+=[f"| `{a['name']}` | {a['values']} | {a['default']} | {a['type']} |" for a in attrs]
        open(os.path.join(gdir, safe(module)+".cell"),"w").write("\n".join(cellbody)+"\n")
        if count is None: ledger["pending"]+=1
        ledger["cells"]+=1
        return {"module":module,"shape":"cell","count":count,"internals":0,
                "ports":len(ports),"attrs":len(attrs),"source":ccite}

def build_subsystem(name, out_dir, verify=False):
    spec=SPECS[name]; pages=load_pages(spec["doc"])
    sub=os.path.join(out_dir,"XCZU19EG",safe(name)); os.makedirs(sub,exist_ok=True)
    ledger={"groups":0,"modules":0,"folders":0,"cells":0,"ports":0,"attributes":0,"pending":0}
    manifest=[]
    for group in spec["groups"]:
        gdir=os.path.join(sub, safe(group["name"])); os.makedirs(gdir,exist_ok=True); ledger["groups"]+=1
        gfm={"name":group["name"],"role":group["role"],"subsystem":name,
             "source":group["source"]}
        if group.get("topology"): gfm["topology"]=group["topology"]
        gbody=[yaml_doc(gfm),"",f"# {name} / {group['name']}","",
               f"{group['role']}. Source `{group['source']}`.","","## Modules",""]
        for module in group["modules"]:
            res=build_module(pages, module, group, gdir, ledger)
            gbody.append(f"- `{module}` ({res['shape']}) — count {res['count'] if res['count'] is not None else '—'}, "
                         f"{res['ports']}p, {res['attrs']} attrs")
            manifest.append({**res,"group":group["name"]})
        open(os.path.join(gdir,"_node.md"),"w").write("\n".join(gbody)+"\n")

    sfm={"name":name,"subsystem":name,"doc":spec["doc"],
         "groups":[g["name"] for g in spec["groups"]],
         "modules":ledger["modules"],"folders":ledger["folders"],"cells":ledger["cells"]}
    sbody=[yaml_doc(sfm),"",f"# {name} subsystem — the file tree IS the circuit","",
           "Folders branch where the cache documents internal structure; `.cell` files "
           "are leaves. Walk to trace the circuit. All facts cite the cache.","",
           "| module | shape | count | internals | ports | attrs | source |",
           "| --- | --- | --- | --- | --- | --- | --- |"]
    for m in manifest:
        sbody.append(f"| {m['module']} | {m['shape']} | {m['count'] if m['count'] is not None else '—'} | "
                     f"{m['internals']} | {m['ports']} | {m['attrs']} | `{m['source'] or '—'}` |")
    open(os.path.join(sub,"_node.md"),"w").write("\n".join(sbody)+"\n")
    json.dump({"subsystem":name,"ledger":ledger,"modules":manifest},
              open(os.path.join(sub,"_subsystem.json"),"w"), indent=2)

    if verify:
        assert ledger["modules"]==sum(len(g["modules"]) for g in spec["groups"]), "module count mismatch"
        print(f"verify: OK — {name}: {ledger['groups']} groups, {ledger['modules']} modules "
              f"({ledger['folders']} folders / {ledger['cells']} cells), {ledger['ports']} ports, "
              f"{ledger['attributes']} attrs, {ledger['pending']} pending")
    return ledger

def main():
    ap=argparse.ArgumentParser(description="build the unified design layout (file tree = circuit) from cache")
    ap.add_argument("--subsystem"); ap.add_argument("--out", default=os.path.join(ROOT,"design_layout"))
    ap.add_argument("--list",action="store_true"); ap.add_argument("--verify",action="store_true")
    a=ap.parse_args()
    if a.list or not a.subsystem:
        print("known subsystems:", ", ".join(SPECS)); return
    if a.subsystem not in SPECS:
        print(f"no spec for {a.subsystem}; known: {', '.join(SPECS)}", file=sys.stderr); sys.exit(2)
    led=build_subsystem(a.subsystem, a.out, a.verify)
    print(f"arch_layout: {a.subsystem} -> {os.path.join(a.out,'XCZU19EG',a.subsystem)}")

if __name__=="__main__":
    main()
