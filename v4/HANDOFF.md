# HANDOFF — read this first, before anything else in v4

You are the next AI dev on this project. The human (TeamBB) has burned many sessions
on AI that drifted — paraphrasing the manufacturer's files, inventing structure,
decomposing things too early, and asking endless questions instead of doing the
work. **This document is the alignment we finally reached. Follow it exactly. Do not
re-derive it, do not "improve" it, do not ask the human to re-explain it.**

If any older doc disagrees with this one, THIS WINS. In particular,
`REPLICA_CONTRACT.md` describes an earlier (verb/NAND-decomposition) approach that we
**abandoned for the current phase** — see "What changed" below.

---

## 1. What we are actually doing RIGHT NOW (the whole task, plainly)

The end goal (far off) is the Xilinx **XCZU19EG** FPGA as a working soft device in C.
**We are NOT building that yet.** We have not started "creating" anything.

We are in **two concurrent phases:**

**Phase 1A (nearly done): Transcription**
> Copy the UNISIM Verilog cell library into accurate, compilable C parts list. One `.c` per `.v`.
> `GND.c` is the approved reference — the proof-of-concept transcription, exactly as written.
> Remaining: ~248 cells, transcribed in the same form, growing `verilog.h` as needed.

**Phase 1B (starting now): C Architecture Specification Language**
> C IS our hardware specification language. The UNISIM `.v` files describe the *structure* of
> physical hardware (ports, signals, connections, behavior). Our C parts list, using `verilog.h`
> macros, must *faithfully describe that architecture* in a form that is:
> - **Compilable** — syntax is valid C
> - **Unambiguous** — each construct has ONE clear meaning (§3)
> - **Enforceable** — tools validate that the C describes what it claims (§6–§8)
>
> The C IS NOT A SIMULATION. It does not execute. It DESCRIBES. We describe using constructs
> (`always`, `assign`, `wire`, `initial`, `@(posedge)`, `[hi:lo]`) whose *architectural meaning*
> is formally defined. When someone reads the C, they understand the hardware without ambiguity.

---

## 2. C Architecture Specification Language (what each construct MEANS)

When you write C code in a parts-list entry, you are using architectural language. Each
construct has a formal, unambiguous meaning tied to real hardware structure. **There is
no "doing your own thing" — every line must mean what it says.**

### Constructs and their architectural meanings:

| Construct | Verilog | C Form | Architectural Meaning |
|-----------|---------|--------|----------------------|
| **4-state net** | `wire x;` | `wire x;` ⇒ `net_t x;` | A signal that can hold 0, 1, X (unknown), or Z (high-impedance). Maps to a structural node. |
| **Vector/bus** | `wire [7:0] X;` | `wire_bits(X, 7, 0);` ⇒ `net_t X[8]` | 8 structurally connected nets, indexed 7..0. Bits are the identity, not size. |
| **Bit/part select** | `assign Y = X[3];` | `assign Y = X[3];` | Y is connected to bit 3 of X. Structural fanout. |
| **Range select** | `assign Y = X[3:0];` | `range_assign(Y, X, 3, 0);` | Y's bits are connected to bits 3,2,1,0 of X. **Notation must be defined — `:` is not valid C.** |
| **Continuous assign** | `assign Y = expr;` | `assign Y = expr;` | Y is permanently driven by expr. The expr describes a combinational function of the inputs. |
| **Synchronous storage** | `always @(posedge clk) Q <= D;` | Must be defined in verilog.h | Q is a storage element that captures D on the rising edge of clk. Defines a clock domain. |
| **Combinational logic** | `assign O = A & B;` | `assign O = A & B;` | O is driven by the bitwise AND of A and B. The `&` is a structural operation (describes a gate). |
| **Parameter (config)** | `parameter WIDTH = 8;` | `parameter WIDTH = 8;` | WIDTH is a configuration constant. Different instantiations can override it. |
| **Initial value** | `initial X = 1'b0;` | `initial X = _1b0;` | X is initialized to 0 at power-on/reset. Describes the INIT state. |
| **Port direction** | `output Y;` | `output net_t *Y;` | Y is driven by this module. The module has write authority. |
| **Port direction** | `input X;` | `input const net_t *X;` | X is read by this module. The module has read-only access. |

### Critical Rules for C Architecture Specification:

1. **Each construct must have a single, unambiguous architectural meaning.** If you use `assign`,
   it means "continuous connection." If you use `always @(posedge clk)`, it means "synchronous
   capture on clock edge." No interpretation, no variation.

