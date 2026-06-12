# SYSTEM CONTRACT — module roles, clocks, and data flow

The authoritative narrative of what each module **is** and **does**. The
machine-readable form is `module_contracts.yaml`; conformance is enforced per
module by `checks/check_module_contract.py` (gate stage 2i). This exists so the
system model **persists in the codebase** — it does not depend on memory or
founder re-explanation.

> Scope: this describes *construction and behaviour* (the build phase). It does
> **not** assign addresses or wire modules together — that is the later
> assignment phase (build-vs-assignment separation).

## The chain

```
   (external feed)
        │
   ┌────▼────┐  OWN time pacer (self-advancing, SPEED-scaled, power-gated).
   │ adapter │  Source timestamps only GATE each record's release (DUE =
   └────┬────┘  RX_TS ≤ ADP_CLK); they never advance it. Writes to the wire.
        │ wire (passive bus/seam)
   ┌────▼────┐  Samples the wire at the MAC clock. Stamps TAI's time onto the
   │   nic   │  data on receipt. Writes to the fifo.            [clock: mac]
   └────┬────┘
        │ fifo_rx (MAC → internal crossing buffer)
   ┌────▼────┐  Samples fifo data at the INTERNAL clock. The live, per-tick,
   │   dom   │  price-indexed order book.                  [clock: internal]
   └────┬────┘
        │  (every internal module runs READ→COMPUTE→WRITE on the internal clock)
   ┌────▼─────────────────┐
   │ candle / footprint / │  Passive consumers (fabric-clocked). Each keeps its
   │ tpo  (+ analytics)   │  OWN record store of history.   [internal_passive]
   └──────────────────────┘
```

## Clocks & time

- **mac** — produces the MAC clock. **internal** — produces the internal clock
  that drives the fabric. **taiosc** — produces TAI's oscillation.
- **tai** — real-world time, accumulated from taiosc. It **does not drive or push
  data — it just exists** to be read and stamped (`role: passive_time`,
  `data_push: false`). Time is a reference, never a controller.
- **timeframe** — counts internal ticks and rolls `BAR_SEQ` at the period (a
  guide, not a master). **pip_resolver** — per-symbol lookup that publishes the
  pip size; owns nothing.

## Memory

- Only **historical** modules (the indicators) keep a record store, and it is a
  **record store, not an index construct** (Law #10): records carry their own
  time + price; no write-pointer, no decoder. All other modules keep no history.

## Enforced invariants (gate 2i, from `module_contracts.yaml`)

- Every module is declared with a contract; an undeclared module fails the gate.
- `has_history` ⇔ a record store is present.
- `clock_domain: mac|internal` ⇒ the netlist names that clock; `self_paced` ⇒ it
  owns a clock generator; `internal_passive` ⇒ it owns no clock (fabric-clocked).
- `role: passive_time` ⇒ keeps no history and pushes no data.
- (Power + start/stop on every clock is enforced separately by check_clock_rule.)
