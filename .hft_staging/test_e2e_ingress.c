/* test_e2e_ingress.c — END-TO-END CHAIN TEST
 *
 * Exercises the full ingress pipeline:
 *   adapter (source) → wire (passive bus) → nic (dedup + stamp) → fifo_rx (CDC FIFO)
 *
 * Demonstrates:
 * - Adapter generates market-data packets (bid/ask/symbol/pip/commission)
 * - Wire bus carries adapter's output as passive lanes (no logic)
 * - NIC samples wire, deduplicates by sequence, stamps with TAI_MAC from tai_cdc
 * - FIFO receives NIC's strobed seam packets, bridges MAC→internal clock domains
 * - Consumer can read head slot from internal domain
 *
 * Single-cycle strobes validate that packets flow end-to-end without stalling.
 */
#include <stdio.h>
#include <stdint.h>
#include <inttypes.h>

/* Stub includes (components linked via .hft/*/Makefile) */
extern void adapter_init(void);
extern void adapter_tick(void);
extern uint64_t adapter_read(uint64_t addr);

extern void wire_init(void);
extern void wire_tick(void);
extern uint64_t wire_read(uint64_t addr);

extern void nic_init(void);
extern void nic_tick(void);
extern uint64_t nic_read(uint64_t addr);

extern void tai_cdc_init(void);
extern void tai_cdc_tick(void);
extern uint64_t tai_cdc_read(uint64_t addr);

extern void fifo_rx_init(void);
extern void fifo_rx_tick(void);
extern uint64_t fifo_rx_read(uint64_t addr);

/* Address bases (per graduation) */
#define ADAPTER_BASE    0x1800000
#define WIRE_BASE       0x1700000
#define NIC_BASE        0x1A00000
#define TAI_CDC_BASE    0x1F00000
#define FIFO_RX_BASE    0x2000000

/* Register offsets (example; real values from backplane) */
#define WIRE_BID_OFF    0
#define WIRE_ASK_OFF    8
#define NIC_SEAM_STROBE 0x200
#define FIFO_HEAD_OFF   0x100

int main(void) {
    printf("=== END-TO-END INGRESS TEST ===\n");
    printf("Chain: adapter → wire → nic (dedup+stamp) → fifo_rx\n\n");

    /* Init all components */
    adapter_init();
    wire_init();
    nic_init();
    tai_cdc_init();
    fifo_rx_init();

    printf("--- Power-on: all components initialized ---\n");

    /* Run 10 cycles to allow clocks to self-run and data to propagate */
    for (int cycle = 0; cycle < 10; cycle++) {
        adapter_tick();
        wire_tick();
        nic_tick();
        tai_cdc_tick();
        fifo_rx_tick();
    }

    printf("\n--- After 10 cycles: check propagation ---\n");

    /* Read adapter output (what it deposited to wire) */
    uint64_t adapter_bid = adapter_read(ADAPTER_BASE + WIRE_BID_OFF);
    uint64_t adapter_ask = adapter_read(ADAPTER_BASE + WIRE_ASK_OFF);
    printf("ADAPTER output:\n");
    printf("  BID=%"PRIu64" ASK=%"PRIu64"\n", adapter_bid, adapter_ask);

    /* Read wire bus (passive copy of adapter output) */
    uint64_t wire_bid = wire_read(WIRE_BASE + WIRE_BID_OFF);
    uint64_t wire_ask = wire_read(WIRE_BASE + WIRE_ASK_OFF);
    printf("\nWIRE bus (passive relay):\n");
    printf("  BID=%"PRIu64" ASK=%"PRIu64"\n", wire_bid, wire_ask);
    printf("  [Expect: wire mirrors adapter] %s\n",
        (wire_bid == adapter_bid && wire_ask == adapter_ask) ? "✓ PASS" : "✗ FAIL");

    /* Read NIC seam (dedup'd, re-stamped packet) */
    uint64_t nic_strobe = nic_read(NIC_BASE + NIC_SEAM_STROBE);
    printf("\nNIC seam (re-stamped, dedup'd):\n");
    printf("  STROBE=%"PRIu64" (1=packet valid)\n", nic_strobe & 1);
    printf("  [Expect: strobe fires for unique packets] %s\n",
        (nic_strobe & 1) ? "✓ PASS" : "✗ FAIL");

    /* Read FIFO head (consumer view) */
    uint64_t fifo_head_bid = fifo_rx_read(FIFO_RX_BASE + FIFO_HEAD_OFF);
    printf("\nFIFO_RX head slot (internal domain, consumer view):\n");
    printf("  HEAD_BID=%"PRIu64" (should match NIC's output)\n", fifo_head_bid);
    printf("  [Expect: FIFO received packet across domain boundary] %s\n",
        (fifo_head_bid == adapter_bid) ? "✓ PASS" : "✗ FAIL");

    printf("\n=== END-TO-END TEST COMPLETE ===\n");
    return 0;
}
