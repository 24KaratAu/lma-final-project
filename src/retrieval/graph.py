"""Graph retrieval (PLAN.md section 14): seed, expand, rerank over the statute graph, plus the lease's own links.

Lease side: the clause's own `uses_term` / `refers_to` links (one hop; a second hop found nothing more on dev),
and two facts the lawyer's checklists ask for that no link points to (PLAN.md section 6):
  - a clause about disputes, courts or final decisions: the deed's arbitration clause elsewhere;
  - a clause tied to the end of the lease: the deed's term clause.

Statute side: BM25 seeds over the provisions (sections, exceptions, explanations), from the clause text. Each
seed is expanded one hop along `exception_to` and `explains` (both ways) and `refers_to`. A neighbour scores
`decay` times its seed's score, or its own score if higher.

Settings chosen on dev only (15 Nov, 60 items): 3 seeds, decay 1.0, clause text alone as the query. Exact
recall@5 0.75 (flat 0.27), section recall@5 0.75 (flat 0.78), exact@1 0.50 (flat 0.15), lease clauses of
the gold path found 0.75 (flat 0). Adding the lease text to the query made the seeds noisier (exact@5 0.68). The top k
provisions come first in the path, so section recall@k reads only statute nodes (src/eval/score.py). Then come
the rulings that interpret them (`interprets` edges, src/graph/rulings.py) and the lease clauses.

Rulings: of those on the top provisions, the ones whose holding best matches the clause (BM25 on the holding),
at most 3, and none that shares no word with it. Taking them in provision order instead gave every s.28 clause
the three jurisdiction cases. Dev, 15 Nov (61 items, 17 rulings), items given a ruling of their own kind
(s.27, jurisdiction, time limits, Exception 1): time limits 18/20 (in order: 0/20), court bars 17/20 (14/20),
restraint 7/20 (8/20; s.27 itself is in the top 5 for only 9 of them). Adding the provision's score made it
worse (28 against 42 in all); 1 or 2 rulings found fewer of the right kind (31, 39). After the lawyer's
corrections to the holdings (15 Nov, Nos. 5, 15 and 18; docs/legal/rulings_review.md), the same check gives
18, 17 and 6 (41); provisions and lease clauses are unchanged on every dev and test item.

Lease clauses go into the evidence cut to their first 1,500 characters, the same cut the agent makes before
verify (src/agent/controller.py, `_evidence`). Uncut, a long term clause ran the 7B model out of memory on a
T4: B1-graph on test, 15 Nov, stopped in L07, whose term is in its 19,082-character preamble (prompts of
27-29k characters; the longest that had run was 17.8k). The path is unchanged, so retrieval-v1's figures stand.
"""

import re
from functools import lru_cache
from pathlib import Path

from src.common.jsonl import read_jsonl
from src.common.schemas import Clause, Lease, StatuteEdge, StatuteNode
from src.retrieval.flat import STATUTE, FlatIndex, bm25_index

EDGES = STATUTE.parent / "edges.jsonl"
DISPUTE = re.compile(r"\b(courts?|suits?|disputes?|differences?|arbitrat\w*|tribunals?|jurisdiction|final|binding|conclusive|questioned)\b", re.I)
ARBITRATION = re.compile(r"\barbitrat\w*", re.I)
LEASE_END = re.compile(
    r"\b(after|expiry|expiration|termination|determination|end)\s+of\s+(the|this)\s+(said\s+)?(lease|term|deed|tenancy|lease period)\b"
    r"|\block-?\s?in\b|\bduring the (term|lease|currency)\b", re.I)
TERM_CLAUSE = re.compile(r"\b(lease|term|tenancy|deed)\b[^.]{0,60}\bfor a (period|term) of\b|\bperiod of (the )?lease\b", re.I)
LEASE_CHARS = 1500  # characters of each lease clause passed on, as in src/agent/controller.py


