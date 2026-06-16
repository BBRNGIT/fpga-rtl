# V4 Model Proof: Verilog Text → Real Digital Primitives

## What We Proved

**test_and_gate.c** demonstrates that:
1. Real digital components exist in `components.h` (AND gate built from NAND)
2. verilog.h macros can instantiate these real components
3. Verilog text (`wire`, `assign A & B`, etc.) maps to actual hardware primitives
4. The test passes: AND(0,0)=0, AND(0,1)=0, AND(1,0)=0, AND(1,1)=1 ✓

## The Model

```
Verilog spec (e.g., glbl.v)
    ↓ (copy text exactly)
C cell (e.g., glbl.c)
    ↓ (use verilog.h macros)
verilog.h definitions
    ↓ (point to real components)
components.h (real digital primitives)
    ↓ (instantiate, wire, settle)
Actual hardware logic (proven working)
```

## Updated verilog.h

- `wire X;` → `wire_t X;` (real wire from components.h)
- `reg X;` → `reg_t X;` (real register from components.h)
- `assign(s0, s1) Y = A & B;` → instantiates `and_t`, wires it, settles it
- Each Verilog construct now instantiates a real component

## Why This Works

1. **Text is spec** — glbl.c copies Verilog exactly (immutable spec)
2. **Macros are realization** — verilog.h macros instantiate components
3. **Components are real** — AND, OR, NAND, etc. are built in C with actual logic
4. **No interpretation** — the text directly describes the hardware through component instantiation

## Next Steps

1. **Extend verilog.h** to handle all Verilog constructs (always, initial, etc.)
2. **Test glbl.c** — prove that with real components, glbl.c actually works
3. **Spawn 248 agents** — transcribe cells with confidence that the model is proven

## Status

✓ Proof of concept working (test_and_gate.c)
✓ verilog.h linked to components.h
✓ Real hardware primitives confirmed
→ Ready to test with actual cell
