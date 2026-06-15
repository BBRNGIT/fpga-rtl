# Production Sign-Off Suite — XCZU19EG C-as-RTL  (derivation-grounded)

**Status:** SPEC FOR REVIEW (nothing built yet). The tapeout checklist.

## The governing law of this suite (read first)

**No gate asserts a value of its own. Every expected value a gate checks against
is DERIVED — read from the protected `conn_tree`/`hierarchy.json` for structure,
and corroborated against the originating cached doc page that the node's `source`
field cites.** A gate that cannot point to its derivation source does not ship.

- A gate's **rule** (e.g. "one driver per net") is a structural law — legitimate.
- A gate's **reference value** (e.g. "CARRY8 has ports CI, CI_TOP, CO, DI, O, S")
  is NEVER written by hand. It is read from `conn_tree` and validated against the
  `Port Descriptions` table on the cited cache page. The doc is the authority;
  the gate only enforces the match.
- **conn_tree is the PROTECTED ROOT.** Gates read it; gates do not alter it.
  Improving conn_tree is a SEPARATE task, never mixed into gate-building.
- For any reference value not yet in the data (fanout, CDC domains, POR init):
  **extractor-first** — write the tool that reads it from the originating cached
  doc, commit that, then the gate derives from it. No invented thresholds, ever.

### Proven pattern (verified on disk, the template for every "derives-now" gate)

```
conn_tree/PL/CLB/CARRY8/CARRY8.md   ports: CI, CI_TOP, CO, DI, O, S   source: ug974 p241
cache/ug974.jsonl  page 241  "Port Descriptions" table rows:
        CI(Input), CI_TOP(Input), CO<7:0>(Output), DI<7:0>(Input),
        O<7:0>(Output), S<7:0>(Input)
=> the two sets MATCH. The gate reads both and FAILS on mismatch.
   The number "6 ports" is never typed by a human — it is read from the doc.
```

---

## Derivation classes

- **DERIVES-NOW** — reference already present in `conn_tree` + its cited cache page.
  Buildable immediately, provably non-arbitrary.
- **STRUCTURAL-ONLY** — pure topology law over the `conn_tree` graph; needs no
  external reference value.
- **NEEDS-EXTRACT** — reference value not yet extracted; requires an extractor that
  reads it from the originating cached doc FIRST (extractor-first), then the gate
  derives from that extractor's committed output.

Status legend: `EXISTS` (in v3) · `PORT` (from v2 `.hft_staging`) · `NEW` · `PARTIAL`.

---

## How to read a check

```
ID  name                              [Tier][Subject][Class][Status]
  RULE        the invariant (pass/fail law)
  STRUCT SRC  the conn_tree / hierarchy.json field that supplies the actual value
  REF SRC     the cached doc region (reached via node.source) that supplies the
              EXPECTED value — or "topology" if structural-only
  FAIL WHEN   the exact mismatch that returns exit 1
  DERIVATION  one line: how expected is read from the doc, not invented
  ENFORCE     where it runs
```

---

# TIER 1 — Connectivity & structural sign-off (LVS + ERC)

### C01 single-driver-per-net        [T1][HW][STRUCTURAL-ONLY][EXISTS→extend]
- RULE: each net has exactly one driver.
- STRUCT SRC: `device.json`/`hierarchy.json` edges (src→dst, dir).
- REF SRC: topology (no external value needed).
- FAIL WHEN: a net id appears as `dst` of ≥2 driving edges.
- DERIVATION: counts drivers from the tree itself; nothing asserted.
- ENFORCE: netc.py + gate_device.sh (erc.py).

### C02 no-floating-input            [T1][HW][STRUCTURAL-ONLY][EXISTS→extend]
- RULE: every input net has a driver.
- STRUCT SRC: edges + `ports_list` (dir=in).
- REF SRC: topology.
- FAIL WHEN: an `in` port's net has no driving edge.
- DERIVATION: graph reachability over the tree.
- ENFORCE: netc.py + erc.py.

### C03 no-dangling-output          [T1][HW][STRUCTURAL+REF][PARTIAL]
- RULE: every driven net is consumed, unless it is a declared device output.
- STRUCT SRC: edges.
- REF SRC: declared-outputs list — itself derived from board/figure edges in
  conn_tree that terminate at a package pin (NOT a hand list).
- FAIL WHEN: a driver feeds no load and the net is not a conn_tree-terminating pin.
- DERIVATION: "is this an output?" answered by the tree's own board edges.
- ENFORCE: erc.py.

