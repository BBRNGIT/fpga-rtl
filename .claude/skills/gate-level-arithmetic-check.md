---
name: Gate-Level Arithmetic Check
description: Device data path must use structural cells only — no native +/-/* in generated ticks
type: enforcement
source: FOUNDER_VISION.md §2 & §9, CLAUDE.md
---

# Gate-Level Arithmetic Check

**Core Rule:** The device data path is **entirely structural** (gate-level). Native C arithmetic operators (`+`, `-`, `*`) are forbidden inside the generated `*_tick()` function. All arithmetic goes through `cell_addsub`, `cell_mul`, etc.

## Why This Rule Matters

Native C operators compile to sequential microcode on a CPU. On an FPGA, we need **flip-flop-level gates** where every signal, latch, and addition is its own addressed register. The gate-level arithmetic check ensures the device is truly hardware at the atomic level, not C pretending to be hardware.

## The Restriction

### ❌ NOT Allowed in *_tick()

```c
// BAD — native C arithmetic in generated tick
static inline void adapter_tick(word_t *r) {
  uint64_t sum = r[A] + r[B];          // ❌ Native +
  uint64_t diff = r[X] - r[Y];         // ❌ Native -
  uint64_t prod = r[M] * r[N];         // ❌ Native *
  
  if (r[SEL] == 1) {                   // ❌ No if in tick
    r[OUT] = r[IN] + 10;
  }
  
  r[OUT] = sum;
}
```

### ✅ ALLOWED in *_tick()

```c
// GOOD — structural cells in generated tick
static inline void adapter_tick(word_t *r) {
  uint64_t sum = 0;
  cell_addsub(r[A], r[B], 0, &sum);    // ✅ Structural addition
  
  uint64_t diff = 0;
  cell_addsub(r[X], r[Y], 1, &diff);   // ✅ Structural subtraction (carry_in=1)
  
  uint64_t prod = 0;
  cell_mul(r[M], r[N], &prod);         // ✅ Structural multiplication
  
  uint64_t mux_out = 0;
  cell_mux(r[SEL], r[IF_TRUE], r[IF_FALSE], &mux_out);  // ✅ Mux instead of if
  
  r[OUT] = mux_out;
}
```

## gate.sh Stage 2b: Arithmetic Check

The gate uses AWK to scan `*_gen.h` and enforce this rule:

```
==> [gate] 2b/3 gate-level arithmetic (no native +/-/* in generated tick)
    adapter_gen.h tick: no native +/-/* — OK
```

### How the AWK Check Works

1. **Strips comments** — Removes `/* */` and `//` comments (so prose never triggers false positives)
2. **Locates tick body** — Finds `_tick(` and the matching closing `}` at column 0
3. **Blanks out cell calls** — Replaces `cell_*( ... )` with spaces (operators inside cells are legal)
4. **Whitelists safe patterns** — Allows `>>`, `<<`, and `i = i + 1ULL` (loop counters)
5. **Scans for violations** — Looks for `+`, `-`, `*` outside of cell calls

### Failure Output

```
==> [gate] 2b/3 gate-level arithmetic (no native +/-/* in generated tick)
[FAIL] native arithmetic operator in generated tick (adapter_gen.h):
  156: r[OUT] = r[IN] + 100;
  167: uint64_t sum = a - b;
  
  FIX: Use cell_addsub for arithmetic:
    cell_addsub(r[IN], 100, 0, &out);  // addition
    cell_addsub(a, b, 1, &out);        // subtraction (carry_in=1)
```

## Mapping C Operators to Cells

