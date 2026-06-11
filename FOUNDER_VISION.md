# Founder's Vision — C-as-RTL FPGA Architecture

> **Single source of truth** for the HFT pipeline architecture, synthesized from CLAUDE.md and hft_pipeline/ARCHITECTURE.md.
> This document is the canonical reference for all module design, FPGA fabric layout, and implementation decisions.

---

## 0. What This System Is

A **proprietary, hardware-oriented high-frequency trading pipeline**, built in C as a faithful model of custom silicon — **not software**.

The end target is a real **FPGA + CPU build**; the C model exists to **force determinism** that carries to that build. Model the hardware accurately and the determinism flows. **The code is not king — the machine is.**

**This is NOT a hedge-fund co-location racer.** We take raw broker data, **strip it**, **re-stamp it with our own time (TAI)**, and **derive our own L2/L3** market structure from raw quotes, for our own unique build. The edge is not latency; the edge is a **rock-solid, internally-consistent, trusted pipeline.**

**Current version:** 2.0.0-staging (emitter-first, netlist-generated device code)

---

## 1. The Build Model — Emitter-First, Flip-Flop Level

Every module is built using the identical **three-stage build-sequence law**:

```
STAGE 1: EMITTER (hand-written Python script: gen_<module>_net.py)
  Input:  Hardware spec (parts list, register addresses, cell connectivity)
  Output: <module>.net.json (netlist, run: python3 gen_<module>_net.py > <module>.net.json)

STAGE 2: NETLIST (JSON: <module>.net.json — PRODUCED OUTPUT, COMMITTED)
  Source: Output of gen_<module>_net.py
  Validate: python3 validate.py <module>.net.json (enforces single-writer, no-overlap, no-floating)

STAGE 3: GENERATOR (hand-written Python script: gennet.py)
  Input:  <module>.net.json
  Output: <module>_gen.h (run: python3 gennet.py <module>.net.json > <module>_gen.h)
```

**Build-Sequence Law (enforced by gate stage 2c):**
- `<module>.net.json` is PRODUCED by the emitter; NEVER hand-written.
- `<module>_gen.h` is PRODUCED by gennet from the netlist; NEVER hand-written.
- Both are COMMITTED to git (proof that the circuit was generated, not hand-coded).
- Clean-room rebuild: running the three commands above must byte-match the committed files.

**Critical Rule: Specification Completeness Before Code Generation**

A specification is complete **ONLY** if it includes:
1. **Register state** (dff_nodes, tables, history_ring)
2. **Input interface** (cross_module_inputs)
3. **Output interface** (seam_nodes)
4. **Combinational logic** (comb_nodes with explicit cell definitions) — **LOAD-BEARING**
5. **Wiring** (signal flow between logic blocks) — **LOAD-BEARING**

Without items 4-5, the emitter produces stubs (register declarations with no logic), and the device fails silently at test/runtime.

---

## 2. The Goal — Why This Architecture

Determinism + fabric-as-wiring + self-contained modules buys:
- **Swap** modules, strategies, and risk profiles **without rebuilding** the pipeline.
- **Clone ingress** to observe **two sources or two symbols** at once.
- Run **many strategies reading the same registers simultaneously.**
- A **trusted system** — build it again and it behaves identically. Reproducibility = trust.

---

## 3. Devices & The Backplane

The system is a set of physical **devices on a backplane (the motherboard)**:

1. **NIC FPGA** (125 MHz MAC clock) — boundary between external market data and the internal system: market-data ingestion, feed handling, network-facing logic, clock-domain interaction for incoming data.
2. **Pipeline FPGA** (250 MHz internal clock) — the core trading modules: DOM, indicators, historical memory, analytics, strategy, risk, OMS, outbound.
3. **CPU** — system management: display/UI control, configuration, startup/init, power, admin/control-plane.
4. **GPU** — the **display device** (boundary concept; we do **not** drive real GPU hardware). It is where the TUIs are rendered. Its own clock domain, no compute.

### The Backplane = Reserved Memory, Nothing More

The backplane is a block of **reserved physical address space**: "machine, give me N bytes" → a base address → that region holds every device's registers. **No logic, no business rules, no data-format awareness, no replay awareness.** Memory + an address map.

