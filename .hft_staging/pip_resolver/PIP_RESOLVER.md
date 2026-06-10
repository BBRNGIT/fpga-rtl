# PIP_RESOLVER — the per-symbol pip-resolution lookup device

Grounded in: `SPEC_REGISTERS.md` §3 (Spatial Grid — `PRICE_IDX_RESOLUTION_REG` is the unified Y-axis
resolution authority) and §4 (PIP Resolver — "a standalone configuration module that defines the
Y-axis (price) grid resolution … decoupled from time and from live price tracking — pure static scale
reference"; "the **absolute authority** for Y-axis resolution across all tools"). Build brief: read
`SEAM_SYMBOL` from the NIC seam output, index a static pip-config table by `symbol * 8`, publish
`PIP_RESOLUTION_REG`. Template: `.hft_staging/nic/` (clocked sibling-window consumer + self-run loop)
and `.hft_staging/adapter/` (structure). Module-barrier + single-writer from `AGENTS.md`/CLAUDE.md.

## What the PIP_RESOLVER IS

A **clocked lookup device** in its **own window (0x2000000)**, running on the **`mac`** cadence (same
domain as the NIC seam it samples — no CDC). Each mac edge it samples the NIC seam's `SEAM_SYMBOL` lane
(gated by `SEAM_VALID`), uses the symbol as a **static-table address** (`addr = symbol * 8` bytes = the
`symbol`-th 64-bit slot), reads the resolved pip value out of a **static, init-only pip-config table**,
and publishes it on its own `PIP_RESOLUTION_REG` output lane.

It is **pure address arithmetic + a branchless table select** — no per-tick accumulation, no ring, no
dedup, no CDC. The table is **config only** (written once by the starter, per §4 "Writes nothing during
operation (config only)"). The device's data path writes only `PIP_RESOLUTION_REG`, `PIP_SYMBOL` (the
symbol it resolved, latched for display/trace), and `PIP_VALID`.

The "× 8" in the brief is the **byte address** of the symbol's slot (`8` bytes per 64-bit register). In
the flat word-array register model the slot index is `symbol` itself; the netlist asserts the table is a
power-of-two depth so the index is a **branchless mask** (`symbol & (depth-1)`) — no `%`, no bounds `if`.

## Block diagram

```
══ MAC clock domain ════════════════════════════════════════════════════════════
  NIC SEAM (0x1A00000, the NIC's own output window — passive to this consumer)
    SEAM_SYMBOL   SEAM_VALID
        │  (PIP_RESOLVER SAMPLES the NIC seam on mac; barrier — never the NIC's
        │   internal ring/state; only the published SEAM_* lanes.)
        ▼
  ┌─ PIP_RESOLVER DEVICE (0x2000000, clock = mac) ──────────────────────────────┐
  │ CONFIG  : PIP_CFG_TABLE(0..DEPTH-1)  — static per-symbol pip resolution,      │
  │            written once by the starter (init-only; never per-tick).           │
  │ READ    : SEAM_SYMBOL, SEAM_VALID ; the table slot at idx = symbol & MASK.     │
  │ COMPUTE : idx  = cell_and(symbol, MASK)            (symbol*8 byte addr = slot)  │
  │           res  = OR-reduce( eqmask(idx,i) ? table[i] : 0 )   (branchless sel)   │
  │           en   = SEAM_VALID                                                     │
  │ WRITE    : PIP_RESOLUTION_REG <= res (en) ; PIP_SYMBOL <= symbol (en) ;         │
  │            PIP_VALID <= SEAM_VALID                                              │
  └───────────────┬──────────────────────────────────────────────────────────────┘
        OUT ▼  PIP_RESOLUTION_REG (the unified Y-axis resolution authority; read by the
               spatial grid / DOM / footprint / tpo when they snap a price to a Price_Idx)
```

## Register table — window 0x2000000 (netlist-assigned offsets, all named)

### config / input (set once by the starter — module-barrier: PIP_RESOLVER's own input lanes)
| lane | type | meaning |
|---|---|---|
| `PIP_POWER`     | bit | power/enable: the device self-runs on the mac edge while bit0 = 1 |
| `PIP_RUN_UNTIL` | u64 | configured self-run tick budget (set once by starter) |

### static pip-config table (config dffs — init-only; NEVER written in the tick)
| lane | type | meaning |
|---|---|---|
| `PIP_CFG_TABLE_<i>` (i = 0 .. DEPTH-1) | u64 | per-symbol pip resolution (effective pip step). The symbol id indexes this table (`addr = symbol * 8` bytes = slot i). Written once by the starter; the device only READS it. |

### state (dff)
| lane | type | meaning |
|---|---|---|
| `PIP_TICKS` | u64 | self-run tick counter (bounds the self-run) |

### output lanes (dff — the device's OWN window; sole writer)
| lane | type | meaning |
|---|---|---|
| `PIP_RESOLUTION_REG` | u64 | resolved pip resolution for the sampled symbol (the §4 `REG_PIP_RESOLUTION` / realized `PRICE_IDX_RESOLUTION_REG` — the unified Y-axis authority) |
| `PIP_SYMBOL`         | u64 | the symbol id that was resolved (latched for display/trace) |
| `PIP_VALID`          | bit | 1 iff a symbol was sampled (= SEAM_VALID) this cycle |

The sampled `SEAM_SYMBOL` / `SEAM_VALID` are read **directly from the NIC window** (`nic_gen.h`) — the
NIC's own published output lanes, the legitimate cross-module surface. The PIP_RESOLVER keeps **no
private copy** of the NIC map; the Makefile regenerates `nic_gen.h` from the NIC's single source.

## Behavior — one MAC clock edge (READ → COMPUTE → WRITE, branchless, gate-level arithmetic)

1. **READ:** `PIP_POWER`, the NIC seam (`SEAM_SYMBOL`, `SEAM_VALID`), and the static table slot at
   `idx = SEAM_SYMBOL & PIP_TABLE_MASK` (`PIP_CFG_TABLE_<idx>`).
2. **COMPUTE (branchless cells — NO native +/-/*):**
   - `idx = cell_and(symbol, PIP_TABLE_MASK)` — the symbol address (`symbol*8` byte address = slot idx)
     reduced to the table range by a power-of-two mask (no `%`, no bounds `if`).
   - `res = OR-reduce over i: cell_gate(PIP_CFG_TABLE_i, cell_eqmask(idx, i))` — exactly one slot is
     gated through; the rest contribute 0. This is the NIC ring-slot select pattern, read-only.
   - `en = SEAM_VALID` — only a valid sampled symbol latches a new resolution.
3. **WRITE:** `PIP_RESOLUTION_REG <= res (en)`, `PIP_SYMBOL <= symbol (en)`, `PIP_VALID <= SEAM_VALID`
   (latched while powered). Write-only WRITE phase (no read-after-write). The config table is never
   written in the tick (init-only).

### Self-running (canonical clock primitive)

`while ((PIP_POWER & 1) && cmp_lt(PIP_TICKS, PIP_RUN_UNTIL)) { pip_resolver_tick(r, nic); PIP_TICKS += 1; }`
— runs on the mac edge while powered, bounded by a configured tick budget (config, not external
stepping). Nothing external advances it.

## Single-writer / reader contract

- **Writer of all `PIP_*` = `pip_resolver_tick()` (generated)** — sole writer of its own window. The run
  loop owns `PIP_TICKS`. The starter writes the `PIP_CFG_TABLE_*` config slots ONCE before power-on
  (init-only config, not a data-path writer).
- **Reader of `PIP_RESOLUTION_REG` = the spatial grid / DOM / footprint / tpo** (downstream, §3/§4) — the
  unified Y-axis resolution authority. Nothing reads it yet (built standalone, the proven order).
- **The PIP_RESOLVER reads, never writes:** `SEAM_SYMBOL` / `SEAM_VALID` (the NIC's published output
  window). It never writes a sibling's register; it never reaches into the NIC's internal ring/state — it
  samples the published seam lanes.

## Clock domain / CDC boundary

- **PIP_RESOLVER clock = `mac`** (same domain as the NIC seam). The seam→pip_resolver hop is
  same-domain; **no CDC** inside the device. (Downstream consumers in the pipeline/internal domain would
  cross via the existing CDC seams; that is not this component's concern.)

## Why the table is collision-free / correct

Table depth `DEPTH` = `PIP_TABLE_DEPTH`, a **power of two** (generate-time assert); index =
`SEAM_SYMBOL & (DEPTH-1)`. The symbol id is the table address (the brief's `symbol * 8` byte address =
the `symbol`-th 64-bit slot). The branchless select gates exactly one slot via `cell_eqmask(idx, i)` and
OR-reduces; for a symbol in range this returns its configured pip value; an out-of-range symbol wraps to
its low bits (a deliberate, bounded mask — same discipline as the NIC ring index). The table is
**static**: written once at init, never mutated, so the lookup is a pure function of the symbol.

## Testbench ≠ device

No `replay`/`source-type`/`CSV`/`file` register; no buffer, no offline prep (the device ingests no data
file — it samples the NIC seam and reads a static config table). The thin test powers the device on
(presenting a NIC-seam symbol + a configured table via the starter) and displays the output lanes; it
does not step, inject into the data path, clock, or read device internals beyond the display lanes.

## Open decisions FLAGGED for the founder

1. **`symbol * 8` = byte address of the slot.** The brief says "address arithmetic (symbol * 8) to index
   a static pip-config table." In the flat 64-bit word-array register model each slot is 8 bytes, so the
   `symbol`-th slot is at byte offset `symbol * 8` and at **word index `symbol`**. The netlist therefore
   indexes by `symbol` (masked to the power-of-two table depth). If the founder intends a different slot
   stride (e.g. multi-word records per symbol), the stride is a netlist constant bump — flag, not a
   silent choice.
2. **Output register name.** The brief names the output `PIP_RESOLUTION_REG`. `SPEC_REGISTERS.md` §4 lists
   `REG_PIP_RESOLUTION` (per-symbol raw pip scale) and the realized `PRICE_IDX_RESOLUTION_REG` (effective
   step used by DOM/footprint/tpo) as the same Y-axis authority. This build publishes `PIP_RESOLUTION_REG`
   per the brief; whether the downstream grid reads it as `PRICE_IDX_RESOLUTION_REG` (a rename at the
   consumer) is the integration wiring decision. Flagged.
3. **`REG_PIP_CONFIG` (operator grid interval) folded into the table.** §4 resolve logic is
   `effective_step = REG_PIP_RESOLUTION × REG_PIP_CONFIG`. The brief asks for a single static per-symbol
   table → published resolution (the lookup IS the resolution). The optional `× REG_PIP_CONFIG` grid
   multiplier (1 pip vs N pips) is **not** in this lookup; if the operator N-pip interval is wanted, it
   is a second config register multiplied in (a `cell_*` multiply cell) — surfaced for a human decision,
   not silently added.
4. **Table depth.** Set to a power of two (`PIP_TABLE_DEPTH`); sized for the symbol-id space in flight.
   The default (16) is the proven small power-of-two; production depth is a config bump, no core change.
