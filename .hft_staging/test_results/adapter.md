# Test Results — Adapter

- **Component:** `.hft_staging/adapter/` — the source. Converts records → price-only packets and, on its
  own real-world clock, **deposits them into the wire bus** (sole writer), paced by source timestamps.
- **Re-run:** 2026-06-07. Graduated to `.hft/adapter`.
- Results independently re-run via `.hft_staging/gate.sh`.

## Project gate — all stages PASS

| Stage | Result |
|---|---|
| 1 validate netlist | **PASS — 120 nodes** (single-writer / no-overlap / no-floating) |
| 2 build + thin test | **build+test OK** (`-Werror`) |
| 2b gate-level arithmetic | **OK** — no native `+`/`-`/`*` in `adapter_gen.h` / `wire_gen.h` ticks (uses `cell_addsub`) |
| 3 clean-room build (from committed HEAD) | **OK** |

## Behavior — synthetic, SPEED=1 (now == source timestamp)

```
adapter display-out  (price-only wire; 4 emitted packet(s); showing most-recent 4 of 4)
  slot  VALID         bid           ask     src_time   now@emit    seq
     0      1      47068000      47073000          0          0      0
     1      1      47067500      47072500         50         50      1
     2      1      47069000      47074000        153        153      2
     3      1      47068500      47073500        204        204      3
```

## Behavior — full live XAU file

```
adapter display-out  (price-only wire; 23390 emitted packet(s); showing most-recent 16 of 23390)
```
Total emitted = **23,390 = record count**; every record reached the wire; windowed display (most-recent
16); `now == src_time` per row. `SPEED` (clock-rate scale) verified at 1 / 1000 / 51 in prior runs.

## Invariants

- Price-only (bid/ask/time/symbol/pip/commission/seq/valid); no spread/qty/side.
- Real-world free-running clock from a power bit; write-out timestamp-paced (`DUE = RX_TS ≤ now`).
- **Gate-level arithmetic** (`cell_addsub` fa-carry-chain) — no native operators in the device tick.
- Deposits into the wire's window (the bus); does not keep a private output the NIC reaches into.

## Reproduce
```sh
.hft_staging/gate.sh .hft_staging/adapter
cd .hft_staging/adapter && make            # synthetic
make xau                                    # full live XAU
make probe && ./probe data_synth.bin 1 8    # per-tick waveform
```
