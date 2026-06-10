# Adapter device — real build, owned in this tree. NO poc/ reference anywhere.
# Flow: netlist --validate--> (gate) --gennet--> C --cc--> thin test.
# The netlist validator is the project gate (single-writer/no-overlap/no-floating).

CC      = cc
CFLAGS  = -std=c11 -Wall -Wextra -Werror -O2
PY      = python3

NET     = adapter.net.json
GEN     = adapter_gen.h

# --- the wire seam: the adapter DEPOSITS into the wire bus, so it depends on
# the wire's published lane map. There is no hand-maintained copy: we regenerate
# the wire's CANONICAL header from its single source (../wire/wire.net.json) via
# the wire's own gennet. Gitignored (generated, never committed). -------------
WIRE_DIR  = ../wire
WIRE_NET  = $(WIRE_DIR)/wire.net.json
WIRE_GEN  = wire_gen.h

.PHONY: all validate gen prep test probe xau clean

all: test

# --- project gate: the netlist validator -----------------------------------
validate: $(NET)
	$(PY) validate.py $(NET)

# --- generate the wire's canonical seam header from its single source -------
$(WIRE_GEN): $(WIRE_NET) $(WIRE_DIR)/gennet.py
	$(PY) $(WIRE_DIR)/gennet.py $(WIRE_NET) > $(WIRE_GEN)

# --- generate the device C from the netlist (after the gate passes) ---------
gen: validate $(WIRE_GEN)
	$(PY) gennet.py $(NET) > $(GEN)

# --- offline prep: synthetic CSV -> binary records (outside the system) -----
prep: prep.py data_synth.csv
	$(PY) prep.py data_synth.csv data_synth.bin

# --- thin test: builds device + buffer + display + starter ------------------
test: gen prep
	$(CC) $(CFLAGS) -o test_synth \
	    test_synth.c adapter.c buffer.c display.c
	@echo "--- running synthetic thin test ---"
	./test_synth

# --- external diagnostic: per-tick waveform (NOT the device, NOT a test) -----
# Logic-analyzer view: single-steps the device and prints registers each tick.
# Inspect any prepped dataset:  ./probe <file.bin> [speed] [max_ticks]
probe: gen prep
	$(CC) $(CFLAGS) -o probe probe.c buffer.c
	@echo "--- probe: per-tick waveform (synthetic, SPEED=1, 8-tick window) ---"
	./probe data_synth.bin 1 8

# --- real XAU data: prep the live file, run the same device -----------------
xau: gen
	$(PY) prep.py ../../XAU-USD_Tick_2026-04-24_12h_UTC.csv data_xau.bin
	$(CC) $(CFLAGS) -DRECORD_FILE='"data_xau.bin"' -o test_xau \
	    test_synth.c adapter.c buffer.c display.c

clean:
	rm -f $(GEN) $(WIRE_GEN) test_synth test_xau probe data_synth.bin data_xau.bin