2. **Expressions (`&`, `|`, `^`, `~`, etc.) describe structural operations.** They are NOT C
   bitwise operators on integers. They are descriptions of gate/logic cells. The C compiler
   sees `A & B` as a valid expression; you have written "A and B are structurally ANDed."

3. **Vector notation (`[hi:lo]`) must be representable in valid C.** Since C doesn't support
   Verilog's `[3:0]` range syntax, we define macros:
   - `wire_bits(name, hi, lo)` for declarations
   - `range_assign(dst, src, hi, lo)` for assignments (to be added to verilog.h)
   - `bit_select(vec, index)` for single-bit selection (optional, for clarity)
   All preserve the semantic intent in source form.

4. **No invented structure.** Every port, signal, connection, and behavior must come from the
   original `.v`. Do not add "helper" signals, intermediate wires, or reorganization. Describe
   exactly what the `.v` describes.

5. **Ambiguity is a failure.** If the C code is unclear (e.g., "is this synchronous or combinational?"),
   the transcription is wrong. Grow `verilog.h` to eliminate ambiguity.

---

## 3. The hard rules (these are why past devs were rejected)

1. **Copy the `.v` exactly as written.** Same names, ports, directions, parameters,
   connections, expressions. The `.c` reads like the `.v`.
2. **No NAND. No gate decomposition. No component wiring. No "verbs."** Those are
   BUILD acts for a LATER phase. A parts list does not decompose a part into NANDs,
   exactly as a Xilinx parts list doesn't. Operators stay as written (`~`, `^`, `&`,
   `|`); they are the *description*, not something to realize now.
3. **Invent nothing.** No ports, counts, fields, defaults, or behavior the `.v`
   doesn't state. Missing info ⇒ STOP and ask the human. Deriving from what the `.v`
   says is fine; fabricating is not.
4. **Drop nothing, summarize nothing, comment-out nothing.** Every part of the cell's
   description is present. (The big license/banner comment block at the top of each
   `.v` IS dropped — the human asked for that. Keep the Description and Revision.)
5. **It must compile as C.** Verbatim Verilog tokens are not C. We bridge that with
   `lib/verilog.h` (see §4). The `.c` reads like Verilog and compiles.
6. **Do not interpret or paraphrase the architecture.** Write exactly what the `.v` states.
   If the `.v` says `always @(posedge clk) Q <= D;`, you write that (using verilog.h).
   You do NOT write "this is a latch" or "this is a DFF" — those are implementations.
   You describe the behavior exactly, and verilog.h defines what it means.
7. **Do not over-ask.** The form is settled (§5). Read the `.v`, transcribe it, grow
   `verilog.h` only when a genuinely new construct appears, show the result. Don't
   turn each cell into a design debate.

---

## 4. `lib/verilog.h` — the C Architecture Specification Dictionary

`verilog.h` IS the specification language. Each macro defines:
- **The C syntax** (what the code looks like)
- **The architectural meaning** (what it describes)
- **The enforcement contract** (what a validator checks)

Every construct used in a parts-list `.c` must be defined in `verilog.h`. If you encounter
a new construct (a new Verilog keyword, operator, or pattern), you:

1. **Understand its architectural meaning.** What does it describe in real hardware?
2. **Define it in `verilog.h`** with a comment documenting the meaning.
3. **Use that definition** in the cell. Never hand-code.

**Currently defined:**
- `logic_t {LO,HI,X,Z}` — 4-state value
- `net_t {logic_t v;}` — a net/signal (the architectural unit)
- `_1b0`, `_1b1`, `_1bx`, `_1bz` — 4-state literals
- `timescale(unit,prec)`, `celldefine`, `endcelldefine` — directives
- `module(name)` → `void name` (a part)
- `endmodule` — the closing brace
- `output` → `net_t *` (driven by this part)
- `input` → `const net_t *` (read-only from outside)
- `inout` → `net_t *` (bidirectional)
- `parameter` → `static const int` (config constant)
- `wire` → `net_t` (internal signal)
- `reg` → `net_t` (register/storage signal)
- `localparam` → `static const int` (local config)
- `tri0`, `tri1`, `tri(s0, s1)` — tri-state nets with drive strength
- `wire_bits(name, hi, lo)` — vector declaration `[hi:lo]`
- `assign(s0, s1)` — continuous assignment with drive strength
- `initial` — initialization block
- `begin...end` → `{...}` — block delimiters
- `DELAY(n)` — timing delay (no-op in C, marker for intent)
- Verilog directives `` `ifdef ``, `` `define ``, etc. → C `#`

