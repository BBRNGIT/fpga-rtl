---
name: No Floats, No Heap, No Pointers
description: Data path uses only fixed integers, static arrays, no dynamic allocation
type: constraint
source: FOUNDER_VISION.md §9, CLAUDE.md
---

# No Floats, No Heap, No Pointers

**Core Rule:** The device data path has **zero dynamic behavior**:
- ❌ No floating-point (`float`, `double`)
- ❌ No dynamic allocation (`malloc`, `calloc`, `realloc`)
- ❌ No function pointers
- ❌ No heap of any kind

All state is **static registers**; all computation is **gate logic**. This ensures reproducible, deterministic hardware behavior.

## Why These Constraints

### No Floats

Floating-point is non-deterministic across platforms:
- Different rounding modes
- Different order of operations
- Accumulation errors vary by CPU, compiler, flags

**Hardware is deterministic.** Prices are fixed-point integers (e.g., `uint64_t` in basis points × 10000).

### No Heap / No malloc

Heap allocation is runtime non-determinism:
- Fragmentation patterns vary
- Allocation order depends on history
- Pointers are runtime values, not compile-time known

**Hardware has fixed registers at known addresses.** All state is preallocated at compile time.

### No Function Pointers

Function pointers are dynamic dispatch:
- Target address varies at runtime
- Can't prove what code will execute
- Enables mutation and side effects

**Hardware has fixed combinational paths.** All logic is statically wired at compile time.

## What IS Allowed

✅ **Fixed-point integers:** `uint64_t`, `int32_t`, `uint8_t`
✅ **Static arrays:** `uint64_t history[256]` (fixed size)
✅ **Stack variables:** Local `uint64_t temp;` (allocated at compile time)
✅ **Bitwise operations:** `&`, `|`, `^`, `<<`, `>>`
✅ **Cell calls:** `cell_addsub`, `cell_mux`, etc. (function calls are OK; function pointers are not)

## Constraint Enforcement

### Fixed-Point Integer Arithmetic

**All prices are fixed-point:**
```c
// ❌ NOT allowed
double bid_price = 45.50;     // Float

// ✅ ALLOWED
uint64_t bid_price = 455000;  // In basis points (4550 = $45.50)
```

**Example conversions:**
```c
// $45.50 → 455000 bps (basis points)
#define SCALE 10000
uint64_t price_usd = 4550;
uint64_t price_bps = price_usd * SCALE;  // 45500000

// Back: 455000 bps → $45.50
uint64_t back_to_usd = price_bps / SCALE;  // 4550
```

### Static Arrays (No Dynamic Allocation)

**WRONG — dynamic allocation:**
```c
// ❌ NOT allowed
uint64_t *history = malloc(256 * sizeof(uint64_t));
history[0] = initial_price;
```

**RIGHT — static array:**
```c
// ✅ ALLOWED
#define HISTORY_SIZE 256
uint64_t history[HISTORY_SIZE] = {0};
history[0] = initial_price;

// Or as a register in the netlist
// "registers": [{"name": "HISTORY_RING", "width": 65536, "dff": true}]
```

### Stack vs. Heap

**WRONG:**
```c
void tick() {
  int *temp = malloc(sizeof(int));  // ❌ Heap allocation
  *temp = r[INPUT];
  free(temp);
}
```

**RIGHT:**
```c
void tick() {
  int temp = r[INPUT];  // ✅ Stack (automatic)
  // temp lives on stack, freed at function end
}
```

### Function Pointers (Not Allowed)

**WRONG:**
```c
typedef uint64_t (*operator_t)(uint64_t, uint64_t);

operator_t ops[4] = {add, sub, mul, div};
uint64_t result = ops[op_code](a, b);  // ❌ Dynamic dispatch
```

**RIGHT:**
```c
// Use cell_mux to select operation, not function pointers
uint64_t add_result = 0;
cell_addsub(a, b, 0, &add_result);

uint64_t sub_result = 0;
cell_addsub(a, b, 1, &sub_result);

uint64_t selected = 0;
cell_mux(op_code, add_result, sub_result, &selected);
```

## In Practice: Registers Are Memory

The netlist defines all storage as registers:

```json
{
  "registers": [
    {"name": "PRICE_CURRENT", "dff": true, "width": 64},
    {"name": "PRICE_HISTORY", "dff": true, "width": 65536}  // Ring buffer
  ]
}
```

These map to C arrays in the backplane:

```c
#define PRICE_HISTORY_SIZE (65536 / 64)  // In uint64_t units
typedef struct {
  uint64_t PRICE_CURRENT;
  uint64_t PRICE_HISTORY[PRICE_HISTORY_SIZE];
} device_regs_t;

word_t *r = (word_t *)backplane_base;
// Access: r[PRICE_CURRENT], r[PRICE_HISTORY], etc.
```

## Checking Compliance

### Static Analysis

Before gate.sh, check for forbidden patterns:

```sh
cd .hft_staging/<module>

# Look for float/double
grep -r "float\|double" *.c *.h | grep -v "^[^:]*:.*//.*"
# Should return nothing

# Look for malloc/calloc
grep -r "malloc\|calloc\|realloc" *.c *.h | grep -v "^[^:]*:.*//.*"
# Should return nothing

# Look for function pointers
grep -r "(\*" *.c *.h | grep -v "^[^:]*:.*//.*"
# Should return nothing (or only in comments)
```

### Compiler Flags

Use compiler flags to enforce:

```makefile
# In component Makefile
CFLAGS += -Werror=all          # All warnings → errors
CFLAGS += -Wfloat-equal        # Warn on float comparisons
CFLAGS += -Wno-float-conversion # Warn on float casts (if needed)
```

## Data Representation Examples

### Prices

```c
// Price: $45.50
#define SCALE 10000  // Basis points
uint64_t price_bps = 455000;
```

### Time

```c
// TAI timestamp: arbitrary large counter
uint64_t tai_counter;  // Free-running, no floats
```

### Quantities

```c
// Volume: 500 shares
uint64_t quantity = 500;
```

### Ratios

```c
// Ratio: 2:1 (e.g., pipeline:MAC clock ratio)
// Represented as fixed constant, not computed
#define PIPELINE_CLOCK_MUL 2
#define MAC_CLOCK_DIV 1
```

## Pre-graduation Checklist

Before running `gate.sh`:

- [ ] No `float` or `double` in data path
- [ ] No `malloc`, `calloc`, `realloc` in device code
- [ ] No function pointers in device code
- [ ] All state is static registers or stack variables
- [ ] All prices are fixed-point integers
- [ ] All arrays are statically sized

## References

- FOUNDER_VISION.md §9 — Non-Negotiable Rules (Data Path)
- FOUNDER_VISION.md §7 — The Data Law (Bid/Ask only)
- CLAUDE.md — No Floats, No Heap, No Function Pointers
