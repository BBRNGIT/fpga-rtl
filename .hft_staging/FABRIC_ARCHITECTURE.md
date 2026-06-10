# FABRIC_ARCHITECTURE.md — The FPGA Fabric (netlist-of-netlists)

> Knowledge artifact. Captures the complete, grounded understanding of the **FPGA fabric** — the
> missing top-level piece that turns 15 individually-graduated C-as-RTL modules into one digitally
> realized FPGA. Built to `hft_pipeline/ARCHITECTURE.md` (§2/§3/§4/§5); closes the §11.5 and §11.9
> diseases. Read this with `DESIGN_GUIDE.md` (per-module method) and the `synthesize-fpga-fabric`
> skill (`.claude/agents/AGNT/skills/synthesize-fpga-fabric.md`).
>
> **Status: design captured, tooling not yet built.** `.hft_staging/fabric/` does not yet exist —
> that absence is correct; the fabric is the next architectural piece, not an oversight.

---

## 1. What the fabric IS

The fabric is a **passive netlist-of-netlists**: a single hand-authored source-of-truth spec that
declares, one level above the modules,

1. **The device map** — which devices exist, their reserved address windows, and which graduated
   module netlists populate each device. (ARCHITECTURE.md §3: the backplane is a **device map, not a
   module map.**)
2. **The connections** — which published register window each consumer samples. This is *declared*,
   not hand-wired: a consumer reading a producer's output addresses **is** wired to it by that fact.
   (§4: the register fabric IS the wiring; **placement = connectivity**.)
3. **The clock domains** — which reference drives each device, the derived ratios (e.g. 2:1
   pipeline:MAC as a real constant, never a loop count), and the CDC/SLR seams where domains meet.
   (§5: many clocks, one reference, crossing via CDC.)

It is the **netlist** of the whole FPGA, exactly as each `<module>.net.json` is the netlist of one
device — the same artifact, one fractal level up: a netlist whose **nodes are devices** and whose
**nets are published register windows**.

## 2. What the fabric IS NOT

- **NOT an orchestrator.** It has no `main()`, no dispatch loop, no `CLK_DEP_TABLE` of hardcoded
  calls. Real silicon has no entry point every block slaves to (§4). The fabric is *wiring*, and
  wiring does not execute.
- **NOT a re-introspection of built modules.** `tools/circuit-introspection.py` scans graduated
  modules *bottom-up* and emits **descriptive** registries (`circuit-topology.json`,
  `registry-*.json`, `CIRCUIT_WIRING.md`). The fabric is the **prescriptive top-down source spec**
  those outputs should conform to. Introspection *reads* reality; the fabric *declares* intent.
  (If they ever disagree, the fabric is the spec and the drift is a finding.)
- **NOT a runtime, a framework, or a shared filespace.** No invented vocabulary. The only structures
  named are ones the founder's docs already use: device, backplane, window, lane, clock domain, CDC,
  SLR seam, netlist.
- **NOT a replacement for the modules.** The 15 graduated `*_gen.h` netlists are unchanged. The
  fabric references them; it does not regenerate or absorb them.

## 3. The tooling (mirrors the per-module emitter→validate→gennet chain, one level up)

The fabric is built with the **identical three-stage law** as every module
(`DESIGN_GUIDE.md` §3, build-sequence law) — only the granularity changes (devices, not gates):

| Stage | Per-module (existing) | Fabric (to build) | Role |
|---|---|---|---|
| EMITTER (hand-written) | `gen_<module>_net.py` | `gen_fabric_net.py` | Emits the netlist as stdout. HAND-WRITTEN only. |
| NETLIST (produced, committed) | `<module>.net.json` | `fabric.net.json` | Single source of truth for the structure. |
| VALIDATOR | `validate.py` | `validate_fabric.py` | Structural gate: single-writer / no-overlap / no-floating, at device granularity. |
| GENERATOR (hand-written) | `gennet.py` | `gennet_fabric.py` | Reads the netlist, produces the realized C. HAND-WRITTEN only. |

Build sequence (run in `.hft_staging/fabric/`):
```sh
python3 gen_fabric_net.py > fabric.net.json        # emitter produces the device-level netlist
python3 validate_fabric.py fabric.net.json         # validate device map + connections + domains
python3 gennet_fabric.py fabric.net.json > fabric_gen.h   # generator realizes the wired FPGA in C
```
Both `fabric.net.json` and `fabric_gen.h` are COMMITTED (proof the FPGA was generated, not
hand-wired). Clean-room rebuild must byte-match — same law as modules.