### C04 port-direction-consistency  [T1][HW][DERIVES-NOW][NEW]
- RULE: edges connect `out`→`in` only.
- STRUCT SRC: edge `dir`.
- REF SRC: each endpoint's `ports_list.dir` in conn_tree (which itself traces to
  the node's cited doc, e.g. ug974 Port Descriptions).
- FAIL WHEN: an edge joins two same-direction ports, or contradicts ports_list.
- DERIVATION: directions read from the doc-sourced ports_list, not assumed.
- ENFORCE: lvs.py.

### C05 net-completeness-vs-spec    [T1][HW][DERIVES-NOW][NEW]  ★ the CARRY8 check
- RULE: every port the originating doc declares for a primitive appears as a
  connection (or an allowlisted no-connect).
- STRUCT SRC: node `ports_list` + incident edges in conn_tree.
- REF SRC: the `Port Descriptions` table on the node's `source` cache page
  (e.g. `ug974 p241` for CARRY8).
- FAIL WHEN: a doc-declared port has no incident edge and no registry no-connect.
- DERIVATION: expected port set is READ FROM the cited cache table; the gate
  compares it to the tree. Proven on CARRY8.
- ENFORCE: lvs.py.

### C06 connection-provenance       [T1][HW][DERIVES-NOW][NEW]
- RULE: every edge cites a real source (board pin table / figure / routing doc)
  or carries a `synthesized` tag (Vivado-internal PIPs with no doc).
- STRUCT SRC: edge `source`/`pin`/`ball`/`fig`.
- REF SRC: the cited cache page must actually contain that pin/figure.
- FAIL WHEN: an edge has no citation, or the cited page lacks the referenced pin.
- DERIVATION: provenance validated against the cache, not trusted blindly.
- ENFORCE: lvs.py.  (Runs EARLY — guards the data other gates derive from.)

### C07 grid-positional-identity    [T1][HW][STRUCTURAL-ONLY][PORT]
- RULE: identity is (X,Y); no address registry; no two cells per site.
- STRUCT SRC: `container.json` positions / fabric geometry.
- REF SRC: topology.
- FAIL WHEN: duplicate coordinate, or a cell carries an explicit address.
- DERIVATION: positional uniqueness from the tree.
- ENFORCE: lvs.py (v2 check_grid_identity.py ported).

---

# TIER 2 — Circuit / logic sign-off (DRC)

