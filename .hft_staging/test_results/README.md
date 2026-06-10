# Test Results — ingress front (current)

Per-component gate + behavior results. The project gate (`.hft_staging/gate.sh`): netlist validator +
`-Werror` build + **2b** (gate-level arithmetic) + **2c** (generated, not hand-written) + clean-room
build from committed HEAD. Own `*_gen.h` is committed + graduated; the netlist is its validation spec.

| Component | Vault | Role |
|---|---|---|
| adapter  | ✅ | source; timestamp-paced; SPEED; deposits price-only packet to the wire bus |
| wire     | ✅ | passive addressed-memory bus; single writer = adapter, reader = NIC |
| taiosc   | ✅ | authoritative TAI oscillator reference (free-running; no discipline) |
| tai      | ✅ | plain counter off taiosc = the TAI time value (no PI, no PPS) |
| mac      | ✅ | NIC sample/copy-rate clock (125 MHz) |
| internal | ✅ | pipeline/DOM sample clock (250 MHz) |
| tai_cdc  | ✅ | gray-code 2-FF CDC of tai's value into the MAC domain (TAI_MAC) |
| nic      | ✅ | samples wire at mac rate, dedup by seq, stamps tai_cdc's TAI_MAC, 1-cycle strobe to seam |
| fifo_rx  | ✅ | MAC→internal async CDC FIFO (Cummings), 512-slot packet-wide, dual gray-code 2-FF sync |

**Verified:** the full `adapter → wire → nic → fifo_rx` ingress chain, e2e (CDC-safe across MAC↔internal).

**Deleted permanently:** `pps_mac` (wrong-design, pre-`taiosc`) — superseded by `taiosc`+`tai`; no
discipline in the canonical model. `nic` was *rebuilt* fresh against the clock set (not deleted).

**Next:** `dom` (price-indexed depth-of-market tables; input from `fifo_rx`).
