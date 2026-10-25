"""Stand-ins for generate, retrieve and verify (PLAN.md section 4).

They keep the agreed signatures and need no GPU, so every workstream can
run end to end before the real versions land. The real ones live in
src/models (generate, verify) and src/retrieval (retrieve).

The oracle mocks answer from gold labels. Use them only on fixtures and
the dev set, never to produce reported numbers.
"""

import json

from src.common.schemas import LabelledItem, Lease, StatuteNode


def mock_generate(prompts: list[str], model: str, **kw) -> list[str]:
    """The `mock` backend of generate(): one fixed JSON answer per prompt."""
    answer = json.dumps({"verdict": "handoff", "provision": None, "confidence": 0.0})
    return [answer for _ in prompts]


def make_oracle_retrieve(items: list[LabelledItem], nodes: list[StatuteNode]):
    """retrieve() that returns each item's gold path."""
    by_clause = {it.clause_id: it for it in items}
    by_id = {n.id: n for n in nodes}

    def retrieve(clause_id: str, lease: Lease, mode: str = "graph", k: int = 5) -> dict:
        item = by_clause.get(clause_id)
        path = list(item.gold_path) if item else []
        found = [by_id[p].model_dump() for p in path if p in by_id]
        return {"nodes": found[:k], "path": path}

    return retrieve


def make_oracle_verify(items: list[LabelledItem], leases: dict[str, Lease]):
    """verify() that returns each item's gold verdict and provision, matched on clause text."""
    gold = {}
    for it in items:
        clause = next(c for c in leases[it.lease_id].clauses if c.clause_id == it.clause_id)
        gold[clause.text] = it

    def verify(clause_text: str, evidence: dict, elements: dict) -> dict:
        item = gold.get(clause_text)
        if item is None:
            return {"verdict": "handoff", "provision": None, "confidence": 0.0}
        return {"verdict": item.gold_verdict, "provision": item.gold_provision, "confidence": 1.0}

    return verify