### 3a. What `validate_fabric.py` checks (device granularity)
- **device-map integrity** — every device has a reserved window; no two device windows overlap;
  every module assigned to a device fits inside that device's window.
- **single-writer per window** — each published register window has exactly one producer device.
  No two devices write the same lane. (The module-level single-writer law, lifted to devices.)
- **no-floating connection** — every consumer's sampled window resolves to a real producer's
  published window. No consumer reads an address no device publishes (a "floating net").
- **clock-domain legality** — every cross-domain connection crosses through a declared CDC/SLR seam
  device (e.g. `tai_cdc`, `fifo_rx`); no raw multi-bit counter is sampled across a domain boundary
  (the tearing law, §5 / CLAUDE.md). A connection that crosses domains without a seam = FAIL.
- **placement = connectivity closure** — every module the modules-graph says produces an output has
  a consumer declared, and every consumer's input resolves; the wiring is complete and order-free.

### 3b. What `gennet_fabric.py` generates
- The **realized FPGA `fabric_gen.h`**: the device map as backplane window reservations, each device
  bound to its graduated module netlist, and the **registered connections** between published
  windows — the wiring made concrete as register-address bindings.
- The **clock distribution**: each domain derived from its reference, ratios as named constants, the
  CDC/SLR seams instantiated at domain boundaries.
- It generates **no business logic and no dispatch order** — every module already reads the previous
  cycle's frozen registered state, so evaluation order is irrelevant (§4). The realized fabric is
  pure structure: power on → clocks distribute → every device ticks READ→COMPUTE→WRITE.

## 4. The workflow this enables — own-design synthesis (not vendor synthesis)

The fabric makes the full FPGA-build flow real, **entirely in C, with no vendor tools** (no Vivado,
no bitstream from Xilinx). It is **our own digitally-realized FPGA**:

```
Design fabric   →  Simulate   →  Synthesize  →  P&R         →  "Bitstream"  →  Load
gen_fabric_net     run the        validate_      placement =     fabric_gen.h    power on the
.py → fabric        wired C        fabric.py       connectivity    (the realized   backplane;
.net.json          (cycle-         proves the      already         FPGA, generated  clocks
(device map)        accurate)      structure       declared in     not hand-wired)  distribute;
                                   is legal        the netlist                      devices tick
```
- This is **own-design synthesis**, not vendor synthesis: we synthesize *our* netlist-of-netlists
  into *our* deterministic C realization. The determinism (§1) carries to a real FPGA build later,
  but the modeling/realization is pure C.
- "Place & route" here = the fabric netlist's declared placement, which **is** the connectivity
  (§4: placement = connectivity). There is no separate routing step because the addresses are the
  wires.

## 5. How it realizes ARCHITECTURE.md intent (and which diseases it closes)

| ARCHITECTURE.md clause | How the fabric realizes it |
|---|---|
| **§2 payoff** (swap modules, clone ingress, many strategies, trusted reproducibility) | The fabric is wiring-as-data; swapping a module = swapping which netlist a device binds; cloning ingress = declaring a second device on the same window. Byte-identical rebuilds = trust. |
| **§3 device map, not module map** | The fabric *is* the device map: devices on the backplane, modules nested into devices. Replaces the flat sprawl. |
| **§4 fabric IS the wiring; placement = connectivity; no manual wiring** | Connections are declared by published-window addresses; the generator realizes them. No `CLK_DEP_TABLE`, no hand-maintained dependency table. |
| **§5 many clocks, one reference; CDC at boundaries** | The fabric declares each domain's reference, derived ratios as constants, and CDC/SLR seams at every crossing — validated by `validate_fabric.py`. |
| **Closes §11.5** (backplane fragmentation — 14 flat per-module sub-headers) | The fabric replaces the flat sub-header sprawl with the device hierarchy: modules wire into devices, devices live on the backplane. |
| **Closes §11.9** (manual wiring — `CLK_DEP_TABLE` + hardcoded 26-call dispatch) | Order-free registered hops mean evaluation order is irrelevant; the generator emits structure, not a dispatch sequence. The manual wiring is deleted, not refactored. |

## 6. Viability (as assessed)

- **Architecturally sound** — it is the same proven emitter-first netlist pattern at a higher
  granularity; nothing new is invented, the method is already validated on 15 modules.
