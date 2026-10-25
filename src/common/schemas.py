"""Shared data contracts (PLAN.md section 4).

Every workstream reads and writes these formats. Changing a field here
needs all four team members to agree (PLAN.md section 10).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

NodeType = Literal["section", "exception", "explanation", "illustration", "ruling"]
EdgeType = Literal["exception_to", "explains", "illustrates", "refers_to", "interprets"]
EdgeSource = Literal["parsed", "regex", "manual"]
RefType = Literal["uses_term", "refers_to"]
DefectType = Literal["restraint_trade", "bar_proceedings", "time_limit", "out_of_scope"]
Form = Literal["single", "cross"]
Verdict = Literal["void", "valid", "handoff"]

# Element checklists (PLAN.md section 6), pending lawyer sign-off.
# Each element maps to its allowed values, or None for free text.
PARTY = {"tenant", "landlord", "both"}
ELEMENTS: dict[str, dict[str, set[str] | None]] = {
    "restraint_trade": {
        "restrained_party": PARTY,
        "restrained_activity": {"trade_or_business", "premises_use"},
        "window": {"during_term", "after_term", "both"},
        "window_start_and_length": None,
        "goodwill_sale": {"yes", "no"},
    },
    "bar_proceedings": {
        "restricted_party": PARTY,
        "rights_covered": {"under_lease", "other"},
        "degree": {"absolute", "partial"},
        "alternative_forum": {"arbitration", "named_court", "none"},
        "named_court_competent": {"yes", "no", "cannot_tell"},
    },
    "time_limit": {
        "affected_party": PARTY,
        "what_is_limited": {"time_to_sue", "contractual_step"},
        "period_and_trigger": None,
        "effect_on_expiry": {"claim_barred", "right_extinguished", "none"},
        "bank_guarantee": {"yes", "no"},
    },
    "out_of_scope": {},
}


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


# Statute graph: data/statute/nodes.jsonl, edges.jsonl


class StatuteNode(Contract):
    id: str
    type: NodeType
    label: str
    text: str


class StatuteEdge(Contract):
    src: str
    dst: str
    type: EdgeType
    source: EdgeSource


# Lease: data/leases/<lease_id>.json


class Clause(Contract):
    clause_id: str
    number: str
    heading: str
    text: str


class Definition(Contract):
    term: str
    clause_id: str
    text: str


class LeaseRef(Contract):
    src: str
    dst: str
    type: RefType


class Lease(Contract):
    lease_id: str
    clauses: list[Clause]
    definitions: list[Definition] = []
    refs: list[LeaseRef] = []

    @model_validator(mode="after")
    def _check_ids(self):
        ids = [c.clause_id for c in self.clauses]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{self.lease_id}: duplicate clause_id")
        bad = [i for i in ids if not i.startswith(f"{self.lease_id}-")]
        if bad:
            raise ValueError(f"{self.lease_id}: clause_id must start with lease_id: {bad}")
        known = set(ids)
        for d in self.definitions:
            if d.clause_id not in known:
                raise ValueError(f"{self.lease_id}: definition {d.term!r} points to unknown clause {d.clause_id}")
        for r in self.refs:
            if r.src not in known or r.dst not in known:
                raise ValueError(f"{self.lease_id}: ref {r.src} -> {r.dst} points to an unknown clause")
        return self


# Labelled item: data/dev/items.jsonl, data/test/items.jsonl


class LabelledItem(Contract):
    item_id: str
    lease_id: str
    clause_id: str
    defect_type: DefectType
    form: Form
    phrasing_family: str
    gold_verdict: Verdict
    gold_provision: str | None
    gold_elements: dict[str, str] = {}
    gold_path: list[str] = []

    @model_validator(mode="after")
    def _check_labels(self):
        if not self.clause_id.startswith(f"{self.lease_id}-"):
            raise ValueError(f"{self.item_id}: clause_id {self.clause_id} is not in lease {self.lease_id}")
        if self.defect_type == "out_of_scope":
            if self.gold_verdict != "handoff" or self.gold_provision is not None:
                raise ValueError(f"{self.item_id}: out_of_scope items are handoff with no provision")
        elif self.gold_provision is None:
            raise ValueError(f"{self.item_id}: in-scope items need a gold_provision")
        allowed = ELEMENTS[self.defect_type]
        for name, value in self.gold_elements.items():
            if name not in allowed:
                raise ValueError(f"{self.item_id}: {name!r} is not an element of {self.defect_type}")
            if allowed[name] is not None and value not in allowed[name]:
                raise ValueError(f"{self.item_id}: {name}={value!r} not in {sorted(allowed[name])}")
        return self


# Prediction: runs/<run_id>/preds.jsonl, the only thing the evaluation harness reads


class ToolCall(Contract):
    tool: str
    args: dict


class Prediction(Contract):
    item_id: str
    verdict: Verdict
    cited_node: str | None = None
    path: list[str] = []
    elements: dict[str, str] = {}
    tool_calls: list[ToolCall] = []
    tokens_in: int = 0
    tokens_out: int = 0


def check_graph(nodes: list[StatuteNode], edges: list[StatuteEdge]) -> None:
    """Raise if node ids repeat or an edge points to a missing node."""
    ids = [n.id for n in nodes]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate statute node id")
    known = set(ids)
    for e in edges:
        if e.src not in known or e.dst not in known:
            raise ValueError(f"edge {e.src} -> {e.dst} points to a missing node")


def check_items(items: list[LabelledItem], leases: dict[str, Lease], nodes: list[StatuteNode]) -> None:
    """Raise if an item points to a clause, provision or path node that does not exist."""
    node_ids = {n.id for n in nodes}
    seen = set()
    for it in items:
        if it.item_id in seen:
            raise ValueError(f"duplicate item_id {it.item_id}")
        seen.add(it.item_id)
        lease = leases.get(it.lease_id)
        if lease is None:
            raise ValueError(f"{it.item_id}: unknown lease {it.lease_id}")
        clause_ids = {c.clause_id for c in lease.clauses}
        if it.clause_id not in clause_ids:
            raise ValueError(f"{it.item_id}: unknown clause {it.clause_id}")
        if it.gold_provision is not None and it.gold_provision not in node_ids:
            raise ValueError(f"{it.item_id}: unknown provision {it.gold_provision}")
        missing = [p for p in it.gold_path if p not in node_ids and p not in clause_ids]
        if missing:
            raise ValueError(f"{it.item_id}: gold_path has unknown ids {missing}")
