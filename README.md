# Statute-grounded enforceability checking for Indian commercial leases

Team ClosedAI, LMA Group Project 2026. The plan, owners and schedule are in [`plans_and_docs/PLAN.md`](plans_and_docs/PLAN.md).

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

## Layout

| Path | What | Owner |
|---|---|---|
| `src/common/` | Shared contracts (`schemas.py`), file I/O, mocks. Changes need all four to agree | Everyone |
| `src/agent/`, `src/eval/` | Agent, fixed pipeline, evaluation harness | Avnish |
| `src/graph/`, `src/retrieval/`, `src/baselines/` | Statute graph, retrieval, frontier baseline | Saksham |
| `src/models/`, `src/train/`, `kaggle/`, `slurm/` | `generate()`, `verify()`, fine-tuning, compute | Amitabh |
| `data/`, `docs/legal/` | Leases, dev and test sets, rulings | Prabhav |
| `tests/fixtures/` | Tiny hand-written set to build against (not data) | Avnish |

## Rules

Work on a branch (`data/`, `graph/`, `model/`, `agent/`, `eval/` + topic), open a PR, get one approval. `main` is protected and the `test` check must pass.