**When you need a new construct:**
- Do NOT hand-code it in the cell
- Add it to `verilog.h` with a comment explaining its architectural meaning
- Use the verilog.h definition
- Rebuild `build.py` will validate it compiles

### Missing constructs (to be added as cells need them):

- `always @(posedge clk)` — synchronous behavior (needs definition in verilog.h)
- `always @(*)` — combinational behavior (needs definition)
- `always @(event)` — event-triggered behavior (needs definition)
- `range_assign(dst, src, hi, lo)` — bit range assignment `[hi:lo]` (needs definition)
- Concatenation `{A, B}` (needs macro)
- Replication `{4{A}}` (needs macro)
- Reduction operators `&A`, `|A` (needs definitions)

---

## 5. The locked file form (GND is the reference — copy its shape)

`clib/unisims/GND.c` is the approved template. Every parts-list entry looks like it:

```c
///////////////////////////////////////////////////////////////////////////////
//   ___   ___
//  | _ ) | _ )    Vendor : TeamBB
//  | _ \ | _ \    Version : 0.0.4
//  |___/ |___/    Description : Functional FPGA Library Component
//                          <CELL one-line description, inherited from the .v>
//   ___   ___     Filename : <CELL>.c
//  | _ ) | _ )    Timestamp : <the actual file-write date/time>
//  | _ \ | _ \
//  |___/ |___/    Source : unisim_src/verilog/src/unisims/<CELL>.v
//
///////////////////////////////////////////////////////////////////////////////
// ---
// cell: <CELL>
// kind: parts-list-entry
// source: unisim_src/verilog/src/unisims/<CELL>.v
// vendor: TeamBB
// version: 0.0.4
// description: <inherited from the .v>
// ports: [ ... as the .v states them ... ]
// params: [ ... ]
// function: <the cell's assign/behavior, in words>
// built_from_nand: false
// ---
//
// Description : <inherited from the .v>
//
// Revision:
//    <every revision line from the .v, marked (from <CELL>.v)>
//    <today> - Transcribed <CELL>.v -> <CELL>.c (TeamBB parts-list entry).
///////////////////////////////////////////////////////////////////////////////
#include "../../lib/verilog.h"

timescale(1 ps, 1 ps)
celldefine

module(<CELL>)( <ports> )
{
    ... parameters, then the assigns, exactly as the .v states them ...
}
endmodule

endcelldefine
```

Locked conventions, do not change:
- **BB logo**, not Xilinx's `X`. Vendor `TeamBB`, Version `0.0.4`.
- **Timestamp = the real file-write date/time** (so commits are honest). Get it with
  `date "+%a %b %e %T %Z %Y"`.
- **Description + Revisions are INHERITED from the source `.v`**, never invented. Add
  one final revision line for our transcription, dated today.
- **YAML front matter** lives inside the `// ...` comment block (so the file stays C),
  for AI devs to follow along. `built_from_nand: false` flags this is the catalog
  phase, not the build.
- **`module(NAME)( ports ) { ... } endmodule`** — the human explicitly chose this
  shape. `assign` is written `assign net->v = VALUE;`. `1'b0`→`VL_0`, etc.
- Verilog re-declares a port in the body (`output G;` after the header); in C the
  direction is in the port list, so it appears once. No info lost.

Every file MUST compile: `cc -c clib/unisims/<CELL>.c -o /dev/null` → exit 0.

---

---

## 6. Enforcement: How we ensure discipline (so you don't have to explain it again)

The goal: **every transcribed cell is correct by construction.** This happens through automated gates,
not human re-explanation.

### 6A. Compilation gate (`build.py`)

**What it checks:**
- Every `.c` file in `clib/unisims/` compiles as C
- Header, YAML metadata, description, and revisions are present
- No hand-rolled constructs outside `verilog.h`
- No invented structure vs the original `.v`

**How to enforce:**
- `build.py` transcribes all 249 cells in parallel
- For each cell: compile with `cc -c ... -o /dev/null`
- Report pass/fail with error details
- **Failure = the transcription is wrong.** Do not commit broken code.

### 6B. Linting gate (`lint_spec.py` — to be written)

**What it checks:**
- No native C operators on `net_t` (e.g., `A + B` is forbidden; use `assign`)
- No unguarded expressions (every assignment must use `assign` or be inside an `always` block)
- Every `assign` has a drive strength (to be added to verilog.h)
- Vector ranges use `range_assign()` or `wire_bits()`, never raw `[3:0]`
- Port directions are consistent (output can't read, input can't drive)
- Parameters are used, not invented
- Initial values are defined (not implicit X)

