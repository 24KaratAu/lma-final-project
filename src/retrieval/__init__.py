"""retrieve(clause_id, lease, mode, k) -> {"nodes", "path"} (PLAN.md section 4).

mode "flat": top-k statute provisions by BM25 against the clause text (best flat retriever on dev).
mode "dense": top-k statute provisions by embedding similarity (BGE-small), for comparison.
mode "graph": seed, expand and rerank over the statute graph (Phase 2, not built yet).
"""

from src.common.schemas import Lease
from src.retrieval.flat import FlatIndex, bm25_index, dense_index


def retrieve(clause_id: str, lease: Lease, mode: str = "flat", k: int = 5) -> dict:
    clause = next(c for c in lease.clauses if c.clause_id == clause_id)
    if mode == "none":
        return {"nodes": [], "path": []}
    if mode == "flat":
        index = bm25_index()
    elif mode == "dense":
        index = dense_index()
    else:
        raise NotImplementedError(f"retrieval mode {mode!r} lands in Phase 2")
    nodes = index.search(clause.text, k)
    return {"nodes": [n.model_dump() for n in nodes], "path": [n.id for n in nodes]}


__all__ = ["FlatIndex", "retrieve"]
