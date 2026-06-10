# candle device — indicator component. Real build, owned in this tree.
# Flow: emitter --> netlist --validate--> (gate) --gennet--> device C --cc--> thin test.

CC      = cc
CFLAGS  = -std=c11 -Wall -Wextra -Werror -O2
PY      = python3

EMIT    = gen_candle_net.py
NET     = candle.net.json
GEN     = candle_gen.h

.PHONY: all emit validate gen test probe clean

all: test

# --- emit the netlist from the emitter (the python deliverable) ---------------
emit: $(EMIT)
	$(PY) $(EMIT) > $(NET)

$(NET): $(EMIT)
	$(PY) $(EMIT) > $(NET)

# --- project gate: the netlist validator --------------------------------------
validate: $(NET)
	$(PY) validate.py $(NET)

# --- generate THIS device's C from its netlist (after the gate passes) ---
gen: validate
	$(PY) gennet.py $(NET) > $(GEN)

# --- thin test: builds device + starter + display ---
test: gen
	@echo "--- candle indicator thin test ---"
	@echo "(test scaffold not yet implemented)"

probe: test
	@echo "--- probe: candle register snapshot ---"

# clean removes compiled artifacts (keeps *_gen.h which is committed)
clean:
	rm -f test_synth probe
