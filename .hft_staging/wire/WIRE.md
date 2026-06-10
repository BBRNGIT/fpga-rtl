# WIRE — a passive addressed-memory bus (the adapter -> NIC boundary)

Grounded in: `INGRESS_FLOW.md` §1 (price-only packet) / §2 (the adapter is the sole writer) / §3
(rewritten: "The wire — a passive addressed-memory bus") / §4 (the NIC samples it), `BLOCK_DIAGRAM.md`
(wire row #1w + the chain; lane law), memory `feedback_hft_wire_and_barrier`. Template:
`.hft_staging/adapter/` (structure only — the wire has no device logic to template).

## What the wire IS (the corrected model — build to this exactly)

The wire is a **PASSIVE addressed-memory bus** in its **own window**. It has **NO clock, NO compute,
NO logic of its own** — it is just addressed storage holding the price-only packet (the lanes in §1).
Structurally it is memory (a held, addressed value); it behaves like a wire: **non-blocking, 1-deep**
(the latest packet, overwritten freely). **The wire writes nothing itself.**

- **Single writer = the ADAPTER.** The adapter's WRITE phase **deposits** the price-only packet
  directly into the wire window — it *drives* the bus. The `WIRE_*` registers live **here, in the wire**
  — not in a private adapter copy the NIC would reach into.
- **Reader = the NIC**, which **samples** the wire on the `mac` cadence (gated by `WIRE_VALID`, deduped
  by `WIRE_SEQ`).
- **Why the wire is required (not optional):** a module may **not read another module's registers
  directly** (`feedback_hft_wire_and_barrier`). The wire is the **barrier/medium** both sides meet at —
  the adapter drives it, the NIC samples it, neither reaches into the other's internal state.

This **discards** the first build's mistake: there is no `WIRE_CLK`, no `STROBE`, no `cell_dff` latch,
no wire-owned clock/tick. The wire is passive; the **adapter** is the sole writer.

## Block diagram

```
  ADAPTER (its own window, 0x1700000) — the SOLE WRITER of the wire bus
    its branchless WRITE phase DEPOSITS the price-only packet into ▼
  ┌─ WIRE BUS (its own window, 0x1800000) ─────────────────────────────┐
  │  PASSIVE addressed memory — NO clock, NO compute, NO latch.         │
  │  Eight lanes (the price-only packet), 1-deep, overwritten freely:   │
  │   WIRE_BID_PX WIRE_ASK_PX WIRE_TIME WIRE_SYMBOL                     │
  │   WIRE_PIP WIRE_COMMISSION WIRE_SEQ WIRE_VALID                      │
  │  The wire writes nothing itself — it is just held, addressed storage.│
  └───────────────┬────────────────────────────────────────────────────┘
        │  the NIC SAMPLES the bus (it may not read the adapter's regs — the
        ▼   wire is the barrier between them)
  NIC DEVICE  ── reads WIRE in time with mac · dedup by WIRE_SEQ · stamps tai → fifo
        SEAM ▼  CDC/FIFO is DOWNSTREAM (NIC->DOM); the wire->NIC hop is same-domain (MAC)
```

## Register table — price-only (INGRESS_FLOW §1), the wire's OWN window

| register (lane) | type | meaning |
|---|---|---|
| `WIRE_BID_PX`     | fixed-point u64 | bid price |
| `WIRE_ASK_PX`     | fixed-point u64 | ask price |
| `WIRE_TIME`       | u64 | source time |
| `WIRE_SYMBOL`     | u64 | symbol id |
| `WIRE_PIP`        | fixed-point u64 | pip value |
| `WIRE_COMMISSION` | fixed-point u64 | commissions |
| `WIRE_SEQ`        | u64 | source sequence number (NIC dedup key) |
| `WIRE_VALID`      | 1 | a new packet is present on the bus |

No spread, no bid qty, no ask qty, no side — DOM rebuilds those downstream (`INGRESS_FLOW.md` §1).
There are **no config / input / comb / dff / clock nodes** — a bus has no logic, only lanes.

## Single-writer / reader contract

- **Single writer of `WIRE_*` = the ADAPTER** (its WRITE phase deposits into this window). The wire
  itself offers **no write path** — it cannot write its own lanes. This is what makes it a *passive*
  bus, and it structurally guarantees the single-writer law (no second writer exists).
- **Reader = the NIC** (off the `mac` clock, gated by `WIRE_VALID`, deduped by `WIRE_SEQ`).
- The wire is the **barrier**: the NIC samples the bus, never the adapter's private registers; the
  adapter drives the bus, never the NIC's internals.

## Clock domain / CDC boundary

- The wire has **NO clock** — it is passive memory. It sits in the **MAC clock domain** (the adapter
  drives it; the NIC reads it on `mac`; both are above the MAC-domain line in `BLOCK_DIAGRAM.md`).
- **The CDC/FIFO is NOT here.** Per `INGRESS_FLOW.md` §5 the clock-domain crossing (gray-code pointers
  + 2-FF sync) is **downstream**, between NIC(`mac`) and DOM(`internal`). The wire→NIC hop is
  same-domain. The wire is **not** a CDC crossing.

## How the passive bus is realized in this framework

- `wire.net.json` declares **only `bus_nodes`** (the eight lanes) + a `window_base`, and the kind
  `passive_bus`. There is **no `clock`, no `comb_nodes`, no `dff_nodes`, no `latch`** section.
- `validate.py` (the gate) enforces *passivity*: it **fails** if any clock/comb/dff/latch/buffer/
  writeout/display-ring key is present, and checks no-overlap + that every lane is addressed.
- `gennet.py` emits **only** the address map (`#define WIRE_<lane>`), the window base + lane count,
  and a `wire_init` that zeroes the memory (the power-off reset value). **No `_tick`, no `_run`, no
  cells, no clock loop** — there is nothing for the wire to compute.
- `wire.c` owns the single bus instance (`g_wire_bus[WIRE_REG_COUNT]`) and exposes `wire_bus()` (the
  addressed window the adapter deposits into and the NIC samples) + `wire_power_on()` (zero the bus).
- The end-to-end **adapter-drives-wire** demo lives in the **adapter** tree (the writer's home): the
  adapter deposits into the wire bus and its display shows the `WIRE_*` lane values the NIC would
  sample. The wire's own thin test just powers the passive bus on and displays it.

## Testbench ≠ device

The wire has no `replay`/`source-type`/`CSV`/`file` register and ingests no data file (it has no
buffer and no offline `prep`). The thin test powers the passive memory on and displays the bus — it
does not step, inject, clock, or read internals (there are none).

## Open decisions FLAGGED for the founder

1. **Window base placeholder.** `BLOCK_DIAGRAM.md` "Open / to confirm": window-base layout is set
   when the production backplane is generated. The wire uses `0x1800000` (the slot after the adapter's
   `0x1700000`) until the production backplane assigns it. Internal lane addresses are netlist-assigned
   and self-contained; only the window base is provisional.
2. **One wire per symbol/source.** `INGRESS_FLOW.md` "Multi-symbol": N parallel instances, one wire
   per symbol/source, all sharing the clock set. This build is ONE instance (the proven first ingress
   path); cloning is a wiring/placement step, no core change.
3. **ARCHITECTURE §4/§6 tension (resolved by the founder's barrier rule).** `hft_pipeline/
   ARCHITECTURE.md` §6 describes a PHY frame with qty+side and says "any module reading those
   addresses is wired to it." The founder's authoritative refinement (`feedback_hft_wire_and_barrier`,
   `INGRESS_FLOW.md` §1/§3): the wire is **price-only** and you read the **bus**, not the producer's
   private regs. This build follows price-only + the passive-bus barrier. Flagged, not silently chosen.
