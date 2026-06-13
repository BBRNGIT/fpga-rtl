# Interconnect fabric — built from primitives by the existing meta-tool

The blank had logic/memory/IO parts but NO interconnection network. These are the
routing parts (UltraScale model: INT tiles, switch boxes, connection boxes, PIPs,
wires), built from primitives via gen_module_net.py + gennet.py — no new tool.

- **pip** — Programmable Interconnect Point: a config flip-flop (set at bitstream
  time) + a gate switch. ON => passes its source wire to its dest wire; OFF => open.
  Same family as the LUT6 (config-dff + select). Config is operator/bitstream-set,
  never data-wired.
- **switch_box** — a WxW crossbar of PIPs (the INT-tile routing core). Each output
  wire = OR-reduce of the gated inputs; the router guarantees one driver per wire.
  PROVEN: routing IN_i -> OUT_j by enabling PIP(i,j); re-route by toggling the PIP.

Wires are CONDUCTORS (like the GTY lanes), not flip-flops. A connection_box is the
same crossbar between a functional tile's pins and routing wires (tile is born
lane-connected). An int_tile = switch_box + connection_boxes.

Next: array INT tiles into a new versioned blank (authentic count, like the CLB),
then the router meta-tool (system_map block diagram + fabric graph -> PIP config).
