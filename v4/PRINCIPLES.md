# V4 Clean Room — Non-Negotiable Principles

These principles are enforced by a gate, not by trust. Violations cause the gate to fail with exit 1.

## 1. Structure, don't search
No tool may look for, identify, or guess an entity. Entities are produced by relational operations over already-labelled rows.

## 2. Join, don't find
Ownership (which primitive owns this table) is a JOIN on (doc,page), never a text search. A row that doesn't join goes to a visible residual — NEVER a fabricated name.

## 3. Conservation = completeness
Every unit (page, table, row) is either placed or in the residual. `total == placed + residual`, asserted in code, exit 1 on imbalance.

## 4. Cite everything
No value enters the catalog without a (doc,page) citation.

## 5. Gate before build
The catalog gate is built and passing FIRST; the derivation must pass it or it is not done.

## 6. AI/human last
Tools are deterministic. Humans review the residual and adjudicate; they do not hand-fill data.
