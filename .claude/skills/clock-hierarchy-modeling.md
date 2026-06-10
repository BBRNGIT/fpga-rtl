---
name: Clock Hierarchy Modeling
description: Model multiple independent clock domains — NIC (125 MHz), Pipeline (250 MHz), CPU, GPU — with explicit CDC
type: architecture
source: FOUNDER_VISION.md §5, CLAUDE.md
---

# Clock Hierarchy Modeling

**Core Rule:** The system has multiple independent clock domains. Each clock derives from a reference oscillator (or PLL). Clock domain crossings (CDC) are real hardware; model them explicitly with gray-code flip-flops and CDC FIFO logic.

## The Real Hardware

```
┌─────────────────────────────────────────────┐
│  Board Crystal (24 MHz reference)           │
└──────────┬──────────────────────────────────┘
           │
           ├─→ CPU PLL ──→ CPU Clock (e.g., 1 GHz)
           │
           ├─→ GPU Reference (100 MHz) ──→ GPU Clock (independent)
           │
           └─→ NIC PLL ──→ NIC MAC Clock (125 MHz) ──→ FIFO ──→ Pipeline Clock (250 MHz)
```

**Key:** Different clocks are driven by different PLLs or references. They are **independent oscillators**, not just frequency ratios.

## Our Deterministic Model

We derive all clocks from a **single simulation time base** (for reproducibility) while **explicitly modeling the CDC** (for realism):

```c
// Simulation time base (all clocks ultimately driven by this)
uint64_t sim_time = 0;

// Independent clock generators
uint64_t nic_mac_clock = sim_time % 8;        // 125 MHz (8-cycle repeat in 1 GHz sim)
uint64_t pipeline_clock = sim_time % 4;       // 250 MHz (4-cycle repeat)
uint64_t tai_clock = sim_time % 16;           // TAI oscillator

// Clock domain boundaries
// CDC FIFO bridges MAC→Pipeline
// Dual gray-code synchronizers for TAI→MAC crossing
```

**Result:** Reproducible (deterministic time base) + Realistic (independent domain modeling).

## Critical Rule: TAI ≠ MAC

**TAI is NOT the sample clock.**

- **MAC clock** = When the NIC reads the wire (125 MHz sample rate)
- **TAI** = The timestamp value itself (independent oscillator)
- **CDC** = Gray-code synchronizer brings TAI value into MAC domain at sample time

**WRONG (conflating them):**
```c
// ❌ BAD — TAI and MAC are not the same
uint64_t tai = mac_edge_counter;  // NO — TAI comes from separate oscillator
```

**RIGHT (separate clocks, CDC bridge):**
```c
// ✅ GOOD — TAI is free-running; MAC samples it
uint64_t tai = tai_osc_counter;   // TAI: free-running off taiosc
uint64_t tai_in_mac_domain = cdc_gray2_sync(tai, mac_clock);  // Bring into MAC domain via CDC
// On MAC edge: r[TIMESTAMP] = tai_in_mac_domain;
```

## Clock Domain Crossings (CDC)

Crossing from one clock domain to another requires **CDC logic** to avoid metastability:

### Gray Code Synchronizer (2-FF CDC)

For synchronizing a single bit or slow counter:

```c
// In gennet.py, for tai_cdc module:
uint64_t tai_gray = tai ^ (tai >> 1);  // Binary → Gray code
uint64_t tai_gray_ff1 = r[TAI_GRAY_FF1];
uint64_t tai_gray_ff2 = r[TAI_GRAY_FF2];

// COMPUTE: capture gray code through 2 FFs
uint64_t tai_gray_synced = tai_gray_ff2;
uint64_t tai_value = /* gray to binary decode */;

// WRITE: latch for next cycle
r[TAI_GRAY_FF1] = tai_gray;
r[TAI_GRAY_FF2] = tai_gray_ff1;
r[TAI_SYNCED] = tai_value;
```

