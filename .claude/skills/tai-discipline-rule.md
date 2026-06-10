---
name: TAI Discipline Rule
description: TAI is authoritative timestamp — free-running off taiosc, no PPS or PI loop in deterministic model
type: constraint
source: FOUNDER_VISION.md §5, CLAUDE.md
---

# TAI Discipline Rule

**Core Rule:** In the deterministic model:
- TAI is a **plain counter** running off `taiosc` (authoritative oscillator)
- **NO PPS (pulse-per-second)** input
- **NO PI loop** (proportional-integral discipline)
- **NO per-domain discipline**
- One deterministic time base drives everything

TAI is the **sole authoritative time source** for the entire system.

## TAI ≠ MAC Clock

**Critical distinction:**

- **MAC clock** = 125 MHz sample clock (when NIC reads the wire)
- **TAI** = Timestamp value (a separate oscillator, free-running)

These are **independent**. The NIC samples on MAC edges and stamps with TAI's current value (brought into MAC domain via CDC gray-code synchronizer).

**WRONG (conflating them):**
```c
// ❌ BAD — TAI and MAC are not the same
uint64_t tai = mac_sample_count;  // NO — TAI is its own oscillator
```

**RIGHT (separate):**
```c
// ✅ GOOD — TAI is independent; stamped into MAC domain via CDC
uint64_t tai = taiosc_counter;              // TAI: free-running off taiosc
uint64_t tai_in_mac_domain = cdc_gray2(tai); // CDC brings TAI into MAC domain
// On MAC edge: timestamp = tai_in_mac_domain
```

## The TAI Architecture (Deterministic Model)

```
┌──────────────┐
│   taiosc     │  Authoritative oscillator (free-running counter)
│  (frequency) │
└──────┬───────┘
       │
       ├─→ [TAI]  (plain counter, one edge per taiosc cycle)
       │
       ├─→ [TAI_GRAY]  (binary → gray code for CDC)
       │
       └─→ [TAI_CDC_FF1] ─→ [TAI_CDC_FF2]  (gray synchronizers)
                              │
                              ├─→ [TAI_IN_MAC_DOMAIN]
                              │    (NIC reads this when sampling)
```

**No feedback loop. No PLL. No PI loop. Pure feed-forward.**

## taiosc Module

The authoritative oscillator is the simplest module:

```json
{
  "registers": [
    {"name": "TAIOSC_COUNTER", "dff": true, "width": 64}
  ],
  "comb_nodes": [
    {
      "name": "taiosc_increment",
      "reads": ["TAIOSC_COUNTER"],
      "writes": ["TAIOSC_COUNTER_NEXT"],
      "logic": {"type": "cell_addsub", "a": "TAIOSC_COUNTER", "b": 1, "carry_in": 0}
    }
  ]
}
```

**In the WRITE phase:**
```c
r[TAIOSC_COUNTER] = counter_next;  // +1 per cycle, deterministic
```

## tai Module

The TAI counter is fed from taiosc:

```json
{
  "registers": [
    {"name": "TAI", "dff": true, "width": 64}
  ],
  "cross_module_inputs": [
    {"name": "TAIOSC_COUNTER"}
  ],
  "comb_nodes": [
    {
      "name": "tai_latch",
      "reads": ["TAIOSC_COUNTER"],
      "writes": ["TAI_NEXT"],
      "logic": {"type": "cell_buf", "input": "TAIOSC_COUNTER"}
    }
  ]
}
```

**Result:** TAI = TAIOSC (one cycle delay due to CDC staging).

## tai_cdc Module

Gray-code synchronizer brings TAI into MAC domain:

```json
{
  "registers": [
    {"name": "TAI_GRAY", "dff": true},
    {"name": "TAI_GRAY_FF1", "dff": true},
    {"name": "TAI_GRAY_FF2", "dff": true}
  ],
  "cross_module_inputs": [
    {"name": "TAI"}
  ],
  "comb_nodes": [
    {
      "name": "binary_to_gray",
      "reads": ["TAI"],
      "writes": ["TAI_GRAY"],
      "logic": {"type": "gray_encode"}
    },
    {
      "name": "gray_decode_ff2",
      "reads": ["TAI_GRAY_FF2"],
      "writes": ["TAI_IN_MAC_DOMAIN"],
      "logic": {"type": "gray_decode"}
    }
  ]
}
```

