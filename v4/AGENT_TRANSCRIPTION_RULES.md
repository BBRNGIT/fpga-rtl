# AGENT TRANSCRIPTION RULES — READ THIS BEFORE TRANSCRIBING UNISIM CELLS

**This document tells you how to transcribe a Verilog cell to C. These rules are BINDING. Violations fail the build.**

---

## Decision Tree: What Type of Cell Are You Transcribing?

**First question: Is this cell COMBINATIONAL or SEQUENTIAL?**

- **Combinational** = outputs depend only on current inputs (no clocks, no state)
  - Examples: LUT1-LUT6, CARRY8, CARRY4, MUXF7/8/9, AND2B1L, OR2L, INV, BUF
  - Rule: Copy the Verilog STRUCTURE exactly
  - Template: See glbl.c, VCC.c
  - **Proceed to Section A**

- **Sequential** = outputs depend on past state (has clocks, resets, sets, latches)
  - Examples: FDRE, FDSE, FDCE, FDPE, LDCE, LDPE, and similar (any with registers)
  - Rule: NEVER copy behavioral code; use components.h primitives
  - Template: See v4/FLIP_FLOP_PATTERN.md (MANDATORY)
  - **Proceed to Section B**

---

## Section A: Combinational Cells

**Goal:** Copy the Verilog structure exactly into C using verilog.h macros.

### Steps

1. **Read the source `.v` file**
   - Understand what it does (LUT? carry? mux? logic?)
   - Note all ports, parameters, assignments, initial values
   - Do NOT read the behavioral blocks yet — focus on structure

2. **Create the C skeleton**
   ```c
   #include "../../lib/verilog.h"

   timescale(1 ps, 1 ps)
   celldefine

   module(CELLNAME)(
       // ports here
   )
   {
       // declarations here
       // logic here
   }

   endmodule
   endcelldefine
   ```

3. **Transcribe ports, parameters, declarations**
   - Copy port names, directions, types exactly from `.v`
   - Copy parameter names and defaults exactly from `.v`
   - Use verilog.h types: `net *` for ports, `net` for signals
   - Use `wire_bits(name, hi, lo)` for vector declarations `[hi:lo]`

4. **Transcribe logic (assignments, expressions)**
   - Copy `assign` statements exactly (using `assign` macro from verilog.h)
   - Copy expressions exactly (`&`, `|`, `^`, `~`, etc. map directly to C)
   - Use `DELAY(n)` for timing delays `#(n)`
   - Do NOT simplify or reorganize

5. **Add the file header**
   ```c
   ///////////////////////////////////////////////////////////////////////////////
   //   ___   ___
   //  | _ ) | _ )    Vendor : TeamBB
   //  | _ \ | _ \    Version : 0.0.4
   //  |___/ |___/    Description : Functional FPGA Library Component
   //                          <one-line description from .v>
   //   ___   ___     Filename : <CELLNAME>.c
   //  | _ ) | _ )    Timestamp : <date/time>
   //  | _ \ | _ \
   //  |___/ |___/    Source : unisim_src/verilog/src/unisims/<CELLNAME>.v
   //
   ///////////////////////////////////////////////////////////////////////////////
   // ---
   // cell: <CELLNAME>
   // kind: parts-list-entry
   // source: unisim_src/verilog/src/unisims/<CELLNAME>.v
   // vendor: TeamBB
   // version: 0.0.4
   // description: <from .v>
   // ports: [list ports]
   // params: [list parameters]
   // function: <one-line description of what it does>
   // built_from_nand: false
   // ---
   ```

6. **Verify**
   - Compile: `cc -c v4/clib/unisims/CELLNAME.c -I v4` (must succeed)
   - Check: No `always`, `generate`, `@(posedge)`, behavioral code
   - Check: All ports/params from `.v` are in `.c`
   - Check: No invented signals or connections

---

## Section B: Sequential Cells (FLIP-FLOPS)

**Goal:** Use C primitives from components.h to describe the hardware structure. NEVER copy behavioral Verilog code.

### MANDATORY RULES

1. **NEVER copy this from Verilog:**
   ```verilog
   always @(posedge C)
     if (R)
       Q <= 1'b0;
     else if (CE)
       Q <= D;
   ```
   This is BEHAVIORAL code (describes simulation), not STRUCTURAL (describes hardware).

