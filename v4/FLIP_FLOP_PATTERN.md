# FLIP-FLOP TRANSCRIPTION PATTERN

**BINDING RULE:** This pattern MUST be followed for all flip-flop cells (FDRE, FDSE, FDCE, FDPE, LDCE, LDPE, and similar).

**Purpose:** Define the correct structure for transcribing flip-flop Verilog cells to C using components.h primitives.

---

## WHAT NOT TO DO

❌ **NEVER copy this from Verilog:**
```verilog
always @(posedge C)
  if (R)
    Q <= 1'b0;
  else if (CE)
    Q <= D;
```

❌ **Reason:** This is BEHAVIORAL code (describes simulation execution), not STRUCTURAL code (describes hardware connections). C is our RTL — it must describe STRUCTURE, not behavior.

---

## WHAT TO DO: The Pattern

### 1. Declarations (from Verilog, structural only)

```c
#include "../../lib/verilog.h"

timescale(1 ps, 1 ps)
celldefine

module(FDRE)(
    net *Q,       /* output */
    net *C,       /* clock input */
    net *CE,      /* clock enable input */
    net *D,       /* data input */
    net *R        /* reset input */
)
{
    /* Parameters (from Verilog) */
    parameter INIT = _1b0;
    parameter IS_C_INVERTED = _1b0;
    parameter IS_D_INVERTED = _1b0;
    parameter IS_R_INVERTED = _1b0;

    /* Internal signals (structural) */
    wire D_in, R_in;
    dff my_ff;                    /* Component from components.h */
    edge clock_edge;              /* Edge detector from components.h */
```

### 2. Logic (using COMPONENTS, not behavioral code)

```c
    /* Handle input inversions (from parameters) */
    assign D_in = D ^ IS_D_INVERTED;
    assign R_in = R ^ IS_R_INVERTED;

    /* Wire the DFF component */
    wire_dff(&my_ff, D_in, C, Q);

    /* Clock edge detection */
    /* (happens in dff_settle when clock edge occurs) */

    /* Reset override (async) */
    /* If R is asserted, force Q to 0 */
    if (R_in && (R != _1bz)) {
        Q->level = LO;
    }

    /* Clock enable gating (optional, depends on cell) */
    /* If CE is not asserted and no clock edge, Q holds */
    /* (This is implicit in dff behavior — it only captures on edge+CE) */
}

endmodule
endcelldefine
```

### 3. Key Rules

1. **Ports:** Copy exactly from Verilog (Q, C, CE, D, R/S/CLR/PRE)
2. **Parameters:** Copy exactly from Verilog (INIT, IS_*_INVERTED)
3. **NO behavioral blocks:** No `always`, `generate`, `@(posedge)`, `<=`
4. **Use components:** `dff` (clocked), `reg` (latch-based), `latch` (SR latch)
5. **Use helpers:** `edge_pos()` for edge detection, `wire_dff()` for wiring, `dff_settle()` for settlement
6. **Async control:** Reset/Set/Clear as combinational logic (override Q directly)
7. **Sync control:** Clock enable as input to dff wiring (checked in dff_settle)

---

## Examples by Cell Type

