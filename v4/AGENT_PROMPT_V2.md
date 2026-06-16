# V4 Agent Prompt V2: Transcribe with Real Components (PROVEN MODEL)

## READ FIRST (binding, non-negotiable)

1. **CLAUDE.md** — V4 section (create exact digital replicas)
2. **v4/HANDOFF.md** — rules, file form
3. **v4/lib/verilog.h** — NOW LINKS TO REAL COMPONENTS
4. **v4/lib/components.h** — REAL digital primitives (NAND, AND, OR, NOT, LATCH, REG, DFF)
5. **v4/MODEL_PROOF.md** — PROVEN: Verilog text → real hardware primitives
6. **v4/test_and_gate.c** — Proof that real components work

---

## THE MODEL (PROVEN)

```
Verilog spec (e.g., glbl.v)
    ↓ (copy text exactly)
C cell using verilog.h macros
    ↓ (verilog.h instantiates components)
components.h real digital primitives
    ↓ (instantiate, wire, settle)
Actual hardware logic that WORKS
```

**Key difference from V1:** verilog.h now points to REAL components, not no-ops.

---

## THE TASK

**For each assigned cell:**

1. **Read the `.v` file exactly**
   ```
   unisim_src/verilog/src/unisims/<CELL>.v
   ```

2. **Write `clib/unisims/<CELL>.c`** using verilog.h (which now instantiates real components)
   
   Form (from glbl.c template):
   ```c
   ///////////////////////////////////////////////////////////////////////////////
   //   ___   ___
   //  | _ ) | _ )    Vendor : TeamBB
   //  | _ \ | _ \    Version : 0.0.4
   //  |___/ |___/    Description : Functional FPGA Library Component
   //                          <ONE-LINE DESCRIPTION FROM .v>
   //   ___   ___     Filename : <CELL>.c
   //  | _ ) | _ )    Timestamp : <date "+%a %b %e %T %Z %Y">
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
   // description: <FROM .v>
   // ports: [list from .v]
   // params: [list from .v]
   // function: <brief description>
   // built_from_nand: false
   // ---
   //
   // Description : <FROM .v>
   //
   // Revision:
   //    <EVERY REVISION LINE FROM .v, marked (from <CELL>.v)>
   //    <TODAY'S DATE> - Transcribed <CELL>.v -> <CELL>.c (TeamBB parts-list entry).
   ///////////////////////////////////////////////////////////////////////////////
   #include "../../lib/verilog.h"

   <COPY THE .v BODY EXACTLY>
   ```

3. **Key: verilog.h macros now instantiate real components**
   - `wire X;` → `wire_t X;` (real wire from components.h)
   - `reg X;` → `reg_t X;` (real register/latch from components.h)
   - `assign Y = A & B;` → instantiates AND gate, wires it, settles it
   - `initial X = _1b0;` → sets initial value on wire/reg
   - Each macro references actual hardware primitives

4. **Compile to verify**
   ```bash
   cc -c clib/unisims/<CELL>.c -o /dev/null -I.
   ```
   Exit code MUST be 0. If it fails, verilog.h macro is missing or wrong.

---

## THE HARD RULES (violations fail)

1. **Copy the `.v` EXACTLY** — same text, same order, no changes
2. **Use verilog.h macros** — every construct (wire, assign, initial, etc.)
3. **No invented signals/ports/parameters** — everything from `.v`
4. **Description + revisions inherited** — never rewritten
5. **Must compile** — `cc -c` exit 0 required
6. **No Xilinx headers** — TeamBB only

---

## WHY THIS WORKS

The Verilog text IS the hardware spec. verilog.h macros instantiate real components. Components are proven working (test_and_gate.c). The text → components chain is proven. No interpretation, no hand-coding.

---

## REPORT FORMAT

```
✓ <CELL1>.c (compiled, real components instantiated)
✓ <CELL2>.c (compiled, real components instantiated)
...
```

If any fail:
```
✗ <CELL> compilation error: [brief error]
```

---

## READ THE PROOF

Run test_and_gate.c to see the model in action:
```bash
cd v4
cc -c lib/components.c -o lib/components.o
cc test_and_gate.c -o test_and_gate -I.
./test_and_gate
# Output: AND gate tests pass ✓
```

This proves the model. Your cells use the same components. Go.