- **Closes 4 diseases** — §11.5 (fragmentation) and §11.9 (manual wiring) directly; and removes the
  two structural enablers of §11.1/§11.4 (a top-level structure that has no place for `sim_feed`/
  replay tokens to live).
- **Enables 3 payoffs** — module swap, ingress clone, many-strategies-on-shared-registers (§2),
  because wiring becomes declarative data rather than hardcoded calls.
- **Software scope** — ~1–1.5k lines of new tooling total: `gen_fabric_net.py` (emitter),
  `validate_fabric.py` (device-granularity validator), `gennet_fabric.py` (generator), plus a thin
  fabric starter/host glue. No change to any graduated module.

## 7. Key files & grounding points (where this knowledge lives)

- **This file** — `.hft_staging/FABRIC_ARCHITECTURE.md` (the captured understanding).
- **The skill** — `.claude/agents/AGNT/skills/synthesize-fpga-fabric.md` (guides future fabric work).
- **Design intent** — `hft_pipeline/ARCHITECTURE.md` §2/§3/§4/§5 (canonical), §11.5/§11.9 (diseases closed).
- **Per-module method** — `.hft_staging/DESIGN_GUIDE.md` (the chain the fabric tooling mirrors).
- **Reference netlist tooling** — `.hft_staging/nic/gen_nic_net.py`, `validate.py`, `gennet.py`
  (the per-module pattern to lift to device granularity).
- **Existing descriptive registries** (the *outputs* the fabric is the source spec for) —
  `circuit-topology.json`, `registry-modules.json`, `CIRCUIT_WIRING.md`, and the bottom-up scanner
  `tools/circuit-introspection.py`.
- **The 15 graduated module netlists** the fabric binds — `.hft/<module>/<module>.net.json`.

## 8. Open decisions (flagged for the founder — do not silently choose)

1. **Domain-reference model** — independent per-device references with ppm drift, or one shared sim
   time base + explicit CDC (ARCHITECTURE.md §5a open decision). The fabric *declares* domains either
   way; which model it encodes is the founder's call. - independent per device preferred.
2. **Backplane redesign vs refactor** — §3 leaves "delete-and-redesign vs refactor the 14 flat
   sub-headers into the device hierarchy" pending. The fabric assumes the device hierarchy as target;
   confirm the migration path before generation. - no migration
3. **Whether `fabric` graduates to `.hft/`** like a module, or is a distinct top-level artifact —
   it references graduated modules rather than being one, so its vault status needs a founder ruling. favric will graduatte afer passing all design checks

---

## 9. Design Template & Examples

This section is the **concrete, ready-to-implement** template. Everything below is grounded in the
committed `.hft/<module>/<module>.net.json` files (read 2026-06-10). Every field name reused here
(`device`, `window_base`, `clock`, `kind`, `seam_nodes`, `wire_inputs`, `seam_inputs`, `tai_input`,
`source`, `sync1`/`sync2`) **already exists in a real module netlist** — no vocabulary is invented.

> The step-by-step device list, connection graph, and clock tree for the actual 15 modules live in
> the companion `.hft_staging/FABRIC_TEMPLATE.md`. This section gives the **netlist structure**, the
> **emitter skeleton**, and a **concrete assignment example**.

### 9.1 The `fabric.net.json` structure (inline-commented)

The fabric netlist mirrors a module netlist one level up: its **nodes are devices** and its **nets are
published register windows**. It has exactly three load-bearing sections — `devices`, `connections`,
`clock_domains` — plus a top-level identity, matching how a module netlist has `device`/`dff_nodes`/
`comb_nodes`/`wiring`.

