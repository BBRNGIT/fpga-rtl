---
name: buffers
role: global clock distribution
subsystem: Clocking
source: ug572 p16 (Clock Buffers)
topology: BUFGCTRL multiplexers cascade to adjacent buffers, forming a ring of eight BUFGMUXes (ug572 p16, Fig 2-4)
---

# Clocking / buffers

global clock distribution. Source `ug572 p16 (Clock Buffers)`.

## Modules

- `BUFGCE` (cell) — count 24, 0p, 0 attrs
- `BUFGCTRL` (cell) — count 8, 0p, 0 attrs
- `BUFGCE_DIV` (cell) — count 4, 0p, 0 attrs
- `BUFG` (cell) — count 1516, 8p, 0 attrs
- `BUFGCE_1` (cell) — count 1, 0p, 0 attrs
- `BUFGMUX` (cell) — count 1, 0p, 0 attrs
- `BUFG_GT` (cell) — count 24, 0p, 0 attrs
- `BUFG_GT_SYNC` (cell) — count 10, 0p, 0 attrs
