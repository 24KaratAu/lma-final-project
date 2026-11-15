"""retrieve(clause_id, lease, mode, k) -> {"nodes", "path"} (PLAN.md section 4).

mode "flat": top-k statute provisions by BM25 against the clause text (best flat retriever on dev).
mode "dense": top-k statute provisions by embedding similarity (BGE-small), for comparison.
mode "graph": the lease's own links plus seed, expand and rerank over the statute graph (src/retrieval/graph.py).
"""

from src.common.schemas import Lease
from src.retrieval.flat import FlatIndex, bm25_index, dense_index
from src.retrieval.graph import graph_retrieve


def retrieve(clause_id: str, lease: Lease, mode: str = "flat", k: int = 5) -> dict:
    clause = next(c for c in lease.clauses if c.clause_id == clause_id)
    if mode == "none":
        return {"nodes": [], "path": []}
    if mode == "graph":
        return graph_retrieve(clause_id, lease, k=k)
    if mode == "flat":
        index = bm25_index()
    elif mode == "dense":
        index = dense_index()
    else:
        raise ValueError(f"unknown retrieval mode {mode!r}")
    nodes = index.search(clause.text, k)
    return {"nodes": [n.model_dump() for n in nodes], "path": [n.id for n in nodes]}


__all__ = ["FlatIndex", "retrieve"]