```jsonc
{
  "device": "fabric",              // this netlist's identity (like every module's "device" field)
  "kind": "fabric",                // self-classification (modules use oscillator|cdc|order_book|…)
  "comment": "netlist-of-netlists: 15 graduated modules wired into 3 devices",

  // ── DEVICES ── the device map (ARCHITECTURE §3: backplane is a device map, not a module map).
  //    Each entry binds a graduated module netlist into a reserved backplane window.
  //    window_base / clock / kind are READ from the module's own *.net.json — not re-invented.
  "devices": {
    "adapter":      { "window_base": "0x1700000", "clock": "self",     "kind": "datapath",
                      "netlist": ".hft/adapter/adapter.net.json", "chip": "NIC_FPGA" },
    "wire":         { "window_base": "0x1800000", "clock": null,       "kind": "passive_bus",
                      "netlist": ".hft/wire/wire.net.json",       "chip": "NIC_FPGA" },
    "nic":          { "window_base": "0x1A00000", "clock": "mac",      "kind": "gateway",
                      "netlist": ".hft/nic/nic.net.json",         "chip": "NIC_FPGA" },
    "taisoc":       { "window_base": "0x1B00000", "clock": null,       "kind": "oscillator",
                      "netlist": ".hft/taiosc/taisoc.net.json",   "chip": "NIC_FPGA" },  // dir=taiosc, file/device=taisoc (⚠ §9.4.3)
    "tai":          { "window_base": "0x1C00000", "clock": null,       "kind": "counter",
                      "netlist": ".hft/tai/tai.net.json",         "chip": "NIC_FPGA" },
    "mac":          { "window_base": "0x1D00000", "clock": null,       "kind": "oscillator",
                      "netlist": ".hft/mac/mac.net.json",         "chip": "NIC_FPGA" },
    "internal":     { "window_base": "0x1E00000", "clock": null,       "kind": "oscillator",
                      "netlist": ".hft/internal/internal.net.json","chip": "PIPELINE_FPGA" },
    "tai_cdc":      { "window_base": "0x1F00000", "clock": null,       "kind": "cdc",
                      "netlist": ".hft/tai_cdc/tai_cdc.net.json", "chip": "NIC_FPGA" },
    "fifo_rx":      { "window_base": "0x2000000", "clock": null,       "kind": "cdc_fifo",
                      "netlist": ".hft/fifo_rx/fifo_rx.net.json", "chip": "SEAM" },
    "dom":          { "window_base": "0x2100000", "clock": "internal", "kind": "order_book",
                      "netlist": ".hft/dom/dom.net.json",         "chip": "PIPELINE_FPGA" },
    // ⚠ placeholder windows (0x0) — founder must assign real Pipeline-FPGA addresses (see §9.4)
    "candle":       { "window_base": "0x0", "clock": "internal", "kind": "module",
                      "netlist": ".hft/candle/candle.net.json",   "chip": "PIPELINE_FPGA" },
    "footprint":    { "window_base": "0x0", "clock": "internal", "kind": "market-data",
                      "netlist": ".hft/footprint/footprint.net.json", "chip": "PIPELINE_FPGA" },
    "tpo":          { "window_base": "0x0", "clock": "internal", "kind": "market-data",
                      "netlist": ".hft/tpo/tpo.net.json",         "chip": "PIPELINE_FPGA" },
    // ⚠ window collision with fifo_rx (both 0x2000000) — founder must reassign (see §9.4)
    "timeframe":    { "window_base": "0x2000000", "clock": "internal", "kind": "rollover",
                      "netlist": ".hft/timeframe/timeframe.net.json", "chip": "PIPELINE_FPGA" },
    "pip_resolver": { "window_base": "0x2000000", "clock": "mac",     "kind": "lookup",
                      "netlist": ".hft/pip_resolver/pip_resolver.net.json", "chip": "PIPELINE_FPGA" }
  },

  // ── CONNECTIONS ── each edge is a consumer sampling a producer's PUBLISHED window.
  //    "from" = producer.published_lane  "to" = consumer.input_field  (§4: the address IS the wire).
  //    "crossing" names the seam device when the edge crosses a clock domain (else null).
  "connections": [
    { "from": "adapter:deposit",   "to": "wire:bus",          "crossing": null,
      "comment": "adapter is sole writer of the wire window" },
    { "from": "wire:WIRE_*",       "to": "nic:wire_inputs",   "crossing": null,
      "comment": "nic samples the wire bus (8 lanes)" },
    { "from": "tai:TAI_IN",        "to": "nic:tai_input",     "crossing": "tai_cdc",
      "comment": "TAI value enters MAC domain via gray-code 2-FF; nic reads TAI_MAC, never raw tai" },
    { "from": "nic:seam_nodes",    "to": "fifo_rx:seam_inputs","crossing": null,
      "comment": "nic SEAM_* lanes; SEAM_STROBE fires the FIFO write" },
    { "from": "fifo_rx:head",      "to": "dom:fifo_head_lanes","crossing": "fifo_rx",
      "comment": "MAC→internal async FIFO; dom drains the head on FIFO_FIFO_RD_FIRE" },
    { "from": "dom:relay_levels",  "to": "candle:input",      "crossing": null,
      "comment": "indicators sample dom's 10-level ladder (edge declared once candle is placed)" }
  ],

  // ── CLOCK_DOMAINS ── many clocks, one reference; CDC at every boundary (§5).
  //    ratios are NAMED CONSTANTS, never loop counts. discipline: none (taisoc is exact by def).
  "clock_domains": {
    "taisoc":   { "kind": "reference",   "discipline": "none",
                  "comment": "authoritative TAI reference (GNSS-equivalent truth)" },
    "tai":      { "kind": "counter",     "reference": "taisoc",
                  "comment": "plain count of taisoc; the TIME VALUE" },
    "mac":      { "kind": "oscillator",  "freq_mhz": 125,
                  "comment": "SAMPLE/COPY rate (when nic reads the wire)" },
    "internal": { "kind": "oscillator",  "freq_mhz": 250, "ratio_to_mac": 2,
                  "comment": "pipeline rate; internal:mac = 2:1 as a constant" }
  },

  // ── SEAMS ── the explicit domain crossings (every cross-domain connection routes through one).
  "seams": [
    { "device": "tai_cdc", "from_domain": "tai", "to_domain": "mac",
      "mechanism": "gray-code 2-FF", "regs": ["TAI_SYNC1_GRAY", "TAI_SYNC2_GRAY"] },
    { "device": "fifo_rx", "from_domain": "mac", "to_domain": "internal",
      "mechanism": "async FIFO (gray 2-FF both sides)", "depth": 512 }
  ]
}
```