**In the netlist:**
```json
{
  "registers": [
    {"name": "TAI_GRAY_FF1", "dff": true},
    {"name": "TAI_GRAY_FF2", "dff": true},
    {"name": "TAI_SYNCED", "dff": true}
  ],
  "comb_nodes": [
    {
      "name": "gray_to_binary",
      "reads": ["TAI_GRAY_FF2"],
      "writes": ["TAI_VALUE"],
      "logic": {"type": "gray_decode", ...}
    }
  ]
}
```

### Async FIFO (Packet CDC)

For crossing multi-bit data (e.g., packets from MAC to Pipeline):

**Structure:**
```
MAC Domain          CDC              Pipeline Domain
  ↓                 ↓                    ↓
Write Port ──→ Async FIFO ──→ Read Port
  r[MAC_WDATA]   Gray-code sync  r[PIPE_RDATA]
  r[MAC_WPTR]    Dual 2-FF       r[PIPE_RPTR]
  r[MAC_WRITE]   (separate)      r[PIPE_READ_VALID]
```

**FIFO registers in netlist:**
```json
{
  "registers": [
    {"name": "FIFO_WRITE_PTR_GRAY", "dff": true},
    {"name": "FIFO_WRITE_PTR_GRAY_FF1", "dff": true},
    {"name": "FIFO_WRITE_PTR_GRAY_FF2", "dff": true},
    {"name": "FIFO_READ_PTR_GRAY_GRAY", "dff": true},
    {"name": "FIFO_DATA[512]", "dff": true}
  ]
}
```

## Clock Discipline

**In the deterministic model:** No PLL discipline, no PPS (pulse-per-second), no PI (proportional-integral) loop.

```c
// ✅ GOOD — TAI is plain counter, no discipline
uint64_t tai = taiosc_counter;  // Free-running off taiosc
```

**In real hardware:** Add a PLL loop (future, if needed):
```c
// (Not implemented now; would require sim model of oscillator drift)
// uint64_t pll_disciplined_tai = tai + pll_correction;
```

## Multiple Time Bases in Netlist

The netlist declares all clock domains explicitly:

```json
{
  "clock_domains": [
    {
      "name": "mac",
      "frequency": 125000000,
      "reference": "board_crystal"
    },
    {
      "name": "pipeline",
      "frequency": 250000000,
      "reference": "internal_pll"
    },
    {
      "name": "tai",
      "frequency": "free_running",
      "reference": "taiosc"
    }
  ],
  "cdc": [
    {
      "from": "tai",
      "to": "mac",
      "type": "gray_code_2ff",
      "signal": "tai_counter"
    },
    {
      "from": "mac",
      "to": "pipeline",
      "type": "async_fifo",
      "width": 512
    }
  ]
}
```

## Verifying Clock Domains

Before graduation:

1. **List all clocks**
   ```sh
   jq '.clock_domains[].name' <module>.net.json
   ```

2. **Verify CDC modules exist**
   ```sh
   jq '.cdc[]' <module>.net.json
   ```

3. **Check TAI is NOT tied to MAC**
   ```sh
   jq '.nodes[] | select(.name | contains("tai")) | .logic' <module>.net.json
   # Should show taiosc-based logic, not mac_counter
   ```

## Common Clock Domain Mistakes

| Mistake | Fix |
|---------|-----|
| TAI = MAC edge counter | TAI is separate oscillator; use gray-code CDC to bring into MAC |
| No CDC between domains | Add gray synchronizer for single bits, FIFO for packets |
| Combinational path across domains | All cross-domain signals go through registered CDC |
| Assuming synchronous clocks | NIC and Pipeline are independent oscillators; model drift potential |
| No timestamp on samples | On every MAC edge, sample TAI and latch timestamp |

## References

- FOUNDER_VISION.md §5 — The Clock
- FOUNDER_VISION.md §5 — Critical: TAI ≠ MAC
- CLAUDE.md — Project Notes (TAI, Timeframe)
- `.hft_staging/tai_cdc/` — Reference CDC module
- `.hft_staging/fifo_rx/` — Reference async FIFO
