# CELLS — Canonical Branchless Cell Primitive Library

**Canonical source:** `.hft_staging/cells/cells.h`

This is the single authoritative copy of the cell primitive library. Every
component's `cells.h` must byte-match the canon **modulo the header-guard
token** (a component may use e.g. `ADAPTER_CELLS_H` instead of `HFT_CELLS_H`;
nothing else may differ). Conformance is enforced by
`.hft_staging/checks/check_cells_canon.sh <component_dir>`, run by `gate.sh`.

## Model

- A wire/register is one 64-bit word (`word_t`). Device state is a flat array
  of these, indexed by node address from the netlist's address map.
- Every cell is a pure word function: no floats, no heap, no function
  pointers, no `if`/`switch`/`?:`. Selection is **mask algebra**; equality is
  **zero-reduction**.
- The core mask trick: `m = -(bit & 1)` broadcasts a 1-bit control to an
  all-ones (`bit=1`) or all-zeros (`bit=0`) 64-bit mask, branchlessly. Then
  `a ^ ((a ^ b) & m)` selects `b` when `m` is all-ones and `a` when zero.

## Primitives

### cell_buf(a)
RTL: a buffer/wire. `out <- a`. Pure pass-through; exists so every netlist hop
is an explicit addressed cell (a lane tap IS a buf node).

### cell_not(a)
RTL: inverter. `out <- ~a`, bitwise over the whole word (64 parallel NOT gates).

### cell_and(a, b) / cell_or(a, b) / cell_xor(a, b)
RTL: 2-input AND/OR/XOR gate arrays, 64 lanes wide. All boolean logic in the
device is composed from these plus NOT.

### cell_mux(a, b, sel)
RTL: 2:1 multiplexer, sel in bit0. `out = sel ? b : a` — but expressed as mask
algebra: `m = -(sel & 1)`, `out = a ^ ((a ^ b) & m)`. No branch, no
conditional move semantics in the source. This is THE replacement for `if` in
the device datapath: a "conditional write" is a mux of (old value, new value)
feeding a dff.

### cell_eqmask(a, b)
RTL: 64-bit equality comparator. Returns 1 in bit0 iff `a == b`, else 0.
Reasoning: `d = a ^ b` is zero iff equal; `(d | -d)` has its top bit set for
any nonzero `d` (either `d` or its two's complement negation is "negative");
so `(~(d | -d)) >> 63` is 1 exactly when `d == 0`. Zero-reduction equality —
no comparison operator in the datapath.

### cell_fa(a, b, cin)
RTL: single-bit full adder. Inputs in bit0; returns sum in bit0, carry-out in
bit1 (`s = a^b^cin`, `co = (a&b) | (cin & (a^b))`). The atomic arithmetic
gate: comparators, counters, and adders are netlists of these, expanded
bit-serially by the generator.

### cell_gate(val, en)
RTL: pass-or-zero (power gate / tri-state-to-zero). `out = en ? val : 0` via
`val & -(en & 1)`. Uses: power-gating a multi-bit register value (e.g. clock
step = SPEED while powered, 0 while off) without an `if` or a literal in the
path; and as the building block of **table select** — gate exactly one slot
through (one-hot enable) and OR-reduce the rest as 0, giving a branchless
N-way lookup.

### cell_addsub(a, b, sub)
RTL: 64-bit ripple-carry adder/subtractor — the STRUCTURAL arithmetic
primitive (the only legal way to add/subtract in a device tick; native
`+`/`-`/`*` are banned by the gate-level-arithmetic law). `sub=0 → a+b`;
`sub=1 → a-b` by two's complement (`a + ~b + 1`: b is XOR-inverted by the sub
mask and the initial carry is `sub`). The internal 64-iteration loop is the
generator-level unrolling of 64 `cell_fa` cells — a gate expansion, not a
data-path branch (no conditional selects the result; the carry chain does).
The loop index is the only native arithmetic, and it is address/index math,
not data. Returns the sum word (the related `cmp_le`/`cmp_lt` carry chain
returns the final carry-out instead).

### cell_sar(a, n)
RTL: arithmetic shift right by a compile-time constant `n` (0 < n < 64) with
sign replication. At gate level a fixed shift is pure rewiring (each output
bit is a wired select of input bit `i+n`); the vacated high bits are filled by
the two's-complement broadcast of bit 63 (`-(a>>63 & 1)`), so negative values
floor correctly. No adder, no branch; shifts are sanctioned in the tick body
(the arithmetic gate strips `>>`/`<<` before scanning). Canonical use:
mid-price `cell_sar(bid + ask, 1)`-style halving where the sum comes from
`cell_addsub`, and power-of-two scaling per the gate-level-arithmetic law
("Shifts → cell_sar", CLAUDE.md Law #2).

### cell_dff(q, d, en)
RTL: D flip-flop with clock-enable — the ONE stateful cell.
`q_next = en ? d : q`, as mask algebra (`q ^ ((q ^ d) & m)`). The device's
clock edge applies this to every dff node each tick; the value latched is the
value present at the input on the edge (registered hop). A register IS a dff.

## Planned: full digital-circuit-builder catalog (future phase)

Founder direction: this library will grow into a complete digital-circuit
builder catalog. The following primitives are **planned, not yet implemented**.
All are composable from the existing D-FF + gates (no new stateful primitive
is required — they will be provided as standard compositions / netlist macros):

- **SR flip-flop / SR latch** — set/reset state; `d = (q | s) & ~r` into a dff
  (plus the level-sensitive latch variant).
- **JK flip-flop** — `d = (j & ~q) | (~k & q)`; toggles on j=k=1.
- **T flip-flop** — `d = q ^ t`; the divide-by-two / toggle cell.
- **D latch (level-sensitive)** — transparent while enable is high.
- **Counters** — ripple and synchronous up/down counters: T-FF chains or
  dff + cell_addsub increment netlists.
- **Shift registers** — dff chains (SIPO/PISO), the basis for serializers.

When implemented, they land in this canonical file first and propagate to
components via the byte-match rule; emitters/gennet may then reference them as
netlist node types.