**Hierarchy (intended end-state):** Only the **devices** explicitly live on the backplane; each device's **modules wire *into* the device** (registers nested inside the device's reserved region). Modules are **not** flat peers on the backplane. The backplane is a **device map, not a module map**.

---

## 4. Modules = Tiny Self-Contained Programs; The Fabric Is The Wiring

- These are **tiny independent programs/workflows on their own.** Each module's clock-edge body is: **read my inputs from the fabric → compute → write my outputs to the fabric.** It **includes no other module, calls no other module, knows only its own registers.**
- **It is NOT one giant program with one entry point that every file slaves to.** Real silicon has no `main()`. There is a clock, and every block does its own thing on every edge.

### The Register Fabric IS The Wiring

On an FPGA, once you place modules, the fabric routes the registered signals — you don't hand-wire them. Here the equivalent: a module reads its input registers and writes its output registers at known addresses, and **any module reading those addresses is wired to it by that fact**, through the shared backplane. **Placement = connectivity.**

**Why you shouldn't still be wiring modules together after placing them:** the explicit memory assignments, registers, and addresses are *meant* to be the wiring already, by design — same as an FPGA fabric. There should be no separate wiring step, no hand-maintained dependency table.

**The commitment that makes this real:** all cross-module communication is **registered** (one clock per hop, like a real pipeline). Every block reads the previous cycle's frozen state → **evaluation order is irrelevant** → run the blocks in any order each tick, identical result.

---

## 5. The Clock — The System's Sole Driver

**The only external verb is: power on the backplane.** Power-on → the crystal oscillates → PLLs lock → clocks distribute → on every clock edge every module does READ→COMPUTE→WRITE. **The system performs because it is powered and clocked.**

### Clock Hierarchy — Many Clocks, One Reference

- Real hardware: a **crystal oscillator** is a *low-frequency reference* (≈24 / 38.4 MHz) fed to a **PLL** that **multiplies** it to the operating frequency. A clock is **phase-locked and multiplied** from its reference.
- There can be **multiple references.** CPU derives from the board crystal. A GPU/PCIe device may share the host 100 MHz reference or use its **own** reference (SRIS, spread-spectrum).
- **CPU, GPU, NIC are independent clock domains.**
- Ratios (e.g. 2:1 pipeline:MAC) are **real derived constants**, never a `for`-loop repetition count.
- **TAI** is our internal re-stamped time, **disciplined off the reference** (the GNSS/PPS PI loop in `time_source` is the *one* legitimate writer). **Broker time is discarded** except for NIC sync.

### Our Deterministic Model

Derive every domain's clock from one simulation time base (so the sim is reproducible) **while explicitly modeling the CDC** between domains (so the real independence is captured).

### Critical: TAI ≠ MAC

- **MAC clock = the SAMPLE/COPY RATE** (when the NIC reads the wire).
- **TAI = the TIMESTAMP VALUE**, a *separate clock with its own oscillator*.
- **The NIC samples on the MAC tick and stamps with TAI's value brought into the MAC domain via CDC.**
- **MAC ≠ TAI — never conflate the sample clock with the time clock.**

### No Clock Discipline (Deterministic Model)

**`taiosc` IS the authoritative reference; `tai` is a PLAIN counter off `taiosc`; one deterministic time base ⇒ NO PPS, NO PI loop, NO per-domain discipline anywhere.** Discipline only returns if we deliberately model oscillator drift — we do not.

---

## 6. The Wire & Ingress Chain

**Data provider → adapter → wire → port pins → NIC PHY → NIC/MAC → CDC/SLR seam → pipeline.**

- **The adapter sits BEFORE the wire**, between the data provider and the wire. Its job: take provider data and **put it on the wire** (serialize into the PHY frame) and drive the port.
- **The NIC then reads the wire off its port** — it does **not** have data "piped into" it.
- **What is in the wire:** digital packets in **our own proprietary binary PHY frame** — we own both ends, so TCP is irrelevant. The frame is minimal: bid/ask price + qty + side + framing.
- **Each data source needs its own connector** that plugs into the adapter: it parses ITS native format and emits the canonical internal form.
- **What the system actually needs from a source: bid data and ask data. That is all.**
- The **NIC↔HFT boundary *is* the CDC/SLR crossing** — true even when NIC and HFT logic sit on the same FPGA.

