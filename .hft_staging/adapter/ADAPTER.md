# Adapter — block diagram (the source)

The adapter IS the source: it converts raw records into binary NIC packets and, on its own real-world
clock, writes them to the wire **paced by each record's source timestamp**. No feeder; the data exists
in the buffer; **the test handles nothing** (power on + display only — it may run ~1 min for real data).
**Every part is built from flip-flop / gate cells** — including the comparator.

```
ADP_POWER (bit) ──set once──► ADP_CLK : REAL-WORLD-TIME counter, free-running   [flip-flop counter]
                                  │  now = real-world time (advances 1 unit / tick)
                                  ▼
┌─ buffer  (flip-flops / gate cells) ──────────────────────────────────┐
│  records[] = data, loaded at once: { bid, ask, TS, seq }              │
│  presents records[POS] → RAW_BID, RAW_ASK, RX_TS, RX_SEQ             │
│  IN_RANGE = (POS < count)                                            │
└───────────────┬───────────────────────────────────────────────────────┘
                ▼
┌─ PACER  (a real sub-device, its own registers, flip-flop primitives) ─┐
│  DUE = (RX_TS ≤ ADP_CLK now) & IN_RANGE                               │
│        └── comparator built from gate primitives (and/or/xor/not),    │
│            NOT a high-level C compare                                 │
│  POS  += DUE                              [flip-flop counter]         │
└───────────────┬───────────────────────────────────────────────────────┘
                │ DUE (1 = this record's real-world time has arrived)
        ┌───────┴───────────────┐
        ▼                       ▼
  write-out (dffs, en=DUE)   WIRE_VALID <= DUE
  WIRE_BID/ASK <= RAW_*      (no spread — DOM computes it from bid/ask)
  WIRE_SYMBOL/PIP/COMM <= config
  WIRE_TIME <= RX_TS   WIRE_SEQ <= RX_SEQ
        │
        ▼
      WIRE = ingress NIC packet, emitted ONLY when DUE → at the record's real-world time
```

**Per real-world tick:** buffer presents `records[POS]`; the PACER computes `DUE = (RX_TS ≤ now) &
in_range`; if DUE → write-out latches the record to WIRE (`WIRE_VALID=1`) and POS consumes it (`+=1`);
if not DUE → no emit, POS holds, the clock keeps advancing until `now` reaches the record's TS. End
(`POS==count`) → power off.

**Effect:** delivery order/jitter is irrelevant — records leave at the real-world times their source
timestamps say, on the free-running real-world clock.

## Parts (all flip-flop / gate primitives)
- **clock** — `ADP_CLK`, real-world time, free-running (power bit). The only thing that "runs."
- **time** — `RX_TS` (source timestamp): the PACER's compare input and `WIRE_TIME`. The only external
  timestamp use in the whole system.
- **buffer** — holds records, presents `records[POS]`.
- **pacer** — sub-device: gate-level comparator (`DUE`) + POS counter. Decides when each record emits.
- **write-out** — gated dffs (`en=DUE`) → WIRE ingress packet.

## Build notes
- The **comparator is a netlist of gate cells** (generated, not hand-written) — `≤` from
  `and/or/xor/not`, no `__int128`, no high-level ops.
- The **test is thin and handles nothing**; a full-data run pacing at real-world time may take ~1 min.
- Offline `prep` extracts the real UTC time → numeric `TS` per record (outside the system).
