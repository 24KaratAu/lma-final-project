"""The agent's tools over one lease and the statute graph (PLAN.md section 5, Phase 2).

get_clause(clause_id)    another clause of the lease, by id or by the deed's own number
lookup_definition(term)  the lease's definition of a defined term
search_graph(query)      statute provisions by BM25, each section followed by its exceptions and explanations
expand(node_id)          what a statute node or lease clause links to, one hop

Each call is logged and everything it returns is kept as evidence for the verifier.
Observations shown to the controller are cut to `obs_chars`; the verifier gets full text.
"""

import re
from functools import lru_cache
from pathlib import Path

from src.common.jsonl import read_jsonl
from src.common.schemas import Lease, StatuteEdge, StatuteNode, ToolCall
from src.retrieval.flat import FlatIndex

STATUTE_DIR = Path(__file__).resolve().parents[2] / "data/statute"
PROVISION_TYPES = ("section", "exception", "explanation")


@lru_cache(maxsize=None)
def load_statute(folder: str = str(STATUTE_DIR)) -> tuple[tuple[StatuteNode, ...], tuple[StatuteEdge, ...]]:
    return tuple(read_jsonl(Path(folder) / "nodes.jsonl", StatuteNode)), tuple(read_jsonl(Path(folder) / "edges.jsonl", StatuteEdge))


_indexes: dict[tuple[str, ...], FlatIndex] = {}


def _index(nodes) -> FlatIndex:
    """BM25 over the provisions, built once per statute (nodes are not hashable, so key on their ids)."""
    provisions = [n for n in nodes if n.type in PROVISION_TYPES]
    key = tuple(n.id for n in provisions)
    if key not in _indexes:
        _indexes[key] = FlatIndex.bm25(provisions)
    return _indexes[key]