### C08 branchless-datapath         [T2][HW][STRUCTURAL-ONLY][PORT]  ★ kills unify.py
- RULE: no `if/?:/switch/for/while`, no native `+ - * / %` in any `_tick`.
- STRUCT SRC: emitted `*_gen.h` tick bodies.
- REF SRC: topology (a syntactic law, no value).
- FAIL WHEN: a bare operator survives the comment-stripped awk scan in a tick.
- DERIVATION: pure syntax rule (Law #3).
- ENFORCE: drc.py + preguard (write-time).

### C09 combinational-loop          [T2][HW][STRUCTURAL-ONLY][PARTIAL]
- RULE: no comb cycle unbroken by a flip-flop.
- STRUCT SRC: `device.json` netlist graph.
- REF SRC: topology.
- FAIL WHEN: a cycle has no `dff`/`latch` on it.
- DERIVATION: cycle search over the tree.
- ENFORCE: drc.py.

### C10 fanout-limit                [T2][HW][NEEDS-EXTRACT][NEW]
- RULE: no net drives more loads than the documented max.
- STRUCT SRC: edge load counts per net (conn_tree).
- REF SRC: **extractor-first** — a new `fanout_extract.py` reads the documented
  drive/fanout limits from UG572/UG574 cache pages → committed `fanout_ref.json`.
- FAIL WHEN: a net's load count exceeds its extracted limit.
- DERIVATION: the limit is EXTRACTED from the cited doc, never chosen by hand.
  Until `fanout_ref.json` exists, this gate is DEFINED but errors "no extracted
  reference" (fail-closed) — it cannot pass on an invented default.
- ENFORCE: drc.py.

### C11 clock-domain-crossing (CDC) [T2][HW][NEEDS-EXTRACT][NEW]  ★ multi-domain
- RULE: every cross-domain signal passes a synchronizer.
- STRUCT SRC: edges + per-node clock-domain tag (conn_tree).
- REF SRC: **extractor-first** — `cdc_extract.py` derives the clock-domain set and
  domain-of-each-clock from UG572 clocking cache + conn_tree clock nets → committed
  `clock_domains.json`. The domain list is NOT asserted by me.
- FAIL WHEN: an edge crosses two extracted domains with no synchronizer cell on path.
- DERIVATION: domains come from the cited clocking doc, then the gate matches.
- ENFORCE: cdc.py.

### C12 self-running-clock          [T2][HW][STRUCTURAL-ONLY][PORT]
- RULE: clocks advance from internal state on power; no external step arg.
- STRUCT SRC: clock-net netlists.
- REF SRC: topology.
- FAIL WHEN: a clock tick reads an injected step input.
- DERIVATION: structural (v2 check_clock_rule.py).
- ENFORCE: drc.py.

### C13 reset/POR-init-state        [T2][HW][NEEDS-EXTRACT][PARTIAL]
- RULE: every register has a documented power-on init; boot is deterministic.
- STRUCT SRC: `*_gen.h` init path.
- REF SRC: **extractor-first** — `por_extract.py` reads documented reset/init
  values from UG974 register tables (cited pages) → committed `por_ref.json`.
- FAIL WHEN: a register's init differs from its extracted documented value, or has none.
- DERIVATION: init values extracted from the cited register tables, not assumed.
- ENFORCE: drc.py + POST.

### C14 logic-content / no-stub     [T2][HW][STRUCTURAL-ONLY][PORT]
- RULE: every block that should compute holds ≥1 real `cell_*`.
- STRUCT SRC: `*_gen.h`; exemptions from `enforcement_registry.yaml` only.
- REF SRC: topology.
- FAIL WHEN: a non-exempt generated block has zero `cell_*`.
- DERIVATION: structural (v2 gate 2d).
- ENFORCE: drc.py.

### C15 analog-boundary-correctness [T2][HW][DERIVES-NOW][PARTIAL]
- RULE: analog primitives appear only as recognized boundary black boxes, never
  gate-decomposed/faked.
- STRUCT SRC: `library.json` `analog:true` set; `lower.py` boundary list.
- REF SRC: the analog flag traces to the primitive's group in `catalog.json`
  (doc-sourced, e.g. ADVANCED/transceiver pages).
- FAIL WHEN: an analog cell is gate-decomposed or its behavior is faked in a tick.
- DERIVATION: the analog set is read from the doc-grounded catalog, not declared.
- ENFORCE: drc.py.

---

# TIER 3 — Count & resource sign-off

### C16 counts-==-DS891             [T3][HW][DERIVES-NOW][EXISTS]
- RULE: every element count equals the authentic device count.
- STRUCT SRC: `container.json` counts.
- REF SRC: `ds_resources.json` (DS891 cache) — the doc value.
- FAIL WHEN: any type's count ≠ DS891.
- DERIVATION: expected counts read from DS891 cache (checks_lib already does this).
- ENFORCE: gate_device.sh.

### C17 resource-budget            [T3][HW][DERIVES-NOW][NEW]
- RULE: a loaded design places ≤ available cells per type.
- STRUCT SRC: design netlist.
- REF SRC: `container.json` totals (which trace to DS891).
- FAIL WHEN: placed cells of a type exceed availability.
- DERIVATION: budget = the extracted container total; activates with real designs.
- ENFORCE: resource.py.

### C18 no-overlap-placement       [T3][HW][STRUCTURAL-ONLY][PARTIAL]
- RULE: one cell per site; placements within fabric bounds.
- STRUCT SRC: `placement.json`, fabric geometry.
- REF SRC: topology.
- FAIL WHEN: duplicate site or out-of-bounds coord.
- DERIVATION: structural.
- ENFORCE: gate_device.sh.

---

# TIER 4 — Generation integrity (reproducibility)

### C19 byte-match (golden-file)   [T4][TOOL+HW][STRUCTURAL-ONLY][PORT]
- RULE: every generated artifact reproduces byte-identically from its generator.
- STRUCT SRC: committed artifact + its tool.
- REF SRC: the artifact is its own reference (re-run → cmp).
- FAIL WHEN: re-running the tool to /tmp and `cmp` differs.
- DERIVATION: self-referential; no external value.
- ENFORCE: integrity.py.

### C20 clean-room-rebuild         [T4][TOOL+HW][STRUCTURAL-ONLY][PORT]
- RULE: the device rebuilds from committed HEAD, not the dirty tree.
- STRUCT SRC: git HEAD archive.
- REF SRC: self.
- FAIL WHEN: from-HEAD rebuild fails/differs.
- ENFORCE: integrity.py + pre-commit.

### C21 no-Verilog/VHDL/TCL        [T4][HW+TOOL][STRUCTURAL-ONLY][EXISTS]
- RULE: C is the only RTL; no HDL files, no HDL string literals in tools.
- STRUCT SRC: file tree + tool source.
- REF SRC: self.
- FAIL WHEN: an HDL file exists or a tool holds an HDL template literal.
- ENFORCE: preguard + integrity.py.

### C22 compile + POST             [T4][HW][STRUCTURAL-ONLY][EXISTS]
- RULE: device compiles `-Werror` and POSTs exit 0.
- ENFORCE: gate_device.sh.

---

# TIER 5 — Tool governance + process anti-sabotage (meta-gates)

### C23 tool-output-is-generated   [T5][TOOL][STRUCTURAL-ONLY][NEW]
- RULE: a tool emitting hardware must derive it from structured input — no
  triple-quoted C/HDL hardware-logic string literals (POST/report harness exempt
  via registry).
- FAIL WHEN: a tool defines `"""...static void *_tick.../module/always/assign..."""`
  and writes it.
- DERIVATION: syntactic scan of tool source (Law #2).
- ENFORCE: toolgov.py + preguard.

### C24 tool-fact-provenance       [T5][TOOL][DERIVES-NOW][NEW]  ★ kills configmap/clkfab rot
- RULE: a tool may not introduce a hardware constant (count/width/rate/range) that
  is neither read from cache nor tagged `curated-constant`.
- STRUCT SRC: tool source + its committed output.
- REF SRC: the cache — every such constant must appear on a cited cache page.
- FAIL WHEN: a magic hardware constant has no cache read and no curated tag.
- DERIVATION: the gate searches the cache for the constant; absent ⇒ fail.
- ENFORCE: toolgov.py.

### C25 judges≠judged + closed-exemptions + tool-usage-order  [T5][TOOL+PROC][PORT]
- RULE (a) enforcement files editable only with `FOUNDER_OVERRIDE=1`; (b) exemptions
  only in `enforcement_registry.yaml`, never inline; (c) phase tools run in declared
  order, denied while board RED.
- ENFORCE: pre-commit + preguard.

### C26 fail-closed + gate-forcing + CI-required  [T5][PROC][PARTIAL→extend]
- RULE: missing check script = FAIL; commit BLOCKED on red gate; same gate is a
  REQUIRED server-side check (unbypassable by `--no-verify`).
- ENFORCE: pre-commit (local) + GitHub required status check (remote authority).

---

# Derivation tally

- DERIVES-NOW (reference in conn_tree + cited cache, buildable immediately):
  C04 C05 C06 C15 C16 C17 C24  — **7**
- STRUCTURAL-ONLY (topology law, no external value): C01 C02 C03 C07 C08 C09 C12
  C14 C18 C19 C20 C21 C22 C23 — **14**
- NEEDS-EXTRACT (extractor-first, reference pulled from cited doc before gate):
  C10 (fanout) C11 (CDC) C13 (POR) — **3**
- PROCESS: C25 C26 — **2**

**26 checks. Not one carries a hand-chosen value: every reference is read from
conn_tree or the originating cached doc, or it is structural, or its extractor
must be built first.**

---

# Build order (after sign-off on THIS spec)

- **Wave 0 — expunge** the fakes (unify.py, ps-realization.py, orphan artifacts).
- **Wave 1 — derives-now + structural spine gates** (no extractor needed):
  C06 first (validate the data), then C01 C02 C04 C05 C07 C15 C16 C24 + C08 C19
  C20 C21 C22 C23 + wiring (erc/lvs/drc/integrity/toolgov, gate_device.sh,
  pre-commit, preguard, enforcement_registry.yaml). Run against the 30 gate-ready
  blocks — prove the spine.
- **Wave 2 — needs-extract gates** (extractor-first, one at a time):
  C13 por_extract → C11 cdc_extract → C10 fanout_extract, each committing its
  `*_ref.json` before its gate.
- **Wave 3 — design-time gates:** C03 C09 C10 C17 C18 as designs load.
- **Then** extend the derivation library for the ~40 NEEDS-DERIVE blocks; each new
  block must pass the full applicable suite before it counts as built.

conn_tree is never altered by gate-building. Improving conn_tree is its own task.
No new block ships before Wave 1 is live.