### 9.2 The `gen_fabric_net.py` emitter skeleton

Hand-written only (build-sequence law). It **reads** the 15 module netlists and **emits** the device
map as stdout — it invents nothing. Mirrors `gen_<module>_net.py` exactly, one granularity up.

```python
#!/usr/bin/env python3
"""gen_fabric_net.py — fabric EMITTER (hand-written).
Reads the 15 graduated module netlists in .hft/, emits fabric.net.json (device-level netlist) to stdout.
NEVER hand-writes the netlist content: window_base/clock/kind are READ from each module's own *.net.json.
Mirrors the per-module gen_<module>_net.py → <module>.net.json contract (DESIGN_GUIDE §3)."""
import json, glob, os, sys

VAULT = ".hft"   # graduated, immutable; the fabric binds these, never regenerates them

# Chip assignment + domain are the ONLY fabric-level design inputs (the rest is read from modules).
CHIP = {  # which XCVU13P chip each device lands on (CLAUDE.md "Project Identity")
    "adapter": "NIC_FPGA", "wire": "NIC_FPGA", "nic": "NIC_FPGA", "taisoc": "NIC_FPGA",
    "tai": "NIC_FPGA", "mac": "NIC_FPGA", "tai_cdc": "NIC_FPGA", "fifo_rx": "SEAM",
    "internal": "PIPELINE_FPGA", "dom": "PIPELINE_FPGA", "candle": "PIPELINE_FPGA",
    "footprint": "PIPELINE_FPGA", "tpo": "PIPELINE_FPGA", "timeframe": "PIPELINE_FPGA",
    "pip_resolver": "PIPELINE_FPGA",
}

DIR = {"taisoc": "taiosc"}   # ⚠ dir/file spelling mismatch: dir=taiosc, file/device=taisoc (§9.4.3)

def read_module(name):
    """Load a graduated module netlist; return its (device, window_base, clock, kind, path).
    Globs the dir so the taiosc/taisoc.net.json spelling mismatch is handled by *.net.json."""
    path = glob.glob(f"{VAULT}/{DIR.get(name, name)}/*.net.json")[0]
    m = json.load(open(path))
    clk = m.get("clock")
    clk = "self" if isinstance(clk, dict) else clk      # adapter has an inline clock dict
    return {"window_base": m.get("window_base"), "clock": clk,
            "kind": m.get("kind"), "netlist": path}

def build_devices():
    """Bind every graduated module into the device map (placement = the window it already declares)."""
    devs = {}
    for name in CHIP:
        d = read_module(name)
        d["chip"] = CHIP[name]
        devs[name] = d
    return devs

def build_connections(devs):
    """Declare each consumer→producer edge from the input fields present in each module netlist.
    A connection EXISTS because a consumer names a producer's published lane (§4). The crossing
    field is set when the edge spans clock domains (resolved via the seams table)."""
    edges = []
    # ingress chain, read from real input fields: wire_inputs, tai_input, seam_inputs, fifo_head_lanes
    edges.append({"from": "adapter:deposit", "to": "wire:bus",           "crossing": None})
    edges.append({"from": "wire:WIRE_*",     "to": "nic:wire_inputs",    "crossing": None})
    edges.append({"from": "tai:TAI_IN",      "to": "nic:tai_input",      "crossing": "tai_cdc"})
    edges.append({"from": "nic:seam_nodes",  "to": "fifo_rx:seam_inputs","crossing": None})
    edges.append({"from": "fifo_rx:head",    "to": "dom:fifo_head_lanes","crossing": "fifo_rx"})
    # indicator edges (dom relay_levels/tables → candle/footprint/tpo) declared once those are placed
    return edges

def build_clock_domains():
    """Many clocks, one reference; ratios as constants; no discipline (taisoc is exact)."""
    return {
        "taisoc":   {"kind": "reference",  "discipline": "none"},
        "tai":      {"kind": "counter",    "reference": "taisoc"},
        "mac":      {"kind": "oscillator", "freq_mhz": 125},
        "internal": {"kind": "oscillator", "freq_mhz": 250, "ratio_to_mac": 2},
    }

def build_seams():
    """Every domain crossing routes through exactly one seam device (tearing law)."""
    return [
        {"device": "tai_cdc", "from_domain": "tai", "to_domain": "mac",
         "mechanism": "gray-code 2-FF", "regs": ["TAI_SYNC1_GRAY", "TAI_SYNC2_GRAY"]},
        {"device": "fifo_rx", "from_domain": "mac", "to_domain": "internal",
         "mechanism": "async FIFO (gray 2-FF both sides)", "depth": 512},
    ]

def main():
    devs = build_devices()
    fabric = {
        "device": "fabric", "kind": "fabric",
        "comment": "netlist-of-netlists: 15 graduated modules wired into 3 devices",
        "devices": devs,
        "connections": build_connections(devs),
        "clock_domains": build_clock_domains(),
        "seams": build_seams(),
    }
    json.dump(fabric, sys.stdout, indent=2)   # emitter output IS the netlist (stdout, like modules)

if __name__ == "__main__":
    main()
```

