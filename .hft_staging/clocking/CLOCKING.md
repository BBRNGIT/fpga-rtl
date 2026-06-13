# Clock management — native clocks, built from primitives by the existing meta-tool

The blank had no clock generators. These are the VU9P clock resources (DS923: 30 CMTs =
30 MMCM + 60 PLL; UG572: per clock region 24 BUFGCE + 8 BUFGCTRL + 4 BUFGCE_DIV), built
from primitives via gen_module_net.py + gennet.py — no new tool.

- **mmcm** (MMCME4) — Mixed-Mode Clock Manager: 7 derived clock outputs from one reference.
  Each output = the reference divided by a bitstream-set DIV (a phase counter that wraps;
  the wrap pulse is the divided clock edge). PROVEN: ref/2 -> 6 edges, ref/3 -> 4 edges over
  12 reference ticks. This is how mac(125MHz)/internal(250MHz) are produced from a reference.
- **pll** (PLLE4) — same divider-bank model, 4 outputs.
- **bufgce** — global clock buffer + enable (gate the clock onto the global net).
- **bufgctrl** — global clock mux (select between two clocks).

A CMT = 1 mmcm + 2 pll (composition). Next: array 30 CMTs + the clock buffers + the
interconnect into the full VU9P container blank (authentic counts), alongside CLB/BRAM/GTY.
