# candle device — indicator component. Real build, owned in this tree.
# Flow: logic.yaml --emit--> netlist --validate--> --gennet--> device C --cc--> thin test.
#
# The emitter is the GENERIC meta-tool ../gen_module_net.py, invoked via the thin
# wrapper gen_candle_net.py on candle_logic.yaml. The netlist and *_gen.h are TOOL
# OUTPUTS (never hand-edited); both are committed as the validation spec.

CC      = cc
CFLAGS  = -std=c11 -Wall -Wextra -Werror -O2
PY      = python3

EMIT    = gen_candle_net.py
LOGIC   = candle_logic.yaml
NET     = candle.net.json
GEN     = candle_gen.h

.PHONY: all emit validate gen selfcheck test probe clean

all: test

# --- emit the netlist from the logic yaml via the generic emitter -------------
emit: $(EMIT) $(LOGIC) ../gen_module_net.py
	$(PY) $(EMIT) > $(NET)

$(NET): $(EMIT) $(LOGIC) ../gen_module_net.py
	$(PY) $(EMIT) > $(NET)

# --- netlist validator --------------------------------------------------------
validate: $(NET)
	$(PY) validate.py $(NET)

# --- generate THIS device's C from its netlist (after validate) ---------------
gen: validate
	$(PY) gennet.py $(NET) > $(GEN)

# --- semantic self-check: netlist-driven OHLC reference simulator -------------
selfcheck: gen
	$(PY) simnet.py $(NET)

# --- thin test: builds device + powers on + displays --------------------------
test: gen
	$(CC) $(CFLAGS) -o test_candle test_candle.c
	./test_candle

probe: test
	@echo "--- probe: candle register snapshot ---"

clean:
	rm -f test_candle candle_selfcheck probe
