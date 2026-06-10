# FABRIC_TEMPLATE.md — Step-by-step design of the actual FPGA fabric

> Companion to `FABRIC_ARCHITECTURE.md` (the methodology). This file is the **concrete design
> spec template**: the device list, the connections, and the clock tree for the real 15 graduated
> modules, expressed in the **same netlist idiom the modules already use** (no invented vocabulary).
>
> Grounded directly in the committed `.hft/<module>/<module>.net.json` files (read 2026-06-10).
> Every field name below is one that already appears in a real module netlist — `device`,
> `window_base`, `clock`, `kind`, `seam_nodes` (with `name`/`from`/`type`), `wire_inputs`,
> `seam_inputs`, `nic_inputs`, `tai_input`, `source`, `sync1`/`sync2`, `relay_levels`, `tables`.

---

## 0. Vocabulary note (read first — prevents drift)

The fabric uses **only** terms the founder's docs and the real netlists already use:

| Concept | Real netlist field(s) it comes from | Do NOT call it |
|---|---|---|
| A device on the backplane | `device`, `window_base`, `kind` | "slot", "instance container" |
| A published register window (producer output) | `seam_nodes`, `out_nodes`, `bus_nodes`, `relay_levels`, `tables`, `deposit` | "port", "pin" |
| A consumer sampling a producer | `wire_inputs`, `seam_inputs`, `nic_inputs`, `tai_input`, `source`, `fifo_head_lanes` | "pin map" |
| A clock-domain crossing | `kind: cdc` / `cdc_fifo`, `sync1`/`sync2` `{reg, from}` | "route latency" |

> The earlier `FPGA_TEMPLATE_STRATEGY.md` proposal used `slot`/`pin`/`pin_pool`/`io_standard`
> vocabulary. Those terms are **not** in any module netlist or in ARCHITECTURE.md §2–§5. This template
> deliberately does not adopt them — the addresses ARE the pins (§4: placement = connectivity).

---

## 1. Device list (the 15 graduated modules, grounded addresses)

Read straight from the committed netlists. `window_base` and `clock` are the module's own declared
values; `kind` is the module's own self-classification.

| Device | `window_base` | `clock` | `kind` | Role |
|---|---|---|---|---|
| `adapter` | `0x1700000` | self (ADP_CLK free-run) | (datapath) | CSV source → price packets; sole writer of wire window |
| `wire` | `0x1800000` | — | `passive_bus` | addressed-memory bus (no clock, no logic) |
| `nic` | `0x1A00000` | `mac` | `gateway` | samples wire + TAI, re-stamps, strobes seam |
| `taisoc` | `0x1B00000` | — | `oscillator` | authoritative TAI reference (dir `taiosc/`, file/device `taisoc` ⚠ §3) |
| `tai` | `0x1C00000` | — | `counter` | plain counter off `taisoc` (no discipline) |
| `mac` | `0x1D00000` | — | `oscillator` | 125 MHz sample-rate clock |
| `internal` | `0x1E00000` | — | `oscillator` | 250 MHz pipeline clock |
| `tai_cdc` | `0x1F00000` | — | `cdc` | gray-code 2-FF: `tai` value → MAC domain (`TAI_MAC`) |
| `fifo_rx` | `0x2000000` ⚠ | — | `cdc_fifo` | MAC→internal async FIFO (gray 2-FF both sides) |
| `dom` | `0x2100000` | `internal` | `order_book` | 16384-entry price tables; 10-level relay ladder |
| `candle` | `0x00000000` ⚠ | — | `module` | OHLC bars (placeholder window — unassigned) |
| `footprint` | `0x00000000` ⚠ | — | `market-data` | POC / imbalance (placeholder window) |
| `tpo` | `0x00000000` ⚠ | — | `market-data` | time-per-price (placeholder window) |
| `timeframe` | `0x2000000` ⚠ | — | `rollover` | bar rollover (placeholder window — collides) |
| `pip_resolver` | `0x2000000` ⚠ | `mac` | `lookup` | pip-size lookup (placeholder window — collides) |

### ⚠ Open device-map findings (the fabric validator's job to enforce — flagged, not silently fixed)