### Testbench ≠ Device

The device powers on and runs on its clock. If external stimulus is needed it drives the NIC **input pins from outside** and observes outputs — it **never lives inside the device.** `replay / source-type / CSV / file` must **never** appear in device registers or the device address map.

---

## 7. THE DATA LAW — Bid/Ask Only

- **There is no "price." There is bid price and ask price, always, explicitly labeled.**
- **No combined metrics as decision inputs. No mid price as a decision basis.** (Mid may never trade.)
- **No buy/sell inference** — bids and asks are resting quantities; they never cross the spread.
- Every price-bearing field, register, and decision states **bid or ask explicitly.**
- **Derived convenience metrics (mid, spread) ARE allowed** — but **only** as read-only values nothing gates on (non-blocking, off every critical path).

---

## 8. Timeframe — A Guide, Not A Master

`timeframe` is a **reference** bar clock derived from our internal clock (TAI) that the bar modules take their cue from. **But modules are NOT slaved to it.**

Each bar module carries **its own multiple** of the base timeframe (e.g. candle on 2×, footprint on 0.5×) in its **own period register**, and closes its own bars accordingly. They are independent hardware blocks; the binary/register design is exactly what makes per-module timeframe scaling possible without coupling.

---

## 8a. The Index Doctrine — One Quantum; Price & Time Are Indices, Not Stored Data

The deepest law of the data model. **There is one fundamental unit: the internal
clock tick.** Everything else is built from it, and price is an *index*, not a
stored coordinate.

- **One quantum: the internal clock tick — the SOLE DRIVER of computation.** Every
  internal register computes on internal clock ticks. **This is NOT `taiosc`.**
  `taiosc` is a *separate* free-running oscillator; `tai` (its accumulated tick-tock
  value) is the **TAI timestamp**, the value **ingress stamps onto external data**.
  **TAI is timestamped *data*, not a controller** — it does not drive or step any
  internal module. On each internal clock tick the registers compute, interacting
  with the TAI-stamped data that arrived through ingress. (Two distinct things:
  the internal clock = the compute heartbeat; `taiosc`/`tai` = the timestamp source.)
- **Every "time frame" is a bounded count of internal clock ticks.** `timeframe`
  counts **internal clock ticks** and rolls `BAR_SEQ` at the period — a **bar is N
  internal ticks**, a coarsened stride on the one internal-tick axis, not a separate
  axis. **DOM** lives at the raw internal tick (stride 1, the live book);
  **candle / footprint / tpo** live at the bar (accumulated then snapshotted).
- **Price is a DIRECT index — no offset, no origin, no anchor.** The price value,
  at pip granularity (`pip_resolver` publishes the pip = the separation between
  adjacent price-indices), **is** the address. Nothing is measured relative to a
  reference price; there is **no `price − origin`** and **no absolute price** (a
  human/charting abstraction that does not apply here). The structure **expands and
  shrinks to exactly the prices the frame covered** — and the frame's bounded
  tick-count is the *only* bound (there is no price-span cap or canvas size to set).
- **Modules are price-indexed activity counters.** Each stores a *measure* at a
  price-index — DOM: physical book activity per pip per tick; footprint: volume per
  pip per bar; tpo: time-touches per pip per bar; candle: the bar's pip-extremes.
- **DOM is the source payload; each module does its OWN counting — nothing is lifted.**
  The **DOM snapshot is the enriched per-internal-tick, all-price payload** (the *what
  happened at each price this tick*). footprint/tpo/candle each keep **their own
  counters** and **count *from* that payload** into their own registers, bounded by
  their own timeframe — they do **not** read DOM's derived aggregates. A module's
  outputs are computed from *its own* accumulation: footprint's POC/VAH/VAL/HVN/LVN
  come from footprint's own bid/ask counts, candle's total volume from candle's own
  counter, tpo's touches from tpo's own tally. **DOM's POC ≠ footprint's POC** — they
  are scoped to different time bounds; lifting a DOM aggregate into an indicator is a
  bug. Because **DOM and every module compute on the same internal clock**, each
  counter advances in lockstep with DOM's per-tick payload, so **no tick is lost** —
  the independent counts are complete and consistent. "footprint is DOM bounded by a
  timeframe" means footprint runs DOM's *kind* of counting, sourced from DOM's payload,
  on its *own* state over its *own* bar.