@lru_cache(maxsize=None)
def statute(nodes_path: str = str(STATUTE), edges_path: str = str(EDGES)) -> tuple[dict, tuple]:
    nodes = {n.id: n for n in read_jsonl(nodes_path, StatuteNode)}
    return nodes, tuple(read_jsonl(edges_path, StatuteEdge))


def neighbours(node_id: str, edges) -> list[str]:
    """Exceptions and explanations of a section, the section of an exception, and sections it refers to."""
    out = [e.src for e in edges if e.dst == node_id and e.type in ("exception_to", "explains")]
    out += [e.dst for e in edges if e.src == node_id and e.type in ("exception_to", "explains", "refers_to")]
    return out


def rulings_of(node_id: str, edges) -> list[str]:
    return [e.src for e in edges if e.dst == node_id and e.type == "interprets"]


def pick_rulings(text: str, provisions: list[str], nodes: dict, edges, m: int) -> list[str]:
    """Rulings on the provisions, best BM25 match of the holding to the text first (ties: provision order)."""
    cand = list(dict.fromkeys(r for p in provisions for r in rulings_of(p, edges) if r in nodes))
    if not cand:
        return []
    held = [n.model_copy(update={"label": ""}) for n in nodes.values() if n.type == "ruling"]  # case names off
    score = dict(zip((n.id for n in held), FlatIndex.bm25(held).score(text)))
    return [r for r in sorted(cand, key=lambda r: -score[r]) if score[r] > 0][:m]


def _first(clauses: list[Clause], pattern: re.Pattern, skip: str) -> Clause | None:
    """The clause matching the pattern most often (ties: the earliest), other than `skip`."""
    hits = [(len(pattern.findall(c.text)), -i, c) for i, c in enumerate(clauses) if c.clause_id != skip]
    best = max(hits, key=lambda h: h[:2], default=(0, 0, None))
    return best[2] if best[0] else None


def lease_evidence(clause: Clause, lease: Lease) -> list[Clause]:
    by_id = {c.clause_id: c for c in lease.clauses}
    found = [r.dst for r in lease.refs if r.src == clause.clause_id]
    if DISPUTE.search(clause.text):
        arb = _first(lease.clauses, ARBITRATION, clause.clause_id)
        found += [arb.clause_id] if arb else []
    if LEASE_END.search(clause.text):
        term = next((c for c in lease.clauses if c.clause_id != clause.clause_id and TERM_CLAUSE.search(c.text)), None)
        found += [term.clause_id] if term else []
    seen, out = {clause.clause_id}, []
    for cid in found:
        if cid in by_id and cid not in seen:
            seen.add(cid)
            out.append(by_id[cid])
    return out


def graph_retrieve(clause_id: str, lease: Lease, k: int = 5, seeds: int = 3, decay: float = 1.0,
                   expand_query: bool = False, max_rulings: int = 3) -> dict:
    clause = next(c for c in lease.clauses if c.clause_id == clause_id)
    evidence = lease_evidence(clause, lease)
    query = " ".join([clause.text] + [c.text for c in evidence]) if expand_query else clause.text
    index = bm25_index()
    raw = index.score(query)
    score = {n.id: s for n, s in zip(index.nodes, raw)}
    nodes, edges = statute()
    cand: dict[str, float] = {}
    for nid in sorted(score, key=lambda i: -score[i])[:seeds]:
        cand[nid] = max(cand.get(nid, float("-inf")), score[nid])
        for nb in neighbours(nid, edges):
            if nb in score:  # a provision, not an illustration
                cand[nb] = max(cand.get(nb, float("-inf")), score[nb], decay * score[nid])
    top = sorted(cand, key=lambda i: (-cand[i], i))[:k]
    rulings = pick_rulings(clause.text, top, nodes, edges, max_rulings)
    out_nodes = [nodes[i].model_dump() for i in top + rulings]
    out_nodes += [{"id": c.clause_id, "type": "lease_clause", "label": f"Lease clause {c.number} {c.heading}".strip(),
                   "text": c.text[:LEASE_CHARS]} for c in evidence]
    return {"nodes": out_nodes, "path": top + rulings + [c.clause_id for c in evidence]}