1. **Window collision** — `fifo_rx`, `timeframe`, and `pip_resolver` all declare
   `window_base = 0x2000000`. Three devices cannot own one window (single-writer / no-overlap law).
   The fabric's `validate_fabric.py` device-map check must reject this until real windows are
   assigned. **Founder decision needed:** the real address for `timeframe` and `pip_resolver`.
2. **Placeholder windows** — `candle`, `footprint`, `tpo` carry `window_base = 0x00000000`. These were
   graduated for *logic correctness* (cell-count > 0) but never address-placed. The fabric is where
   they get their device address. **Founder decision needed:** Pipeline-FPGA addresses for these three.
3. **Name spelling (triple mismatch)** — the TAI oscillator lives in directory `.hft/taiosc/`, but its
   netlist file is `taisoc.net.json` and its `device` field is `"taisoc"`; CLAUDE.md / ARCHITECTURE
   call it `taiosc`. The emitter globs the directory so it binds the file regardless, but the
   `dir=taiosc / file=taisoc / device=taisoc` inconsistency should be reconciled.

These are exactly the conditions §3a of FABRIC_ARCHITECTURE.md says the validator catches
(device-map integrity, single-writer, no-overlap). Surfacing them is the template working as designed.

---

## 2. The connections (grounded producer → consumer edges)

Each edge below is read from a real netlist field. A connection is **declared** by the consumer naming
the producer's published lane — that naming **is** the wire (§4).

```
adapter ──deposit──▶ wire(0x1800000)            adapter.writeout/deposit → wire.bus_nodes
                                                 (adapter is the SOLE writer of the wire window)

wire ──WIRE_*──▶ nic                             nic.wire_inputs = [WIRE_BID_PX, WIRE_ASK_PX,
                                                   WIRE_TIME, WIRE_SYMBOL, WIRE_PIP,
                                                   WIRE_COMMISSION, WIRE_SEQ, WIRE_VALID]

tai ──TAI_IN──▶ tai_cdc ──TAI_MAC──▶ nic         tai_cdc.source = "TAI_IN"
                  (gray 2-FF)                     tai_cdc.sync1 = {reg: TAI_SYNC1_GRAY, from: TAI_GRAY}
                                                 tai_cdc.sync2 = {reg: TAI_SYNC2_GRAY, from: TAI_SYNC1_GRAY}
                                                 nic.tai_input  = "TAI_MAC"   (in-domain, never raw TAI)

nic ──SEAM_*──▶ fifo_rx                          nic.seam_nodes[].name = SEAM_BID_PX, SEAM_ASK_PX,
                  (each seam_node: {name,           SEAM_TIME, SEAM_SRC_TIME, SEAM_SYMBOL,
                   from, type, comment})            SEAM_PIP, SEAM_COMMISSION, SEAM_SEQ, SEAM_STROBE
                                                 fifo_rx.seam_inputs = [SEAM_BID_PX, ... SEAM_STROBE]
                                                 fifo_rx.write_side.fire_from = "SEAM_STROBE"

fifo_rx ──head lanes──▶ dom                      dom.fifo_head_lanes = [BID_PX, ASK_PX, TIME,
                  (MAC→internal CDC FIFO)           SRC_TIME, SYMBOL, PIP, COMMISSION, SEQ]
                                                 dom.fifo_fire  = "FIFO_FIFO_RD_FIRE"
                                                 dom.fifo_empty = "FIFO_FIFO_EMPTY"

dom ──relay_levels / tables──▶ (indicators)      dom publishes relay_levels (10-level ladder) +
                                                   tables; candle/footprint/tpo sample these once
                                                   placed (their input edges are not yet declared)
```

**End-to-end ingress chain (verified against netlists):**
`adapter → wire → nic → fifo_rx → dom`, with the TAI value entering at `nic` via `tai_cdc`.
This is the §2 ingress payoff path; every hop is a published-window read, no hop is a direct
cross-module register read (module barrier honored).

**Crossing inventory (where domains meet — must pass through a seam device):**

| Crossing | Seam device | Mechanism | Validated by |
|---|---|---|---|
| `internal`(tai) → `mac`(nic) for the TAI value | `tai_cdc` | gray-code 2-FF (`sync1`→`sync2`) | clock-domain-legality check |
| `mac`(nic) → `internal`(dom) for the packet | `fifo_rx` | async FIFO, gray 2-FF both sides | clock-domain-legality check |

