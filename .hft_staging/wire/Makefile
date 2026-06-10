# Wire BUS — a PASSIVE addressed-memory boundary (adapter -> NIC). Real build,
# owned in this tree. NO poc/ reference anywhere. The wire has NO clock, NO
# compute, NO logic, NO buffer, NO offline prep — it is just addressed storage
# the adapter deposits into and the NIC samples.
# Flow: netlist --validate--> (gate) --gennet--> address map --cc--> thin test.
# The netlist validator is the project gate (passive/no-overlap/addressed).

CC      = cc
CFLAGS  = -std=c11 -Wall -Wextra -Werror -O2
PY      = python3

NET     = wire.net.json
GEN     = wire_gen.h

.PHONY: all validate gen test probe clean

all: test

# --- project gate: the netlist validator (passive bus laws) -----------------
validate: $(NET)
	$(PY) validate.py $(NET)

# --- generate the bus address map from the netlist (after the gate passes) --
gen: validate
	$(PY) gennet.py $(NET) > $(GEN)

# --- thin test: builds the passive bus + display + starter ------------------
test: gen
	$(CC) $(CFLAGS) -o test_synth \
	    test_synth.c wire.c display.c
	@echo "--- running wire bus thin test ---"
	./test_synth

# --- external diagnostic: the bus snapshot (NOT the device, NOT a test) ------
probe: test
	@echo "--- probe: wire bus snapshot ---"
	./test_synth

clean:
	rm -f $(GEN) test_synth