### 6C. Architectural correctness gate (`arch_check.py` — to be written)

**What it checks:**
- Each construct's architectural meaning is unambiguous
- If the C uses `always @(posedge clk)`, the clock is defined
- If the C uses `assign Y = X[3:0]`, both X and Y are properly declared
- No implicit dependencies (e.g., a signal driven in two places without explicit tri-state notation)
- The C accurately reflects the `.v` (spot-check: description matches, port list matches, parameter defaults match)

### 6D. Build pipeline

**Today:**
```
$ python3 build.py
  → Transcribe all 249 cells to clib/unisims/*.c
  → Compile each with cc -c
  → Report: X pass, Y fail (with errors)
  → Rerun after fixing verilog.h or the transcription
```

**Next (to add):**
```
$ python3 build.py
  → Transcribe, compile (§6A)
  → Lint spec (§6B)
  → Check architecture (§6C)
  → Report: all cells correct, ready for next phase
```

No cell is "done" until it passes all gates.

---

## 7. What changed from the older docs (so you don't get whiplash)

`REPLICA_CONTRACT.md` and the `gate_replica.py` C4–C7 checks describe a PRIOR approach
where we decomposed each cell's logic into wired NAND components and a verb language
(`AND/OR/ASSIGN/...`). **That was wrong for THIS phase.** It conflated *building the
part* with *cataloging the part*. We tore it out. The NAND/component library
(`lib/components.{c,h}`) and verbs still exist and are correct — but they belong to
the LATER build phase, not to transcription. Do not use them in parts-list `.c` files.

**Also changed:** This HANDOFF.md now defines C as an *architecture specification language*
(§2), not just a syntax bridge. verilog.h is no longer just "make the code compile" — it
is the formal definition of what each construct means. Enforcement is built in (§6), so
future devs don't have to re-explain the discipline.

---

## 8. Status (on disk, verified)

- `lib/verilog.h` — the dictionary. Defines what GND needed. **Grow it per new cell.**
- `clib/unisims/GND.c` — the ONE finished, approved, compiling parts-list entry. The
  reference template. Built from `unisim_src/verilog/src/unisims/GND.v`.
- `lib/components.{c,h}`, `test_components.c` — the NAND/verb library. CORRECT, but
  for the LATER build phase. Not used in transcription.
- `clib_gate/`, `contract.sh`, `REPLICA_CONTRACT.md`, `PRINCIPLES.md` — older
  infrastructure from the abandoned approach; superseded by THIS doc for the current
  phase.

**Cells transcribed: 1 of ~249 (GND).**

---

## 9. Your next action

### Phase 1A (Transcription): Cells 2–249

1. Pick the next cell. Smallest-first is easiest to grow the dictionary cleanly. Next
   candidates by size: `VCC` (≈ GND, `assign P = 1'b1;` — confirms the template),
   then `PULLUP`/`PULLDOWN`/`KEEPER` (introduce `input` and pull behavior).
2. Read its `.v` exactly: `nl -ba unisim_src/verilog/src/unisims/<CELL>.v`.
3. Add any new Verilog construct it uses to `lib/verilog.h` (one fixed definition).
   - Understand its architectural meaning (§2, table)
   - Write a clear comment in verilog.h documenting the meaning
   - Define it so the cell `.c` uses it (not hand-rolled)
4. Write `clib/unisims/<CELL>.c` in the GND form — header + YAML + inherited
   description/revisions + the transcribed module. Real write-time timestamp.
5. Compile it (`cc -c ... -o /dev/null`, exit 0). Show the result.
6. Do NOT decompose to NAND. Do NOT invent. Do NOT ask the human to re-explain.

### Phase 1B (Specification Language): Enforce via tools

1. **Build automation:** Enhance `build.py` to:
   - Transcribe all 249 cells in parallel (status quo)
   - Compile each with `cc -c` (status quo)
   - Run `lint_spec.py` on each (new)
   - Run `arch_check.py` on each (new)
   - Report: cells passing all gates (§6)

2. **Create `lint_spec.py`** — validates C architecture specification:
   - No native C operators on `net_t`
   - Vector ranges use macros, not raw `[3:0]`
   - Port directions are consistent
   - Every construct is defined in verilog.h

3. **Create `arch_check.py`** — validates architectural accuracy:
   - C accurately describes the original `.v`
   - No implicit dependencies or invented structure
   - Each construct's meaning is unambiguous

The goal: **all 249 cells compile + pass linting + pass architecture checks,
so every cell is correct by construction. Future devs just follow the form; the gates
enforce discipline.**