- **Price is stored as a VALUE only when it is the measured quantity** (candle OHLC,
  a published POC). When price is the **axis** it is the *address*, never data — so:
  **no allocation, no free-slot search, no stored price keys, no anchor/window
  subsystem.** The index *is* the match; the position *is* the price.
- **Price may be referenced ONLY against time — never against price, never absolute.**
  If a price value is needed, it is defined by a *time event*: `open` = price at frame
  start, `high` = highest during the frame, `low` = lowest during the frame, `close` =
  last price at frame end; DOM bid/ask counters = TAI-timestamped market events **per
  internal clock tick**. No price-vs-price offset, no absolute-price anchor — ever.
  **Immutable and enforced at every level** (spec, emitter, gate); a violation halts
  development until corrected.
- **History is a record store, not an index construct.** A historical module's memory
  is a bank of stored records in flip-flops; **each record carries its own intrinsic
  coordinates — commit time and price data — as stored fields.** There is NO index
  construct: no write-pointer counter, no address decoder, no allocation, no managed slot.
  A committed bar is stored (e.g. shift-in); its identity is the **time it carries**, not
  a slot. **Browsing/querying is a separate module** (its own build task) that scans the
  records in parallel hardware, compares on the intrinsic attribute (e.g. highest high),
  and names the result by its **time** (the most unique identifier other than price). The
  "index" is a *reference frame over data already present*, not infrastructure to build —
  do not import generalist DB/indexing habits.
- **`pip_resolver` owns nothing** — a per-symbol lookup publishing the pip size (the
  price-index separation unit). `timeframe` is a tick accumulator (the bar stride).
  Neither is an axis authority; **time (tick-count) is the only persistent reference.**

Two clock roles, never conflated: **`taiosc → tai`** produces the **TAI timestamp**
(stamped onto external data at ingress — data, not a driver); the **internal clock**
drives *all* computation, and `timeframe` counts **internal** ticks into bars. Time
the system *references on data* is TAI; time that *drives* the system is the internal
clock; every module projects price-indexed activity onto that one internal-tick axis.
(CLAUDE.md Law #10;
`memory/index_doctrine_price_time_as_index.md`.)

---

## 9. Non-Negotiable Rules (Data Path)

- **No floats anywhere.** All prices are fixed-point integers (e.g. `uint64_t price_bps` = price × 10000).
- **No malloc/calloc.** Stack or static fixed arrays only.
- **No dynamic dispatch.** No function pointers in the data path.
- **No native `+`/`-`/`*` in generated ticks.** Use `cell_addsub`, `cell_mul`, `cell_shift` (structural cells).
- **No native `==`/`!=`.** Use `cell_eqmask` (comparator cells).
- **No `?:` ternary.** Use `cell_mux` (multiplexer cells).
- **No `if`/`else` in data path.** Flatten all logic with bitwise boolean algebra into gate chains.
- **No nested conditionals.** All branches are one-level deep (MUX selectors).
- **No loops over bits.** Use `__builtin_popcountll`, `__builtin_ctzll`, `__builtin_clzll`.
- **No function calls in tick.** All logic is inline gate algebra.

### Generated Code

- **Device tick is GENERATED ONLY** (gennet output in `<module>_gen.h`). NEVER hand-written.
- **No `cell_*()` in source files.** All cells are generated from the netlist.
- **`*_gen.h` IS COMMITTED to git** (build-sequence law, not gitignored).
- **Netlist validates the circuit** (`validate.py` enforces single-writer, no-overlap, no-floating).
- **Byte-identical rebuilds** — clean-room gate stage confirms the circuit hasn't drifted.

### Module Barrier

- **No cross-module register reads.** Modules sample only published windows (passive addressed-memory buses).
- **Single writer per register.** A register is owned by one module; no concurrent writes.
- **Hierarchy:** Producer publishes a window (relay lanes), consumer samples it (no private copies).

