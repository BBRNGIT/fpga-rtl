# Architecture Clarifications — User's Intent

## Canonical Source
**ARCHITECTURE.md is canonical.** All code must conform to it. Any contradiction = wrong.

---

## Clock Model: 5 Independent Oscillators

**§5a is correct and enforced.** All clocks are **truly independent**, not derived from one deterministic time base.

```
1. TAIOSC          (authoritative oscillator, GNSS-equivalent)
2. TAI             (plain counter off TAIOSC, timestamp source)
3. MAC             (NIC PHY clock, 125 MHz, independent reference)
4. INTERNAL        (Pipeline clock, 250 MHz, independent reference)
5. CPU             (host clock, independent reference)

[Optional: GPU clock, independent]
```

**Each oscillator has its own reference (real hardware ppm drift).** Simulator **must model independent clocks** (not slaved to one time base). CDC synchronizers exist **because they drift independently** — the synchronizers are the **proof the clocks are separate**.

**Any assumption that clocks are deterministic/synchronized without CDC = wrong.**

---

## Adapter: Data Repository, Not Passthrough

**Adapter holds external data (is the repository for external state).**

Model:
```
┌─────────────────────────────────┐
│ EXTERNAL WORLD                  │
│ (CSV file, broker stream, etc)  │
└────────────┬────────────────────┘
             │
      [reads from]
             │
             ▼
┌─────────────────────────────────┐
│ ADAPTER                         │
│ • Holds latest external data    │
│ • Cache of most recent packet   │
│ • (does NOT read + write in     │
│   same cycle; is a buffer)      │
└────────┬────────────────────────┘
         │
      [writes to]
         │
         ▼
┌─────────────────────────────────┐
│ WIRE (relay lanes)              │
│ • Passive, adapter's output     │
│ • Readable by NIC               │
└─────────────────────────────────┘
```

**Adapter is a register window, not a pipe:**
- External source writes new data → adapter registers
- Adapter holds the data (doesn't transform, doesn't pace)
- NIC reads from wire (adapter's output)
- On next adapter tick: if new external data arrived, update wire output

**Adapter does NOT:**
- Read external data and immediately write it (not a passthrough)
- Perform pacing or gating in the same cycle
- Act as a stream — it's a snapshot buffer

---

## Candle: Per-Module Bar Subscription

**Candle (and all bar modules) subscribe to bar-close signals.**

Model:
```
TIMEFRAME module outputs:
  ├─ TF_BASE_PERIOD_TICKS    (e.g., 250 = 1 second @ 250 MHz)
  └─ TF_BASE_CLOSED          (pulse, once per base period)

Each bar module declares its multiplier:
  CANDLE.multiplier = 2        (2× base period)
  FOOTPRINT.multiplier = 1     (1× base period)
  TPO.multiplier = 4           (4× base period)

Each module independently:
  if (internal_tick_count % (TF_BASE_PERIOD × multiplier)) == 0:
    close_bar()
```

**User-configurable:** If user wants a specific multiplier (2×, 0.5×, custom), the module reads it from its own register. **No assumptions.** Default = 1× per base period (one bar per base tick).

**Timeframe is a reference, not a master.** Modules subscribe to the base tick; each applies its own multiple.

---

## Display: Every Module Outputs Display Lanes

**Every module has a display output window.** No selectivity, no "only if important."

```
Every module publishes:
  MODULE_DISPLAY_*  (raw register lanes, non-blocking)
  
Example (DOM):
  ├─ DOM_DISPLAY_BEST_BID
  ├─ DOM_DISPLAY_BEST_ASK
  ├─ DOM_DISPLAY_BID_QTY
  ├─ DOM_DISPLAY_ASK_QTY
  ├─ DOM_DISPLAY_BAR_SEQ
  └─ ...

Example (CANDLE):
  ├─ CANDLE_DISPLAY_BID_OPEN
  ├─ CANDLE_DISPLAY_BID_HIGH
  ├─ CANDLE_DISPLAY_BID_LOW
  ├─ CANDLE_DISPLAY_BID_CLOSE
  ├─ CANDLE_DISPLAY_ASK_OPEN
  ├─ CANDLE_DISPLAY_ASK_HIGH
  ├─ CANDLE_DISPLAY_ASK_LOW
  ├─ CANDLE_DISPLAY_ASK_CLOSE
  ├─ CANDLE_DISPLAY_VOLUME_BID
  ├─ CANDLE_DISPLAY_VOLUME_ASK
  └─ ...
```

**Display lanes are:**
- Raw register reads (no reformat, no logic)
- Non-blocking (pipeline never waits for display)
- Async (GPU device reads at its own clock rate)
- Every module has them (not "optional nice-to-have")

**Nothing too crazy** = keep display output simple and direct, no computed derivatives.

---

## Backplane: Reconsider Later

Device hierarchy (§3: modules nested inside devices vs. flat) is **pending discussion.** Do not assume the current flat layout is final. Mark as "TBD" until founder/user confirms the device structure.

---

## Summary: Canonical Rules (No Assumptions)

1. ✓ **ARCHITECTURE.md is law**
2. ✓ **5 independent clock oscillators** (not one deterministic base)
3. ✓ **Adapter is a data repository** (not a passthrough pipe)
4. ✓ **Candle per-module bar subscription** (user configurable, default 1×)
5. ✓ **Every module outputs display lanes** (raw registers, non-blocking)
6. ⏳ **Backplane structure (device vs. flat) pending**

**Any contradiction to these rules = wrong code, must be fixed.**