class Toolbox:
    NAMES = ("get_clause", "lookup_definition", "search_graph", "expand")

    def __init__(self, lease: Lease, nodes, edges, k: int = 5, obs_chars: int = 600):
        self.lease, self.k, self.obs_chars = lease, k, obs_chars
        self.nodes = {n.id: n for n in nodes}
        self.edges = list(edges)
        self.index = _index(nodes)
        self.clauses = {c.clause_id: c for c in lease.clauses}
        self.by_number = {c.number.lower(): c for c in lease.clauses if c.number}
        self.calls: list[ToolCall] = []
        self.evidence: dict[str, str] = {}  # id -> full text, in the order found

    # Lease side

    def clause(self, ref: str):
        ref = str(ref).strip()
        if ref in self.clauses:
            return self.clauses[ref]
        if f"{self.lease.lease_id}-{ref}" in self.clauses:
            return self.clauses[f"{self.lease.lease_id}-{ref}"]
        return self.by_number.get(ref.lower().removeprefix("clause ").removeprefix("cl. ").strip())

    def links(self, clause_id: str) -> list[dict]:
        """The lease's own uses_term / refers_to edges out of a clause."""
        return [{"type": r.type, "clause_id": r.dst} for r in self.lease.refs if r.src == clause_id]

    def get_clause(self, clause_id: str) -> dict:
        c = self.clause(clause_id)
        if c is None:
            return {"error": f"no clause {clause_id!r} in lease {self.lease.lease_id}"}
        self._keep(c.clause_id, f"Lease clause {c.number} {c.heading}".strip() + f": {c.text}")
        return {"clause_id": c.clause_id, "number": c.number, "heading": c.heading, "text": self._cut(c.text), "links": self.links(c.clause_id)}

    def lookup_definition(self, term: str) -> dict:
        t = str(term).strip().strip("\"'“”").lower()
        found = [d for d in self.lease.definitions if d.term.lower() == t] or [
            d for d in self.lease.definitions if t and (t in d.term.lower() or f"“{t}”" in d.text.lower() or f'"{t}"' in d.text.lower())
        ]
        if not found:
            return self._defined_inline(str(term).strip().strip("\"'“”"))
        for d in found:
            self._keep(d.clause_id, f"Definition of {d.term} (clause {self.clauses[d.clause_id].number or d.clause_id}): {d.text}")
        return {"definitions": [{"term": d.term, "clause_id": d.clause_id, "text": self._cut(d.text)} for d in found[:3]]}

    def _defined_inline(self, term: str) -> dict:
        """A term the parser did not list, defined inside a clause: (hereinafter called the "X"), is referred to as the "X"."""
        pattern = re.compile(r"[“\"]" + re.escape(term) + r"[”\"]", re.I)
        defining = re.compile(r"\b(means?|meaning|referred to|called|defined)\b", re.I)
        hits = []
        for c in self.lease.clauses:
            for m in pattern.finditer(c.text):
                around = c.text[max(0, m.start() - 200) : m.end() + 200]
                hits.append((not defining.search(around), c, around))
                break
        if not hits:
            return {"error": f"no definition of {term!r} in lease {self.lease.lease_id}"}
        _, c, around = min(hits, key=lambda h: h[0])  # a clause that defines the term, else the first that quotes it
        self._keep(c.clause_id, f"Lease clause {c.number} {c.heading}".strip() + f": {c.text}")
        return {"definitions": [{"term": term, "clause_id": c.clause_id, "text": "..." + around + "..."}]}

    # Statute side

    def neighbours(self, node_id: str) -> list[str]:
        """Exceptions and explanations of a section; the section an exception or explanation belongs to."""
        out = [e.src for e in self.edges if e.dst == node_id and e.type in ("exception_to", "explains")]
        out += [e.dst for e in self.edges if e.src == node_id and e.type in ("exception_to", "explains", "refers_to", "interprets")]
        return [n for n in out if n in self.nodes]

    def search_graph(self, query: str, k: int | None = None) -> dict:
        seeds = self.index.search(str(query), k or self.k)
        ranked = []
        for n in seeds:
            for nid in [n.id] + self.neighbours(n.id):
                if nid not in ranked:
                    ranked.append(nid)
        for nid in ranked:
            self._keep(nid, f"{self.nodes[nid].label}: {self.nodes[nid].text}")
        return {"nodes": [self._show(nid) for nid in ranked]}

    def expand(self, node_id: str) -> dict:
        node_id = str(node_id).strip()
        if node_id in self.nodes:
            for nid in self.neighbours(node_id):
                self._keep(nid, f"{self.nodes[nid].label}: {self.nodes[nid].text}")
            return {"node": node_id, "neighbours": [self._show(nid) for nid in self.neighbours(node_id)]}
        c = self.clause(node_id)
        if c is None:
            return {"error": f"no statute node or lease clause {node_id!r}"}
        out = []
        for link in self.links(c.clause_id):
            got = self.get_clause(link["clause_id"])
            out.append({"type": link["type"]} | {k: got[k] for k in ("clause_id", "number", "text") if k in got})
        return {"clause_id": c.clause_id, "neighbours": out}

    # Calls, evidence

    def call(self, tool: str, args: dict) -> dict:
        args = args if isinstance(args, dict) else {}
        self.calls.append(ToolCall(tool=tool, args=args))
        if tool not in self.NAMES:
            return {"error": f"unknown tool {tool!r}; use one of {', '.join(self.NAMES)} or verify"}
        try:
            return getattr(self, tool)(**args)
        except TypeError as e:
            return {"error": f"bad arguments for {tool}: {e}"}

    def evidence_nodes(self) -> list[dict]:
        return [{"id": i, "text": t} for i, t in self.evidence.items()]

    def path(self) -> list[str]:
        """Statute nodes first, in the order found, then lease clauses (the scorer reads recall@k off the front)."""
        ids = list(self.evidence)
        return [i for i in ids if i in self.nodes] + [i for i in ids if i not in self.nodes]

    def _keep(self, nid: str, text: str) -> None:
        self.evidence.setdefault(nid, text)

    def _show(self, nid: str) -> dict:
        n = self.nodes[nid]
        return {"id": nid, "label": n.label, "text": self._cut(n.text)}

    def _cut(self, text: str) -> str:
        return text if len(text) <= self.obs_chars else text[: self.obs_chars] + " ..."