| Operation | C Code | Cell Call |
|-----------|--------|-----------|
| Addition | `a + b` | `cell_addsub(a, b, 0, &result)` |
| Subtraction | `a - b` | `cell_addsub(a, b, 1, &result)` (carry_in=1) |
| Multiplication | `a * b` | `cell_mul(a, b, &result)` |
| Conditional | `sel ? x : y` | `cell_mux(sel, x, y, &result)` |
| Bit shift left | `a << b` | `cell_sar(a, -b, &result)` or mask |
| Bit shift right | `a >> b` | `cell_sar(a, b, &result)` or mask |
| Equality | `a == b` | `cell_eqmask(a, b, &result)` |
| Comparison `<` | `a < b` | `cell_cmp_lt(a, b, &result)` |
| Bitwise AND | `a & b` | `cell_and(a, b, &result)` |
| Bitwise OR | `a \| b` | `cell_or(a, b, &result)` |
| Bitwise XOR | `a ^ b` | `cell_xor(a, b, &result)` |

## What IS Allowed (Not Flagged)

✅ **Outside tick function**
- Host code in buffer.c, display.c, test code
- Native arithmetic is fine here; it's not device logic

✅ **Inside helper functions called by tick**
- Comparators, cell implementations
- These are infrastructure, not device data path

✅ **Loop counters**
- `i = i + 1ULL` (increment in for loops)
- Shift operators `>>`, `<<`

✅ **Array indexing**
- `arr[i]` (brackets don't trigger arithmetic check)

## Preventing Arithmetic Violations

### During Netlist Design

When writing `gen_<module>_net.py`, define every arithmetic operation as a `comb_node`:

```json
{
  "comb_nodes": [
    {
      "name": "price_adder",
      "reads": ["PRICE_A", "PRICE_B"],
      "writes": ["PRICE_SUM"],
      "logic": {"type": "cell_addsub", "carry_in": 0}
    }
  ]
}
```

### During gennet.py

When writing `gennet.py`, translate `comb_nodes` to `cell_*()` calls:

```python
# In gennet.py
for node in spec['comb_nodes']:
    if node['logic']['type'] == 'cell_addsub':
        print(f"uint64_t {node['name']} = 0;")
        carry = node['logic'].get('carry_in', 0)
        inputs = node['reads']
        print(f"cell_addsub(r[{inputs[0]}], r[{inputs[1]}], {carry}, &{node['name']});")
        # Later, in WRITE phase:
        for output in node['writes']:
            print(f"r[{output}] = {node['name']};")
```

## Pre-gate Checklist

Before running `gate.sh`:

- [ ] All arithmetic in netlist is defined as comb_nodes
- [ ] gennet.py translates all operations to cell_*() calls
- [ ] `*_gen.h` contains no native `+`/`-`/`*` outside cell calls
- [ ] No native arithmetic in tick body
- [ ] All conditionals replaced with cell_mux

## Common Violations and Fixes

| Code | Problem | Fix |
|------|---------|-----|
| `r[OUT] = r[A] + r[B]` | Native + in tick | Use `cell_addsub` |
| `if (r[SEL]) { ... }` | Native if in tick | Use `cell_mux` to select |
| `r[C] = a > b ? x : y` | Native ternary | Use `cell_mux` instead |
| `for (int i = 0; i < n; i++)` | Loop in tick | Unroll or use cell logic |
| `r[OUT] = (a + b) * c` | Nested arithmetic | Break into separate cells |

## Debugging Arithmetic Failures

If gate.sh 2b fails:

1. **Locate the violation**
   ```sh
   grep -n "+\|-\|*" .hft_staging/<module>/<module>_gen.h \
     | grep -v "cell_" | grep -v "//" | grep -v "/*"
   ```

2. **Check the netlist**
   ```sh
   cat <module>.net.json | grep -A5 "ARITHMETIC_NODE"
   ```

3. **Regenerate**
   ```sh
   python3 gennet.py <module>.net.json > <module>_gen.h
   ```

4. **Verify the fix**
   ```sh
   .hft_staging/gate.sh .hft_staging/<module>
   ```

## References

- FOUNDER_VISION.md §2 — Gate-Level Arithmetic
- FOUNDER_VISION.md §9 — Non-Negotiable Rules (Data Path)
- CLAUDE.md — Gate-Level Arithmetic section
- `.hft_staging/gate.sh` — Stage 2b implementation (lines 63–108)
- `.hft_staging/adapter/cells.h` — Cell primitives reference
