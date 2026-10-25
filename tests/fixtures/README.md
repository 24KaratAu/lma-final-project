# Fixtures

A tiny, hand-written set that follows the formats in `src/common/schemas.py` (PLAN.md section 4). Build and test against it until the real data lands.

| File | Contents |
|---|---|
| `statute/nodes.jsonl` | 8 nodes: Sections 27 and 28 of the Indian Contract Act, their exceptions, and 2 synthetic rulings |
| `statute/edges.jsonl` | `exception_to` edges and 2 `interprets` edges |
| `leases/L00.json` | 1 synthetic lease with 13 clauses, 2 definitions and 3 cross-references |
| `items.jsonl` | 10 items: void, valid and handoff for each of the three defect types, 2 in cross-clause form, and 1 out-of-scope item |

**Fixtures are not data.** The lease and rulings are made up, and the labels follow the draft rules in PLAN.md section 6 before lawyer sign-off. Never use them for training, tuning or reported numbers. The real statute graph comes from the parse of the India Code PDF.