### FDRE (D flip-flop with clock enable and reset)

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

    /* Async reset: forces Q to 0 when R is asserted */
    if (R_in) {
        Q->level = LO;
    }

    /* Clock enable check (in dff_settle): only capture if CE or undefined */
    if (CE || CE == _1bz) {
        dff_settle(&ff);
    }
}
```

### FDSE (D flip-flop with clock enable and set)

Same as FDRE, but:
- Parameter: `INIT = _1b1` (default high, not low)
- Async set: `Q->level = HI;` (not LO)
- Input: `S` (not `R`)

```c
module(FDSE)(net *Q, net *C, net *CE, net *D, net *S)
{
    parameter INIT = _1b1;
    parameter IS_C_INVERTED = _1b0;
    parameter IS_D_INVERTED = _1b0;
    parameter IS_S_INVERTED = _1b0;

    wire D_in = D ^ IS_D_INVERTED;
    wire S_in = (S ^ IS_S_INVERTED) && (S != _1bz);

    dff ff;
    wire_dff(&ff, D_in, C, Q);

    if (S_in) {
        Q->level = HI;     /* SET to 1, not RESET to 0 */
    }

    if (CE || CE == _1bz) {
        dff_settle(&ff);
    }
}
```

### FDCE (D flip-flop with clock enable and async clear)

Same as FDRE (clear = reset to 0):

```c
module(FDCE)(net *Q, net *C, net *CE, net *D, net *CLR)
{
    parameter INIT = _1b0;
    parameter IS_C_INVERTED = _1b0;
    parameter IS_D_INVERTED = _1b0;
    parameter IS_CLR_INVERTED = _1b0;

    wire D_in = D ^ IS_D_INVERTED;
    wire CLR_in = (CLR ^ IS_CLR_INVERTED) && (CLR != _1bz);

    dff ff;
    wire_dff(&ff, D_in, C, Q);

    if (CLR_in) {
        Q->level = LO;     /* CLEAR to 0 */
    }

    if (CE || CE == _1bz) {
        dff_settle(&ff);
    }
}
```

### FDPE (D flip-flop with clock enable and async preset)

Same as FDSE (preset = set to 1):

```c
module(FDPE)(net *Q, net *C, net *CE, net *D, net *PRE)
{
    parameter INIT = _1b1;
    parameter IS_C_INVERTED = _1b0;
    parameter IS_D_INVERTED = _1b0;
    parameter IS_PRE_INVERTED = _1b0;

    wire D_in = D ^ IS_D_INVERTED;
    wire PRE_in = (PRE ^ IS_PRE_INVERTED) && (PRE != _1bz);

    dff ff;
    wire_dff(&ff, D_in, C, Q);

    if (PRE_in) {
        Q->level = HI;     /* PRESET to 1 */
    }

    if (CE || CE == _1bz) {
        dff_settle(&ff);
    }
}
```

---

## Variants

### LDCE / LDPE (Latches, not flip-flops)

Use `latch` instead of `dff`:

```c
module(LDCE)(net *Q, net *D, net *G, net *CLR)
{
    wire D_in = D;
    wire CLR_in = (CLR) && (CLR != _1bz);

    latch l;
    wire_latch(&l, D_in, G, Q);    /* G is gate/enable */

    if (CLR_in) {
        Q->level = LO;
    }

    latch_settle(&l);
}
```

### Clock Inversion (IS_C_INVERTED)

If `IS_C_INVERTED = 1`, the clock edge is on the FALLING edge, not rising:

```c
if (IS_C_INVERTED) {
    /* Trigger on negedge */
    if (edge_neg(&clock_edge)) {
        dff_settle(&ff);
    }
} else {
    /* Trigger on posedge (default) */
    if (edge_pos(&clock_edge)) {
        dff_settle(&ff);
    }
}
```

---

## Testing & Validation

After transcribing a flip-flop cell:

1. **Syntax:** `cc -c v4/clib/unisims/CELLNAME.c -I v4` (must compile)
2. **Structure:** Verify ports, parameters match `.v` exactly
3. **No behavioral:** Search for `always`, `generate`, `@(`, `deassign` — must be zero
4. **Components used:** Verify `dff`, `latch`, `edge_pos`, `dff_settle()`, `latch_settle()` calls are present
5. **CI/CD:** Push to GitHub, watch CI/CD validate automatically (BUILD.sh + pre-commit)

---

## Remember

**This is the ONLY pattern for flip-flops.** Do not invent variations. Do not copy behavioral Verilog. Use components. Wire structurally. Let the C compiler enforce correctness.

**BINDING RULE:** Violations of this pattern fail the build. No exceptions.
