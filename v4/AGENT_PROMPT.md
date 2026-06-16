# V4 Agent Prompt: Transcribe UNISIM Cells

## READ FIRST (binding, non-negotiable)

1. **CLAUDE.md** — V4 section (the task: create exact digital replicas)
2. **v4/HANDOFF.md** — full rules, examples, file form
3. **v4/lib/verilog.h** — C primitive definitions

These are NOT optional. Read them before starting.

---

## THE TASK

**You are creating exact digital replicas of real FPGA hardware IN C.**

UNISIM is the spec of the real Xilinx FPGA. You must copy it exactly to C, using our C primitives (defined in verilog.h). The C replica must match the Verilog spec faithfully, or the design breaks.

**Cells assigned to you:** [LISTED IN AGENT INVOCATION]

**For each cell:**

1. **Read the `.v` file exactly**
   ```
   unisim_src/verilog/src/unisims/<CELL>.v
   ```
   Read the entire file. Understand the structure.

2. **Write `clib/unisims/<CELL>.c` using glbl.c as the template**
   
   Form:
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
   // description: <FROM .v, INHERITED NOT INVENTED>
   // ports: [list from .v]
   // params: [list from .v]
   // function: <brief description of what it does>
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

   <COPY THE .v BODY EXACTLY, line by line>
   ```

3. **Key transformations (verilog.h handles these):**
   - `` `timescale `` → `timescale(...)`
   - `` `celldefine `` → `celldefine`
   - `` `ifdef `` → `#ifdef`
   - `module NAME(ports);` → `module(NAME)(ports)`
   - `output` → `output` (macro = `net_t *`)
   - `input` → `input` (macro = `const net_t *`)
   - `wire` → `wire` (macro = `net_t`)
   - `parameter X = V;` → `parameter X = V;`
   - `assign Y = X;` → `assign Y = X;`
   - `1'b0` → `_1b0` (macro = `(net_t){LO}`)
   - `always @(...)` → `always @(...)`  (if used)
   - `initial` → `initial`

4. **Compile to verify**
   ```bash
   cc -c clib/unisims/<CELL>.c -o /dev/null -I.
   ```
   Exit code MUST be 0. If it fails, fix verilog.h usage.

---

## THE HARD RULES (violations fail)

1. **Copy the `.v` EXACTLY** — same names, ports, parameters, assignments, order. NO CHANGES.
2. **No invented signals, ports, or parameters** — if it's not in `.v`, don't add it.
3. **Description + revisions inherited from `.v`** — copy them exactly, never rewrite.
4. **Every construct uses verilog.h** — don't hand-code C, use the macros.
5. **C must compile** — `cc -c` must exit 0.
6. **No Xilinx headers** — TeamBB header only, no Xilinx logo/copyright/license.

---

## IF YOU GET STUCK

- **Port direction:** look at how glbl.c does it
- **Verilog construct not in verilog.h:** STOP. Don't invent. Tell us (but this should not happen).
- **Compilation error:** Fix the verilog.h usage. Don't hand-code workarounds.

---

## REPORT FORMAT

When done:
```
✓ <CELL1>.c (compiled)
✓ <CELL2>.c (compiled)
...
```

If any fail:
```
✗ <CELL> compilation error: [brief error]
```

---

## THIS IS NOT OPTIONAL

You are creating exact replicas of real hardware. The spec cannot change. Accuracy is the only goal. Read the binding docs first. Follow the rules exactly. Do not invent. Do not re-ask.
