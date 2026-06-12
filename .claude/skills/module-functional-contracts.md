---
name: Module Functional Contracts
description: Every module has a declared functional contract (role, clock domain, history, data direction) enforced at the gate
type: enforcement
source: Founder directive 2026-06-12; .hft_staging/SYSTEM_CONTRACT.md, module_contracts.yaml
---

# Module Functional Contracts

**Core Rule:** Every module's role, clock domain, data direction, and whether it
keeps history are **declared** in `.hft_staging/module_contracts.yaml` and the
module's **construction must match its contract**. This is enforced per module by
`checks/check_module_contract.py` (gate stage 2i). The system model persists in
the codebase — it does not rely on memory or re-explanation.

## The model (see SYSTEM_CONTRACT.md for the full narrative)

- **adapter** — data-in; OWN time pacer (self-advancing, SPEED-scaled, power-gated).
  Source timestamps only *gate* each record's release; they never *advance* it.
  Writes to the wire. (`self_paced`)
- **nic** — samples the wire at the MAC clock; stamps TAI's time on receipt;
  writes to the fifo. (`mac`)
- **tai** — real-world time, oscillated by taiosc; **does not drive or push data,
  it just exists** to be read/stamped. (`passive_time`, `data_push: false`)
- **mac / internal / taiosc** — oscillators (produce the MAC / internal / TAI clocks).
- **fifo_rx / tai_cdc** — MAC→internal crossings. **timeframe** — counts internal
  ticks, rolls BAR_SEQ. **pip_resolver** — publishes pip size, owns nothing.
- **dom** — samples fifo at the internal clock; live per-tick price-indexed book. (`internal`)
- **every other internal module** runs READ→COMPUTE→WRITE on the internal clock.
- **historical modules** (indicators) keep their OWN record store; others keep none.

## Enforced invariants (gate 2i)

- Module is declared in `module_contracts.yaml` (undeclared ⇒ fail).
- `has_history` ⇔ a record store (history_ring) is present.
- `clock_domain: mac|internal` ⇒ netlist clock names that domain; `self_paced` ⇒
  owns a clock generator; `internal_passive` ⇒ owns no clock (fabric-clocked).
- `role: passive_time` ⇒ keeps no history and pushes no data.

## When building a new module

Declare its contract in `module_contracts.yaml` first, then build to it. The gate
will reject any module whose construction contradicts its declared contract.
Relates to [[Build vs Assignment Separation]] and the Index Doctrine (Law #10).
