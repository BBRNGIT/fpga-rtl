---
name: CDC/SLR Seam
description: NIC-to-pipeline boundary is a real clock domain crossing — model explicitly with gray-code and async FIFO
type: architecture
source: FOUNDER_VISION.md §6, CLAUDE.md
---

# CDC/SLR Seam

**Core Rule:** The boundary between NIC (MAC 125 MHz) and Pipeline (250 MHz) is a real **clock domain crossing**. Model it explicitly using:
- **Gray-code synchronizers** for control signals (1-2 bits)
- **Async FIFO** for data packets

This is true even if NIC and Pipeline logic sit on the same physical FPGA. The clock domains are independent; CDC logic is required.

## The Hardware Boundary

```
┌──────────────────────────────────┐  ┌──────────────────────────────────┐
│         NIC FPGA                 │  │      Pipeline FPGA               │
│       (125 MHz MAC)              │  │      (250 MHz internal)          │
│                                  │  │                                  │
│  Adapter → Wire → NIC/MAC        │  │  FIFO → DOM → Candle → ...      │
│            (samples on edge)      │  │                                  │
│                                  │  │                                  │
│  Output:                         │  │  Input:                          │
│  - [PACKET_VALID]               │  │  - [FIFO_READ_VALID]            │
│  - [PACKET_DATA]    ─────→ CDC ──→  - [FIFO_READ_DATA]              │
│  - [WRITE_PTR_GRAY] ─────→ FIFO ──→ - [WRITE_PTR_GRAY_SYNCED]       │
│                                  │  │                                  │
└──────────────────────────────────┘  └──────────────────────────────────┘
           MAC Domain                           Pipeline Domain
```

**The CDC/SLR seam is the FIFO and gray-code synchronizers.**

## Why CDC Is Required

Without CDC logic, crossing clock domains causes **metastability**:

```
NIC writes: [PACKET_DATA] = new_packet
Pipeline reads: data = [PACKET_DATA]

If the write and read happen near the clock boundary, the flip-flop
input may be transitioning, causing the output to be indeterminate.
```

**Solution:** Synchronize the crossing using flip-flops (CDC synchronizers).

## Gray-Code Synchronizer (for pointers)

FIFO read and write pointers cross domains. Gray code ensures **at most one bit changes** per cycle, so a half-synchronized pointer is still valid.

```
Write domain (MAC):
  [WRITE_PTR] → XOR tree → [WRITE_PTR_GRAY]
               (bin2gray)

Synchronizer (2 FF stages):
  [WRITE_PTR_GRAY] → FF1 → FF2 → [WRITE_PTR_GRAY_SYNCED]
  (metastable)      (stable in read domain by FF2)

Read domain (Pipeline):
  [WRITE_PTR_GRAY_SYNCED] → XOR tree → [WRITE_PTR_BINARY]
                           (gray2bin)
```

**In netlist (tai_cdc style):**
```json
{
  "registers": [
    {"name": "WRITE_PTR_GRAY", "dff": true},
    {"name": "WRITE_PTR_GRAY_FF1", "dff": true},
    {"name": "WRITE_PTR_GRAY_FF2", "dff": true}
  ],
  "comb_nodes": [
    {
      "name": "binary_to_gray",
      "reads": ["WRITE_PTR"],
      "writes": ["WRITE_PTR_GRAY"],
      "logic": {"type": "gray_encode"}
    },
    {
      "name": "gray_to_binary",
      "reads": ["WRITE_PTR_GRAY_FF2"],
      "writes": ["WRITE_PTR_BINARY_SYNCED"],
      "logic": {"type": "gray_decode"}
    }
  ]
}
```

## Async FIFO (for data packets)

FIFO decouples write rate (MAC) from read rate (Pipeline):

```
Write Side (MAC Domain)
  [PACKET_IN] → FIFO Memory [512 entries] → Read Side (Pipeline)
  [WRITE_PTR] → Gray sync ────────────────→ [READ_PTR_GRAY_SYNCED]
                                            ↓
                             [FIFO_FULL] check
```

**FIFO registers:**
```json
{
  "registers": [
    {"name": "FIFO_WRITE_PTR_GRAY", "dff": true},
    {"name": "FIFO_WRITE_PTR_GRAY_FF1", "dff": true},
    {"name": "FIFO_WRITE_PTR_GRAY_FF2", "dff": true},
    {"name": "FIFO_READ_PTR_GRAY", "dff": true},
    {"name": "FIFO_READ_PTR_GRAY_FF1", "dff": true},
    {"name": "FIFO_READ_PTR_GRAY_FF2", "dff": true},
    {"name": "FIFO_DATA_0", "dff": true, "width": 512},
    {"name": "FIFO_DATA_1", "dff": true, "width": 512},
    ...
  ]
}
```

