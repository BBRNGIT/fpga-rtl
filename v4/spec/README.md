# The spec — YOUR build contract (not the reference docs)

This is the spec that drives development. The Xilinx datasheets (in `cache.db`) are
the **reference**; this is **our** contract built from them. We copy the chip-design
workflow: build a closed **cell library** once, then everything is **composition**.

## The model (founder-decided, locked)
- **Unit = the cell** (Boolean gate / flip-flop / analog boundary). The atom.
- **Composition:** cell -> primitive -> module -> device. Bottom-up.
- **DONE = a module: fully C, fully wired, fully working.**

## The four files
- `cells.yaml` — LAYER 0. The closed cell library: digital cells from first-principles
  Boolean logic (universal), analog cells as behavioral boundaries (db-cited). Nothing
  in the device may use a cell outside this file.
- `composition.yaml` — LAYERS 1-3. How cells compose into primitives, modules, device.
  Ports and decompositions are POPULATED FROM THE DB (cited); undocumented decompositions
  are `PENDING` (open items), never guessed.
- `done.yaml` — the testable pass condition per layer + the always-on invariants.
- `test.py` — the EXTERNAL checker. Reads any build output and passes ONLY if it
  conforms to the three files above. This is the gate: an agent's job is to make the
  test pass, not to interpret the spec.

## How the db serves the spec
The db is the fact-source. The spec's CONTENT (a primitive's ports, a module's
primitives, the analog cells) is QUERIED from the db and cited — never invented.
First-principles Boolean cells need no source (they're the bedrock of digital logic).
Where the db can't answer (an undocumented decomposition), the spec says `PENDING` —
surfacing the gap to the founder instead of letting an agent fabricate.

## Why this ends the drift
There is nothing left to interpret. Cells are universal or db-cited. Composition is
db-populated or explicitly PENDING. Done is a test, not an opinion. A new agent does
not "understand the vision" — it makes `test.py` pass. Non-conforming output fails,
automatically, with no judgment.

## Workflow (the manufacturing line)
1. `cells.yaml` is the library (done).
2. `composition.yaml` is populated from the db (primitives' ports + decompositions, cited).
3. Build each module in C by composing its primitives from cells.
4. `test.py` gates every layer: cell -> primitive -> module -> device.
5. A module is DONE when it's fully C, wired, working — and the test says so.