### Testing

- **Thin test only:** power-on + display (no clock stepping, no data injection, no orchestration).
- **Test file ≤45 lines** (enforced by pre-commit hook).
- **No manual gate primitives in tests.** Tests call generated tick functions; don't build the circuit.

---

## 10. Current Code Status — Diseases to Remove

The market-state *core* is largely sound (DOM ladder, CDC/SLR seam, NBA-registered hops, time discipline, indicator structures, register fabric concept). The drift is concentrated in 9 diseases (see hft_pipeline/ARCHITECTURE.md §11):

1. `sim_feed_loop` — replay harness fused into device
2. TAI fast-forward from feed timestamps
3. Ghost values (`is_buy/is_sell/is_trade` inferred)
4. Replay concepts in device map
5. Backplane fragmentation (14 per-module sub-headers)
6. Host-thread display coupling
7. Candle reads DOM blended price
8. Timeframe single shared clock
9. Manual wiring (`CLK_DEP_TABLE`)

**Policy:** Code built on a wrong/rejected design is **DELETED and rebuilt fresh — NEVER patched/retrofitted.** Patching carries the flawed assumption forward. Architecture is king.

---

## 11. Critical Rule: No AI Attribution

**This project rejects all AI co-authoring markers.** Do not include `Co-Authored-By`, `GENERATED`, comments about Claude, or any AI attribution in commits, code, or documentation.

Commits carry the user's name only. This is enforced and non-negotiable.

---

## 12. Graduated Modules (15 Total, Flip-Flop Realized)

**Ingress Chain (verified order-free, fully pipelined):**
- `adapter` (208 cells) — source; timestamp-paced CSV parser; deposits price-only packet into wire bus
- `wire` (0 cells) — passive addressed-memory bus; sole writer = adapter
- `taiosc` (5 cells) — authoritative TAI oscillator; free-running, no discipline
- `tai` (4 cells) — plain TAI counter; off taiosc, no PI/PPS
- `mac` (5 cells) — 125 MHz NIC sample/copy-rate clock
- `internal` (5 cells) — 250 MHz pipeline clock
- `tai_cdc` (12 cells) — gray-code 2-FF CDC of tai into MAC domain
- `nic` (180 cells) — samples wire, dedup by seq, stamps tai_cdc, strobes nic→fifo seam
- `fifo_rx` (8211 cells) — MAC→internal async CDC FIFO; 512-slot packet-wide, dual gray-code 2-FF sync

**Pipeline Modules:**
- `dom` (212 cells) — price-indexed order book; 16384-entry tables, best-price tracking, relay ladder
- `candle` (64 cells) — bid/ask OHLC bars; 256-bar history ring; per-module multiplier
- `footprint` (88 cells) — POC/VAH/VAL + imbalance; per-module multiplier
- `tpo` (72 cells) — time-per-price accumulator; per-module multiplier
- `timeframe` (8 cells) — base period tick generator; reference for all bar modules
- `fractal` (15 cells) — 5-bar pivot detector; fractals up/down
- `cbr` (18 cells) — cross-bar deltas; volume, true range, cumulative delta

**Total:** ~9,600 cells (flip-flop level, all validated through gate stage 2d)

---

## 13. References

- **CLAUDE.md** — Project instructions and quick commands
- **hft_pipeline/ARCHITECTURE.md** — Full detailed architecture (§1-§11)
- **.hft_staging/DESIGN_GUIDE.md** — Step-by-step build methodology
- **.hft_staging/FABRIC_ARCHITECTURE.md** — FPGA fabric design (device map, netlist, generation)
- **.hft/*/*.net.json** — Module netlists (source of truth for real structure)

---

## 14. Next Steps

1. **Design the FPGA fabric** — device hierarchy, address allocation, module assignments (ground in real-world FPGA spec, not hft_pipeline/)
2. **Build meta-tools** — gen_fabric_net.py (emitter), validate_fabric.py (validator), gennet_fabric.py (generator)
3. **Generate realized backplane** — fabric_gen.h (the wired FPGA in C)
4. **Verify end-to-end** — all 15 modules wired and executing order-free, fully pipelined
