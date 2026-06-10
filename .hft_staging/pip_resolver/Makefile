# PIP_RESOLVER device — the per-symbol pip-resolution lookup. Real build, owned in
# this tree. NO poc/ ref.
# Flow: emitter --> netlist --validate--> (gate) --gennet--> device C --cc--> thin test.
# The netlist validator is the project gate (single-writer/no-overlap/no-floating).

CC      = cc
CFLAGS  = -std=c11 -Wall -Wextra -Werror -O2
PY      = python3

EMIT    = gen_pip_resolver_net.py
NET     = pip_resolver.net.json
GEN     = pip_resolver_gen.h

# --- the sibling seam the PIP_RESOLVER SAMPLES. It reads the NIC seam's
# SEAM_SYMBOL/SEAM_VALID lanes. There is NO hand-maintained copy of the NIC map:
# regenerate the NIC's CANONICAL header from its single source via the NIC's own
# gennet. Gitignored (generated, never committed copy). ------------------------
NIC_DIR = ../nic
NIC_NET = $(NIC_DIR)/nic.net.json
NIC_GEN = nic_gen.h

# --- the NIC in turn samples the wire bus + tai_cdc; its gennet emits a header
# that #includes wire_gen.h + tai_cdc_gen.h. Regenerate those sibling-of-sibling
# headers from their single sources too (gitignored copies). -------------------
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

$(NIC_GEN): $(NIC_NET) $(NIC_DIR)/gennet.py $(WIRE_GEN) $(TAI_CDC_GEN)
	$(PY) $(NIC_DIR)/gennet.py $(NIC_NET) > $(NIC_GEN)

# --- generate the device C from the netlist (after the gate passes) -----------
gen: validate $(NIC_GEN)
	$(PY) gennet.py $(NET) > $(GEN)

# --- thin test: builds device + starter + display -----------------------------
test: gen
	$(CC) $(CFLAGS) -o test_synth test_synth.c pip_resolver.c display.c
	@echo "--- running pip_resolver thin test ---"
	./test_synth

probe: test
	@echo "--- probe: pip_resolver register snapshot ---"
	./test_synth

clean:
	rm -f $(GEN) $(NIC_GEN) $(WIRE_GEN) $(TAI_CDC_GEN) test_synth probe