2. **Instead, use the PATTERN from v4/FLIP_FLOP_PATTERN.md**
   - Read it NOW before transcribing
   - It shows exactly how to wire `dff`, `latch`, etc. from components.h
   - It shows how to handle reset, set, clock enable, inversions
   - Follow it EXACTLY — no variations

3. **Steps:**
   - Read FLIP_FLOP_PATTERN.md
   - Note the cell's control inputs (R, S, CLR, PRE, CE, C)
   - Find the matching pattern (FDRE, FDSE, FDCE, FDPE, LDCE, etc.)
   - Copy the pattern, substituting your cell's names
   - Verify it compiles
   - Done

### Examples

**FDRE (D flip-flop with clock enable and async reset):**
```c
module(FDRE)(net *Q, net *C, net *CE, net *D, net *R)
{
    parameter INIT = _1b0;
    parameter IS_C_INVERTED = _1b0;
    parameter IS_D_INVERTED = _1b0;
    parameter IS_R_INVERTED = _1b0;

    wire D_in = D ^ IS_D_INVERTED;
    wire R_in = (R ^ IS_R_INVERTED) && (R != _1bz);

    dff ff;
    wire_dff(&ff, D_in, C, Q);

    if (R_in) {
        Q->level = LO;  /* async reset */
    }

    if (CE || CE == _1bz) {
        dff_settle(&ff);  /* clock and capture */
    }
}
```

**FDSE (D flip-flop with clock enable and async set):**
Same as FDRE, but `INIT = _1b1` and `Q->level = HI;` (not LO).

**LDCE (latch with async clear):**
Use `latch` instead of `dff`. Same pattern otherwise.

See `v4/FLIP_FLOP_PATTERN.md` for all variants.

---

## What NOT to Do

❌ Copy behavioral blocks (`always`, `generate`, `@(...)`)  
❌ Use `<=` or any Verilog procedural assignment  
❌ Hand-code logic that should use components (dff, latch, etc.)  
❌ Invent signals or connections not in the `.v`  
❌ Simplify or reorganize the structure  
❌ Add comments explaining the code (the code IS the spec)  

---

## Validation

After transcribing, VERIFY:

1. **Compiles:**
   ```bash
   cd v4
   cc -c clib/unisims/CELLNAME.c -I . 2>&1 | head -20
   ```
   (Must have zero errors)

2. **Fidelity:**
   - [ ] All ports from `.v` present in `.c`
   - [ ] All parameters from `.v` present in `.c`
   - [ ] Port directions match (input/output/inout)
   - [ ] Combinational: all assign statements present
   - [ ] Flip-flop: follows FLIP_FLOP_PATTERN.md exactly

3. **No behavioral code:**
   - [ ] No `always` (except in comments)
   - [ ] No `generate`
   - [ ] No `@(posedge)`, `@(negedge)`, `@(*)`
   - [ ] No `<=` (Verilog non-blocking assignment)
   - [ ] No procedural logic

4. **Commit:**
   ```bash
   git add v4/clib/unisims/CELLNAME.c
   git commit -m "Add CELLNAME cell (Tier X, Phase Y)"
   git push
   ```
   The pre-commit hook validates everything. If it fails, fix the issue locally and push again.

---

## Quick Checklist

- [ ] Read the `.v` file
- [ ] Determine: Combinational or Sequential?
- [ ] If Combinational: Copy structure exactly (Section A)
- [ ] If Sequential: Follow FLIP_FLOP_PATTERN.md exactly (Section B)
- [ ] Verify compiles: `cc -c clib/unisims/CELLNAME.c -I . 2>&1`
- [ ] Verify fidelity: All ports, params, connections match `.v`
- [ ] Commit and push
- [ ] Done

---

## Questions?

**Q: What if the cell has a construct I've never seen?**  
A: Check if it's in verilog.h. If not, ask the human (do NOT invent a definition).

**Q: Can I reorder the ports or parameters?**  
A: No. Match the `.v` exactly.

**Q: What about the big license block at the top of the `.v`?**  
A: Drop it. Keep the Description and Revision history only.

**Q: What if transcription seems impossible?**  
A: It's not. Either it's a Combinational cell (copy structure) or Sequential (use pattern). Ask the human if unsure.

---

**BINDING RULE:** Violations of these rules fail the build. No exceptions. Follow them exactly.