> `validate_fabric.py` then enforces §3a (device-map integrity, single-writer, no-floating,
> clock-domain legality). It will **fail** on the placeholder/colliding windows below — correct
> behavior, the validator is doing its job — until the founder assigns real addresses.

### 9.3 Concrete assignment of the 15 modules to the 3 devices

| Chip | Domain | Modules (graduated) |
|---|---|---|
| **NIC FPGA** | `mac` (125 MHz) + `taisoc`/`tai` refs | `adapter`, `wire`, `nic`, `taisoc`, `tai`, `mac`, `tai_cdc` |
| **SEAM** (NIC↔Pipeline) | `mac`→`internal` | `fifo_rx` (write side MAC, read side internal) |
| **Pipeline FPGA** | `internal` (250 MHz) | `internal`, `dom`, `candle`, `footprint`, `tpo`, `timeframe`, `pip_resolver` |
| **CPU** | host | (none graduated yet) |

Verified end-to-end ingress path (every hop a published-window read, module barrier honored):
`adapter → wire → nic → fifo_rx → dom`, with the TAI value entering at `nic` via `tai_cdc`.

### 9.4 Open device-map findings (flagged for the founder — validator will block on these)

These are real conditions read from the netlists, surfaced rather than silently "fixed":

1. **Window collision** — `fifo_rx`, `timeframe`, `pip_resolver` all declare `window_base = 0x2000000`.
   Single-writer / no-overlap forbids this. **Decision needed:** real windows for `timeframe` and
   `pip_resolver`.
2. **Placeholder windows** — `candle`, `footprint`, `tpo` carry `0x0`. They graduated for logic
   correctness but were never address-placed. **Decision needed:** Pipeline-FPGA addresses.
3. **Name spelling (triple mismatch)** — the TAI oscillator lives in directory `.hft/taiosc/` but its
   netlist file is `taisoc.net.json` and its `device` field is `"taisoc"`; CLAUDE.md / ARCHITECTURE
   call it `taiosc`. The emitter globs the directory (`taiosc/*.net.json`) so it binds the real file
   regardless, but the `dir=taiosc / file=taisoc / device=taisoc` inconsistency should be reconciled.

Until 1–2 are resolved, `validate_fabric.py` correctly fails — the fabric is the place these
long-deferred address decisions finally get forced and recorded.
