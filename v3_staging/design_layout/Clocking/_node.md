---
name: Clocking
subsystem: Clocking
doc: ug572-ultrascale-clocking
groups:
  - buffers
  - sources
modules: 12
folders: 0
cells: 12
---

# Clocking subsystem — the file tree IS the circuit

Folders branch where the cache documents internal structure; `.cell` files are leaves. Walk to trace the circuit. All facts cite the cache.

| module | shape | count | internals | ports | attrs | source |
| --- | --- | --- | --- | --- | --- | --- |
| BUFGCE | cell | 24 | 0 | 0 | 0 | `ug572-ultrascale-clocking p16` |
| BUFGCTRL | cell | 8 | 0 | 0 | 0 | `ug572-ultrascale-clocking p16` |
| BUFGCE_DIV | cell | 4 | 0 | 0 | 0 | `ug572-ultrascale-clocking p16` |
| BUFG | cell | 1516 | 0 | 8 | 0 | `ug572-ultrascale-clocking p30` |
| BUFGCE_1 | cell | 1 | 0 | 0 | 0 | `ug572-ultrascale-clocking p17` |
| BUFGMUX | cell | 1 | 0 | 0 | 0 | `ug572-ultrascale-clocking p21` |
| BUFG_GT | cell | 24 | 0 | 0 | 0 | `ug572-ultrascale-clocking p33` |
| BUFG_GT_SYNC | cell | 10 | 0 | 0 | 0 | `ug572-ultrascale-clocking p33` |
| MMCM | cell | 35 | 0 | 25 | 2 | `ug572-ultrascale-clocking p4` |
| PLL | cell | 35 | 0 | 16 | 2 | `ug572-ultrascale-clocking p4` |
| MMCME4_BASE | cell | — | 0 | 0 | 0 | `—` |
| PLLE4_BASE | cell | — | 0 | 4 | 0 | `—` |
