# NIC device — the wire->fifo gateway. Real build, owned in this tree. NO poc/ ref.
# Flow: emitter --> netlist --validate--> (gate) --gennet--> device C --cc--> thin test.
# The netlist validator is the project gate (single-writer/no-overlap/no-floating).

CC      = cc
CFLAGS  = -std=c11 -Wall -Wextra -Werror -O2
PY      = python3

EMIT    = gen_nic_net.py
NET     = nic.net.json
GEN     = nic_gen.h

# --- sibling seams the NIC SAMPLES. The NIC reads the wire bus (WIRE_*) and
# tai_cdc's MAC-domain TAI value (TAI_MAC). There is NO hand-maintained copy of
# either map: regenerate each sibling's CANONICAL header from its single source
# via that sibling's own gennet. Gitignored (generated, never committed). --------
WIRE_DIR    = ../wire
WIRE_NET    = $(WIRE_DIR)/wire.net.json
WIRE_GEN    = wire_gen.h

TAI_CDC_DIR = ../tai_cdc
TAI_CDC_NET = $(TAI_CDC_DIR)/tai_cdc.net.json
TAI_CDC_GEN = tai_cdc_gen.h

.PHONY: all emit validate gen test probe clean

all: test

# --- emit the netlist from the emitter (the python deliverable) ---------------
emit: $(EMIT)
	$(PY) $(EMIT)

$(NET): $(EMIT)
	$(PY) $(EMIT)

# --- project gate: the netlist validator --------------------------------------
validate: $(NET)
	$(PY) validate.py $(NET)

# --- regenerate the sibling seam headers from their single sources ------------
$(WIRE_GEN): $(WIRE_NET) $(WIRE_DIR)/gennet.py
	$(PY) $(WIRE_DIR)/gennet.py $(WIRE_NET) > $(WIRE_GEN)

$(TAI_CDC_GEN): $(TAI_CDC_NET) $(TAI_CDC_DIR)/gennet.py
	$(PY) $(TAI_CDC_DIR)/gennet.py $(TAI_CDC_NET) > $(TAI_CDC_GEN)

# --- generate the device C from the netlist (after the gate passes) -----------
gen: validate $(WIRE_GEN) $(TAI_CDC_GEN)
	$(PY) gennet.py $(NET) > $(GEN)

# --- thin test: builds device + starter + display -----------------------------
test: gen
	$(CC) $(CFLAGS) -o test_synth test_synth.c nic.c display.c
	@echo "--- running nic thin test ---"
	./test_synth

probe: test
	@echo "--- probe: nic register snapshot ---"
	./test_synth

clean:
	rm -f $(GEN) $(WIRE_GEN) $(TAI_CDC_GEN) test_synth probe