**Behavior:**
- MAC writes packets to FIFO[WRITE_PTR] on MAC edges
- Pipeline reads FIFO[READ_PTR] on pipeline edges
- Pointers are gray-coded for synchronization
- FULL/EMPTY flags use synced pointers

## NIC Module (write side)

```c
static inline void nic_tick(word_t *r) {
  // READ
  uint64_t packet_in = r[WIRE_PACKET];
  uint64_t write_ptr = r[FIFO_WRITE_PTR];
  uint64_t read_ptr_gray_synced = r[FIFO_READ_PTR_GRAY_SYNCED];
  uint64_t read_ptr_binary = gray_to_bin(read_ptr_gray_synced);
  
  // COMPUTE
  uint64_t next_write_ptr = write_ptr + 1;
  uint64_t write_ptr_gray = bin_to_gray(next_write_ptr);
  
  // Check FIFO not full
  uint64_t fifo_full = 0;
  cell_eqmask(next_write_ptr, read_ptr_binary, &fifo_full);
  
  uint64_t can_write = cell_not(fifo_full);
  
  // WRITE
  r[FIFO_WRITE_PTR] = next_write_ptr;
  r[FIFO_WRITE_PTR_GRAY] = write_ptr_gray;
  
  if (can_write) {
    r[FIFO_DATA[write_ptr]] = packet_in;
  }
}
```

## Pipeline Module (read side)

```c
static inline void fifo_rx_tick(word_t *r) {
  // READ
  uint64_t read_ptr = r[FIFO_READ_PTR];
  uint64_t write_ptr_gray_synced = r[FIFO_WRITE_PTR_GRAY_SYNCED];
  uint64_t write_ptr_binary = gray_to_bin(write_ptr_gray_synced);
  
  // COMPUTE
  uint64_t packet_out = r[FIFO_DATA[read_ptr]];
  
  // Check FIFO not empty
  uint64_t fifo_empty = 0;
  cell_eqmask(read_ptr, write_ptr_binary, &fifo_empty);
  
  uint64_t next_read_ptr = read_ptr + 1;
  uint64_t read_ptr_gray = bin_to_gray(next_read_ptr);
  
  // WRITE
  r[FIFO_READ_PTR] = next_read_ptr;
  r[FIFO_READ_PTR_GRAY] = read_ptr_gray;
  r[FIFO_OUTPUT] = packet_out;
  r[FIFO_VALID] = cell_not(fifo_empty);
}
```

## CDC Latency

Gray-code synchronizer adds latency:
- Cycle 0: MAC writes pointer
- Cycle 1-2: Synchronizer stages (FF1, FF2)
- Cycle 3: Pipeline reads synced pointer

**Expected pipeline FIFO_VALID latency: 2-3 cycles after packet write.**

## Verifying CDC/SLR Seam

Before graduation:

1. **Check gray-code sync exists**
   ```sh
   grep -r "gray_encode\|gray_decode\|FF1\|FF2" fifo_rx.net.json
   # Should show gray coding + 2-FF stages
   ```

2. **Verify pointers use gray code (not binary)**
   ```sh
   jq '.registers[] | select(.name | contains("PTR_GRAY"))' fifo_rx.net.json
   # Should exist for both read and write pointers
   ```

3. **Confirm FIFO memory is dual-ported**
   ```sh
   jq '.registers[] | select(.name | contains("FIFO_DATA"))' fifo_rx.net.json
   # Should show parallel read/write on different domains
   ```

4. **Check no cross-domain logic**
   ```sh
   grep -r "if.*WRITE.*READ\|READ.*WRITE" fifo_rx.c
   # Should return nothing (no direct domain crossing in logic)
   ```

## Common CDC Mistakes

| Mistake | Fix |
|---------|-----|
| No synchronizer on pointers | Add 2-FF gray-code sync between domains |
| Binary pointers without gray | Use gray encoding for CDC pointers |
| Single FF for sync | Use 2 FF stages minimum (metastability risk) |
| Async FIFO as simple buffer | Model dual-port memory with independent pointers |
| Assuming synchronized data stays valid | Latch synchronized output; don't rely on wire |

## References

- FOUNDER_VISION.md §6 — The Wire & Ingress Chain
- FOUNDER_VISION.md §5 — Clock Domain Crossings
- CLAUDE.md — Project Notes (NIC, CDC/SLR seam)
- `.hft_staging/fifo_rx/` — Reference async FIFO implementation
- `.hft_staging/tai_cdc/` — Reference gray-code synchronizer
