# The Component Library — model & structure

The audited vocabulary every design composes. It is **multi-rooted**, with **three
distinct primitive classes** (founder law `library-model-primitives-vs-addressable`).
Two axes are kept strictly separate and must never be conflated:

- **Built from core primitives** — what a part is *made of*.
- **Addressable** — a *separate* universal requirement (every part is reachable in
  the system, or it lives only in code/AI memory). **Addressable ≠ flip-flopped.**

## The three primitive classes

1. **Gate / boolean constructs** (`atoms.yaml`, section `gates`) — the combinational
   cells: `buf not and or xor mux eqmask fa gate addsub sar shl`. Each is an
   irreducible C function in `cells/cells.h`. Stateless.

2. **Flip-flops** — stateful storage. The **D flip-flop** (`dff`) is the irreducible
   state atom (`atoms.yaml`, section `flip_flops`); its only definition is `cell_dff`.
   The **other flip-flop TYPES are composites** built from `dff` + gates and live in
   `components/`: `t_ff`, `sr_ff`, `jk_ff`, `d_latch`. (A flip-flop is not one thing —
   there are types; they are part of the library.)

3. **Conductors** (`conductors.yaml`) — wire / bus / lane: **real copper carrying a
   signal.** A conductor **holds no state and is NOT built from flip-flops** — it is
   its own first-class primitive class. In the C-as-RTL model a conductor lane is a
   passive addressed slot: deposited into by its single driver, sampled by readers,
   no logic, no tick. (This is what `wire`/`dom_bus` are.) Conductors are carried
   THROUGH elaboration as conductors — never reduced to flip-flops.

## Composites

A composite (`components/*.comp.yaml`) is defined PURELY as a composition of lower
library components (any of the three classes). Composition only — no field for raw
logic or invented values. New components are added to the library deliberately
(reviewed materializations), never improvised inside a design.

## Manifests

- `atoms.yaml`      — gate constructs + the D flip-flop atom (C-lowered, `cells.h`).
- `conductors.yaml` — the conductor primitive class (passive addressed carriers).
- `components/`     — composites (flip-flop types t_ff/sr_ff/jk_ff/d_latch; higher
  composites as added).

All composite flip-flop-type bodies here are transcribed verbatim from the audited
`circuitlib` lowerings — nothing invented.