**Flow:**
1. TAI (in TAI domain) → Gray code
2. Gray code → FF1 (synchronizer stage 1)
3. FF1 → FF2 (synchronizer stage 2)
4. FF2 → Gray decode → TAI_IN_MAC_DOMAIN (ready to use in MAC tick)

## NIC Usage: Timestamp on Sample

When the NIC samples data on a MAC edge:

```c
// In nic_tick() (MAC domain)
uint64_t data_in = r[WIRE_DATA];
uint64_t tai_stamped = r[TAI_IN_MAC_DOMAIN];  // CDC'd TAI value

// Store packet with timestamp
uint64_t packet = (data_in << 64) | tai_stamped;
r[PACKET_WITH_TIMESTAMP] = packet;
```

**Why this works:**
- NIC reads TAI_IN_MAC_DOMAIN (already CDC'd; safe to use in MAC domain)
- Timestamp is CDC'd TAI value from previous cycle (registered snapshot)
- No metastability; no combining clock domains

## No Discipline (Deterministic Model)

**NOT in this model:**
```c
// ❌ NOT implemented
uint64_t pps_input;  // No external PPS
uint64_t pll_error = pps_input - (tai % 1000000000);  // No feedback
uint64_t tai_disciplined = tai + pll_correction;  // No PI loop
```

**Why not:** For determinism, the model must be fully specified at compile time. PLL discipline adds runtime feedback (PPS sync), which makes reproducibility harder.

**Future:** If oscillator drift must be modeled, we'd add a controlled oscillator with known drift rates (not runtime feedback).

## Verifying TAI Compliance

Before graduation:

1. **Check taiosc is plain counter**
   ```sh
   jq '.nodes[] | select(.name | contains("taiosc"))' taiosc.net.json
   # Should show only simple increment (cell_addsub with +1)
   ```

2. **Check tai_cdc uses gray code**
   ```sh
   jq '.nodes[] | select(.name | contains("gray"))' tai_cdc.net.json
   # Should show gray_encode and gray_decode
   ```

3. **Verify no PPS or PI loop in registe**
   ```sh
   grep -r "pps\|pi_\|pll_\|feedback" taiosc.net.json tai.net.json tai_cdc.net.json
   # Should return nothing
   ```

4. **Confirm NIC reads TAI_IN_MAC_DOMAIN (not raw TAI)**
   ```sh
   jq '.cross_module_inputs[]' nic.net.json | grep -i tai
   # Should show TAI_IN_MAC_DOMAIN, not TAI
   ```

## Common TAI Mistakes

| Mistake | Fix |
|---------|-----|
| TAI = MAC counter | TAI is separate oscillator; use gray-code CDC |
| No CDC synchronization | Add tai_cdc gray-code module to bring TAI into MAC |
| PLL discipline in netlist | Deterministic model has no feedback; keep TAI free-running |
| Assuming NIC has direct TAI access | NIC reads CDC'd TAI in its domain (TAI_IN_MAC_DOMAIN) |
| Timestamp without CDC | Always synchronize TAI before using in other domains |

## Pre-graduation Checklist

- [ ] taiosc is a plain counter with no feedback
- [ ] tai_cdc uses gray-code synchronization (2-FF CDC)
- [ ] No PPS or PLL discipline in the netlist
- [ ] NIC reads TAI_IN_MAC_DOMAIN (CDC'd value)
- [ ] All cross-domain TAI usage goes through CDC module

## References

- FOUNDER_VISION.md §5 — The Clock, TAI ≠ MAC, No Clock Discipline
- CLAUDE.md — Project Notes (TAI)
- `.hft_staging/taiosc/` — Reference oscillator module
- `.hft_staging/tai/` — Reference TAI counter module
- `.hft_staging/tai_cdc/` — Reference CDC module
