# Test Results — Wire

- **Component:** `.hft_staging/wire/` — the **passive addressed-memory bus** between adapter and NIC.
  No clock, no compute, no cells. The adapter deposits (sole writer); the NIC samples. The barrier that
  lets two modules meet without reading each other's registers.
- **Re-run:** 2026-06-07. Graduated to `.hft/wire`.

## Project gate — all stages PASS

| Stage | Result |
|---|---|
| 1 validate netlist | **PASS — 8 bus lanes**, passive / no-overlap / addressed (no clock/compute/latch; sole writer = adapter) |
| 2 build + thin test | **build+test OK** (`-Werror`) |
| 2b gate-level arithmetic | **OK** — no native `+`/`-`/`*` (it has no tick logic at all) |
| 3 clean-room build (from committed HEAD) | **OK** |

## Behavior — standalone thin test (quiescent bus)

```
wire bus  (passive addressed-memory boundary; price-only; 1-deep — the current packet the NIC samples)
  VALID         bid           ask     src_time    symbol      pip   commission    seq
      0             0             0          0         0        0           0      0
```
Standalone the bus reads zero (nothing has deposited). When driven by the adapter it holds the latest
price-only packet 1-deep (see [adapter.md](adapter.md) / [nic.md](nic.md) end-to-end).

## Invariants

- Passive: no clock, no compute, no cells — pure addressed storage (the generated header is the address
  map + a zero-init only).
- 1-deep, non-blocking medium of transfer; latest packet, overwritten freely.
- Single writer = adapter; reader = NIC. Lane map (`wire_gen.h`) is the single source consumed by both
  the adapter (deposit) and the NIC (sample) — regenerated, never hand-copied.

## Reproduce
```sh
.hft_staging/gate.sh .hft_staging/wire
```
