# Component Design & Build Guide (C-as-RTL)

How to take a module from the founder's blueprint → validated component → immutable vault, fast.
This is the repeatable method (proven on the adapter). Follow it; do not re-derive it each time.
The `netlist-builder` subagent automates steps 2–5.

> **Architecture is king, not results.** A passing binary with the wrong structure is a rejection.
> Build to the founder's docs; never invent vocabulary, directories, or abstractions absent from them.

## 0. The laws (non-negotiable)

- **Flip-flop level.** Every signal/flip-flop/gate is its own addressed register; operations are
  **branchless boolean functions between registers** (mask algebra, not `if`/`?:`/`switch`/`%`).
- **Device data path is branchless.** Conditionals live ONLY in: the buffer, the offline `prep`
  (CSV→binary, outside the system), and the external display/probe. Never in the generated device.
- **No floats, no malloc/calloc/realloc, no function pointers, no ghost values** (every operand is read
  from a register — no inferred `is_buy`/aggressor/mid-as-input).
- **Data law: price-only** at the wire (bid/ask/time/symbol/pip/commission/seq/valid). Downstream derives
  spread/qty/side. Bid and ask always explicit.
- **Single-writer.** A device writes only its own registers; consumers only read. Placement = wiring.
- **Clocks self-run from a power bit.** Nothing external advances a clock. Testbench ≠ device: no
  `replay`/`source-type`/`CSV`/`file` token in any device register or address map.
- **No `poc/` coupling, no invented `runtime/`/`framework`/shared tree.** poc was a throwaway proof.

## 1. Spec from the blueprint (extract, don't invent)

For the target module, read its sections and extract — into `<module>/<MODULE>.md` BEFORE any code:
- **Registers IN / OUT** — from `SPEC_REGISTERS.md` + the module's section in `hft_pipeline/ARCHITECTURE.md`,
  `INGRESS_FLOW.md`, `BLOCK_DIAGRAM.md`.
- **READ→COMPUTE→WRITE behavior** — what it computes each clock edge (as boolean/mask ops).
- **Clock domain + address window** (its own base; CDC/SLR seam if it crosses a domain).
- **Connections** — which lanes it reads, which it writes, who reads it.
Deliverable: `<MODULE>.md` = ASCII block diagram + register table + single-writer/reader contract +
clock/CDC boundary + open decisions flagged for the founder (flag tensions, don't silently choose).

## 2. Scaffold staging (`.hft_staging/<module>/`)

Mirror the adapter's structure:
```
<MODULE>.md            design doc (step 1)
gen_<module>_net.py    emitter: writes <module>.net.json
<module>.net.json      generated netlist (do not hand-edit logic)
cells.h                branchless primitives (buf/not/and/or/xor/mux/eqmask/dff[/fa/gate])
gennet.py              netlist -> device C generator
validate.py            gate: single-writer / no-overlap / no-floating
<module>.c/.h          host glue / starter (power on, step away — no main() the modules slave to)
buffer.c/.h            ONLY if the module ingests external data (the blessed conditional/IO home)
display.c/.h           external display (reads lanes raw; no compute)
test_<module>.c        thin test: power-on + display only (<=45 lines; no clock/step/inject/wire-read)
Makefile               targets: validate, gen, build/test, probe; references THIS tree ONLY
.gitignore             ignore SIBLING *_gen.h (other devices) + compiled + *.bin; own <mod>_gen.h is COMMITTED
```

## 3. Netlist + emitter (the python file)

- `gen_<module>_net.py` emits `<module>.net.json`: nodes (config, inputs, dffs, comb wires, outputs) in
  the module's address window, wired as cells — branchless. Selection via `cell_mux`/`cell_gate`/
  `cell_dff`/`cell_eqmask`; comparators as gate netlists; ring/index via mask (`& (depth-1)`, depth a
  power of two with a generate-time assertion).
- `gennet.py` generates the device C with explicit READ→COMPUTE→WRITE phases from the netlist.
- A self-running `<module>_run` loop: `while (power & in_range/condition) <module>_tick(r);`

> **BUILD-SEQUENCE LAW (enforced — `.githooks/check_generated.sh` + gate stage 2c):**
> **Your deliverable is the netlist + the `gennet` GENERATOR — running `gennet` SPAWNS the device code.**
> You do **NOT** hand-code device / flip-flop files. The device tick (`*_tick`, `cell_*()` composition)
> is **GENERATED** into `<module>_gen.h` by `gennet`. If you catch yourself typing flip-flop logic,
> `cell_*()` calls, or a `*_tick` body by hand — **STOP; write the generator instead.** The only files
> you hand-write are the non-device glue (starter, buffer, display, thin test); they may *call* generated
> entry points but contain **no `cell_*()` and no `*_tick` definition**. Sequence: `.net.json` →
> `gennet.py` → `*_gen.h`. The device's OWN `<module>_gen.h` **IS committed + graduated** — the netlist
> is its **validation spec** (`check_generated.sh` byte-matches the committed circuit against
> `gennet.py <module>.net.json`, proving it was generated, not hand-edited). Only **SIBLING** `*_gen.h`
> (regenerated copies of other devices) are gitignored. The guard blocks any hand-written flip-flop logic
> and any committed gen header that fails the byte-match.

## 4. Fill the rest (template from the adapter)

Reuse the proven adapter files as templates, changing only the netlist + behavior: `cells.h` (copy the
proven set), host starter, thin test (power-on + display), external display, Makefile, `validate.py`.
Offline `prep` only if the module ingests data. Name constants (`#define`), no magic numbers.

## 5. Gate + iterate

```sh
.hft_staging/gate.sh .hft_staging/<module>     # validate + build(-Werror) + clean-room build
```
Fix until PASS. The `drift-guard` pre-commit hook + skill enforce no floats/heap/poc/runtime and
catch invented vocabulary. Re-run the gate yourself — never trust an unverified "done".

## 6. Commit + graduate

```sh
git add <explicit paths>            # never git add -A; user name only, no AI attribution
git commit -m "<stage>: <type>: <lowercase desc>"
.hft_staging/graduate.sh <module>   # gated promotion -> immutable .hft vault
```

## Speed notes

- **Template from the adapter** — copy structure, change the netlist + behavior. Most files are nearly
  identical between components.
- **Use the `netlist-builder` subagent** for steps 2–5: give it the module name; it extracts the spec,
  scaffolds, writes + runs the emitter, fills the rest, and runs the gate. You ground (point it at the
  module + flag any open decisions) and verify the gate output.