No other edge crosses a domain. Every multi-bit cross-domain value (`tai`) goes through a `cdc`/
`cdc_fifo` device — the tearing law is satisfied structurally.

---

## 3. The clock tree (domains, references, ratios)

Grounded in the `kind: oscillator|counter|cdc` devices and CLAUDE.md's two-clock model.

```
taisoc (oscillator, authoritative reference — the GNSS-equivalent truth)
   │  no discipline anywhere: taisoc IS exact by definition
   └─▶ tai (counter)  ── plain count of taisoc; the TIME VALUE

mac (oscillator, 125 MHz)      ── the SAMPLE/COPY RATE (when nic reads the wire)
internal (oscillator, 250 MHz) ── pipeline rate; ratio internal:mac = 2:1 (named constant, never a loop)

Domain assignment of devices:
  mac domain:       nic, pip_resolver        (clock: "mac")
  internal domain:  dom                        (clock: "internal")
  self/source:      adapter (free-running ADP_CLK paced by source timestamps)
  no clock (memory/ref): wire, taisoc, tai, mac, internal, tai_cdc, fifo_rx
  unassigned (placeholder): candle, footprint, tpo, timeframe
```

**Rules the clock tree encodes (from CLAUDE.md "Clock domain separation (absolute)"):**
- `mac ≠ tai`: the sample clock is not the time clock. `nic` samples on `mac`, stamps with the TAI
  value brought in via `tai_cdc` (read as `TAI_MAC`, never raw `tai`).
- No discipline (no PPS, no PI loop): `taisoc` is the one deterministic base; `tai` just counts it.
- The 2:1 internal:mac ratio is a **real constant**, not an iteration count.

**Founder open decision (FABRIC_ARCHITECTURE.md §8.1, noted as resolved "independent per device"):**
each device's reference is independent (with ppm drift if modeled); the fabric *declares* the domains
either way. This template encodes independent-per-device references.

---

## 4. Device assignment to the 3 chips (XCVU13P layout)

Grounded in CLAUDE.md "Project Identity" (NIC FPGA / Pipeline FPGA / CPU) and the real domains above.

| Chip | Domain | Devices assigned (graduated only) | Notes |
|---|---|---|---|
| **NIC FPGA** | `mac` (125 MHz) + `taisoc`/`tai` refs | `adapter`, `wire`, `nic`, `taisoc`, `tai`, `mac`, `tai_cdc`, `fifo_rx`(write side) | ingress + wire sampling + dedup + TAI stamp |
| **Pipeline FPGA** | `internal` (250 MHz) | `internal`, `fifo_rx`(read side), `dom`, `candle`, `footprint`, `tpo`, `timeframe`, `pip_resolver` | order book + indicators |
| **CPU** | host | (none graduated yet) | host control / instrumentation |

> `fifo_rx` straddles the NIC→Pipeline SLR/domain seam by design (write side = MAC, read side =
> internal). That is exactly what a `cdc_fifo` device is — it is assigned to the seam, not to one chip.
> `pip_resolver` declares `clock: mac` but its placeholder window collides with `fifo_rx` — its chip
> assignment is provisional until finding §1.2 is resolved by the founder.

---

## 5. How this becomes `fabric.net.json` (the emitter's job)

The emitter `gen_fabric_net.py` does **not** invent any of the above — it **reads** the 15 module
netlists and re-expresses §1–§4 as one device-level netlist. See FABRIC_ARCHITECTURE.md §9 for the
`fabric.net.json` structure and the `gen_fabric_net.py` skeleton. The build sequence is the same
three-stage law as every module:

```sh
cd .hft_staging/fabric
python3 gen_fabric_net.py > fabric.net.json        # emitter reads .hft/*/*.net.json, emits device map
python3 validate_fabric.py fabric.net.json         # device-map + single-writer + no-floating + CDC legality
python3 gennet_fabric.py fabric.net.json > fabric_gen.h   # realize the wired FPGA in C
```

The validator will **fail** on the three findings in §1 (window collision, placeholder windows) until
the founder assigns real addresses — which is the correct behavior, not a bug.
