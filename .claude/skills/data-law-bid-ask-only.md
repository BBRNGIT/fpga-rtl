---
name: Data Law — Bid/Ask Only
description: Bid/ask prices are primitives — no inference, no mid as decision input, derived metrics are read-only
type: constraint
source: FOUNDER_VISION.md §7, CLAUDE.md
---

# Data Law — Bid/Ask Only

**Core Rule:** The data path works with **bid and ask prices ONLY** as primitives. No invented or inferred fields. Derived metrics (mid, spread) are allowed as read-only outputs, never as decision inputs.

## The Primitives at Wire

```
Wire carries:
✅ BID (best bid price)
✅ ASK (best ask price)
✅ QTY_BID (bid quantity)
✅ QTY_ASK (ask quantity)
✅ SYMBOL (e.g., AAPL)
✅ TIME (wire timestamp)
✅ SEQ (sequence number)
✅ VALID (data valid flag)

NOT in wire:
❌ SIDE (inferred from context)
❌ TRADED (inferred from price move)
❌ MID (calculated)
❌ SPREAD (calculated)
```

**These are facts, not inferred.**

## Derived Metrics (Read-Only)

Downstream modules **may calculate** mid, spread, imbalance, etc. But these:

1. **Are never decision inputs** — No conditional logic based on mid price
2. **Live in output registers** — Marked read-only for consumers
3. **Never feed back into logic** — No "if mid > X then..."

**WRONG (mid as decision input):**
```c
// ❌ BAD — using mid for a decision
uint64_t mid = (r[BID] + r[ASK]) / 2;
if (mid > threshold) {
  r[ACTION] = BUY;  // Decision based on derived mid
}
```

**RIGHT (mid as metric only):**
```c
// ✅ GOOD — mid is output, not decision input
uint64_t mid = 0;
cell_addsub(r[BID], r[ASK], 0, &mid);
uint64_t mid_half = 0;
cell_sar(mid, 1, &mid_half);
r[MID_PRICE_OUTPUT] = mid_half;  // Published, read-only

// Decisions based on BID and ASK only
uint64_t bid_touch = cell_cmp_gt(r[BID], threshold);
uint64_t ask_touch = cell_cmp_gt(r[ASK], threshold);
```

## No Inference

**WRONG (inferring side):**
```c
// ❌ BAD — inferring side from context
uint64_t side;
if (r[PRICE] < r[BID]) {
  side = SELL;  // Inferred, not provided
} else {
  side = BUY;
}
```

**RIGHT (side is explicit input or not used):**
```c
// ✅ GOOD — either side is provided, or we don't use it
uint64_t side = r[SIDE_INPUT];  // Explicit
// OR: we only care about bid/ask, not side
uint64_t imbalance = r[QTY_BID] - r[QTY_ASK];  // Pure data
```

## Netlist Constraint

In the netlist, enforce data law:

```json
{
  "registers": [
    {"name": "BID", "dff": true, "width": 64},
    {"name": "ASK", "dff": true, "width": 64},
    {"name": "QTY_BID", "dff": true, "width": 32},
    {"name": "QTY_ASK", "dff": true, "width": 32}
  ],
  "seam_nodes": [
    {"name": "BID", "width": 64},
    {"name": "ASK", "width": 64},
    {"name": "QTY_BID", "width": 32},
    {"name": "QTY_ASK", "width": 32},
    {"name": "MID_PRICE_CALCULATED", "width": 64},  // ✅ Derived, output
    {"name": "SPREAD_CALCULATED", "width": 64}       // ✅ Derived, output
  ],
  "comb_nodes": [
    {
      "name": "mid_calc",
      "reads": ["BID", "ASK"],
      "writes": ["MID_PRICE_CALCULATED"],
      "logic": {"type": "mid_adder"}  // One-way: bid+ask→mid
    }
  ]
}
```

**Key:** MID is a seam_node (published output), never a cross_module_input (decision input).

## Decision Logic Examples

### WRONG (using derived metrics)

```c
// ❌ NO — uses mid_price
uint64_t mid = (r[BID] + r[ASK]) / 2;
if (mid > threshold) {
  r[DECISION] = BUY;
}
```

### RIGHT (using primitives)

```c
// ✅ YES — uses bid and ask directly
uint64_t bid_high = cell_cmp_gt(r[BID], threshold);
uint64_t ask_high = cell_cmp_gt(r[ASK], threshold);
uint64_t both_high = cell_and(bid_high, ask_high);
r[DECISION] = both_high ? BUY : HOLD;  // Decision on primitives
```

## Spread and Imbalance

**Allowed:** Calculate and publish these as metrics.
**Not allowed:** Use them in decision logic.

```c
// ✅ ALLOWED — compute spread as output metric
uint64_t spread = 0;
cell_addsub(r[ASK], r[BID], 1, &spread);  // ASK - BID
r[SPREAD_OUTPUT] = spread;

// ✅ ALLOWED — compute imbalance as metric
uint64_t imbalance = 0;
cell_addsub(r[QTY_BID], r[QTY_ASK], 1, &imbalance);
r[IMBALANCE_OUTPUT] = imbalance;

// ❌ NOT ALLOWED — use spread for decision
if (r[SPREAD_OUTPUT] < narrow_threshold) {
  r[DECISION] = TRADE;  // NO — using derived metric
}

// ✅ ALLOWED — use qty's directly for decision
uint64_t qty_imbalanced = cell_cmp_gt(r[QTY_BID], r[QTY_ASK]);
r[DECISION] = qty_imbalanced ? BUY_MORE : HOLD;
```

## Module Boundaries

**Adapter** (wire → adapter):
- Reads: BID, ASK from wire
- Outputs: BID, ASK (passthrough or latch)
- Never infers or derives; transparent

**DOM** (adapter → dom):
- Reads: BID, ASK, QTY_BID, QTY_ASK
- Builds order book from these primitives
- Outputs: DOM_BID[n], DOM_ASK[n] (book structure)

**Candle** (dom → candle):
- Reads: DOM_BID, DOM_ASK
- Calculates bars: HIGH, LOW, OPEN, CLOSE
- Outputs: OHLC values (pure aggregation, not inference)

## Pre-graduation Checklist

Before `gate.sh`:

- [ ] No SIDE, IS_BUY, IS_SELL, IS_TRADED in device registers
- [ ] All decisions based on BID and ASK, not derived MID
- [ ] Derived metrics (mid, spread) are published as seam_nodes, not cross_module_inputs
- [ ] No feedback loops (mid → logic → mid)
- [ ] No invented fields; all data is sourced

## Auditing for Data Law Violations

```sh
# Check for inferred fields
grep -r "is_buy\|is_sell\|is_trade\|side" .hft_staging/<module>/*.net.json
# Should return nothing (side is only in adapter from source)

# Check for mid-price logic in netlist
grep -r "mid" .hft_staging/<module>/*.net.json
# Should only show in seam_nodes (output), not comb_nodes (logic)

# Verify no feedback loops
jq '.comb_nodes[] | select(.writes[] == .reads[])' <module>.net.json
# Should return nothing (no node reads its own output)
```

## Common Data Law Violations

| Violation | Fix |
|-----------|-----|
| Using mid in decision | Use BID and ASK directly; calculate mid for output only |
| Inferring side | Don't infer; use explicit side input if needed |
| Circular mid dependency | Mid is calc-only; never feeds back into decision logic |
| Invented field in registers | Only primitives in data path |
| Mid as cross_module_input | Mid is output; consumers derive it themselves or read published mid |

## References

- FOUNDER_VISION.md §7 — The Data Law
- FOUNDER_VISION.md §6 — The Wire & Ingress Chain
- CLAUDE.md — Data Law: Price-Only at Wire
