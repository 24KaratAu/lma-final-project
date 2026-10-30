"""verify(): the element-check prompt, its parser, and the decision rules.

The rules follow PLAN.md section 6 as corrected by the lawyer in
docs/legal/session1_review.md. The few-shot examples are the lawyer's own
illustrations from that review, not dev or test clauses.
"""

import json
import re

from src.common.schemas import ELEMENTS
from src.models.generate import generate

VERDICTS = {"void", "valid", "handoff"}
PROVISIONS = {
    "restraint_trade": {"ICA-27", "ICA-27-E1"},
    "bar_proceedings": {"ICA-28", "ICA-28-E1", "ICA-28-E2"},
    "time_limit": {"ICA-28", "ICA-28-E3"},
}

RULES = """\
Decision rules (Indian Contract Act, 1872):
- restraint_trade (s.27, ICA-27): a restraint on carrying on a trade or business that runs after the lease ends is void, \
however limited in area or time. A restriction only on the use of the premises during the term is valid. \
A restraint on business elsewhere during the term only: handoff. If goodwill is sold (Exception 1, ICA-27-E1): handoff.
- bar_proceedings (s.28(a) first limb, ICA-28): a clause that shuts out every forum, or makes one party's decision final \
and unchallengeable in any court, is void. Referring disputes to arbitration is valid (ICA-28-E1, or ICA-28-E2 for \
existing disputes). Choosing one court that already has jurisdiction (e.g. where the premises are) is valid; naming a \
court whose jurisdiction cannot be told from the lease: handoff.
- time_limit (s.28(a) second limb and s.28(b), ICA-28): a clause shortening the time to sue, or saying a right is \
extinguished, waived or forfeited, or a party discharged, once a period ends, is void. A period that only governs a \
contractual step (notice, cure, payment) with no such consequence is valid, and so is a time to sue of three years or \
more (no shorter than the Limitation Act allows).
- Anything else (rent, maintenance, caps on liability, stamp duty...) is out_of_scope: verdict handoff, provision null."""

SHOTS = [
    (
        "The Lessee shall not run a similar business within 5 km of the Premises for 3 years after the lease ends.",
        {"defect_type": "restraint_trade", "elements": {"restrained_party": "tenant", "restrained_activity": "trade_or_business", "window": "after_term", "window_start_and_length": "end of lease; 3 years", "goodwill_sale": "no"}, "verdict": "void", "provision": "ICA-27", "confidence": 0.95},
    ),
    (
        "During the lease, the Tenant shall use the premises only as an office.",
        {"defect_type": "restraint_trade", "elements": {"restrained_party": "tenant", "restrained_activity": "premises_use", "window": "during_term", "goodwill_sale": "no"}, "verdict": "valid", "provision": "ICA-27", "confidence": 0.95},
    ),
    (
        "The Landlord's decision on any dispute is final and cannot be challenged in any court.",
        {"defect_type": "bar_proceedings", "elements": {"restricted_party": "tenant", "rights_covered": "under_lease", "degree": "absolute", "alternative_forum": "none"}, "verdict": "void", "provision": "ICA-28", "confidence": 0.95},
    ),
    (
        "The Tenant shall notify the Landlord of any defect within 30 days.",
        {"defect_type": "time_limit", "elements": {"affected_party": "tenant", "what_is_limited": "contractual_step", "period_and_trigger": "30 days from the defect", "effect_on_expiry": "none", "bank_guarantee": "no"}, "verdict": "valid", "provision": "ICA-28", "confidence": 0.9},
    ),
    (
        "The Tenant shall notify the Landlord of any defect within 30 days, failing which the Tenant shall be deemed to have waived all claims in respect of the defect.",
        {"defect_type": "time_limit", "elements": {"affected_party": "tenant", "what_is_limited": "contractual_step", "period_and_trigger": "30 days from the defect", "effect_on_expiry": "right_extinguished", "bank_guarantee": "no"}, "verdict": "void", "provision": "ICA-28", "confidence": 0.9},
    ),
]


def element_sheet(only: str | None = None) -> str:
    lines = []
    for dtype, elements in ELEMENTS.items():
        if not elements or (only and dtype != only):
            continue
        if not only:
            lines.append(f"{dtype}:")
        for name, values in elements.items():
            lines.append(f"{'' if only else '  '}{name}:{' | '.join(sorted(values)) if values else 'free text'}")
    return "\n".join(lines)


def build_prompt(clause_text: str, evidence: dict | None = None, shots: bool = True) -> str:
    """The element-check prompt: classify the clause, fill its elements, then give the verdict."""
    parts = [
        "You review clauses of Indian commercial leases for enforceability under Sections 27 and 28 of the Indian Contract Act, 1872.",
        RULES,
        "Elements to fill for each defect type (use exactly these names and values):\n" + element_sheet(),
    ]
    nodes = (evidence or {}).get("nodes", [])
    if nodes:
        parts.append("Retrieved text:\n" + "\n".join(f"[{n.get('id', '?')}] {n.get('text', '')}" for n in nodes))
    if shots:
        parts.append("Examples:\n" + "\n\n".join(f"Clause: {c}\nAnswer: {json.dumps(a)}" for c, a in SHOTS))
    parts.append(
        "First decide the defect_type (restraint_trade, bar_proceedings, time_limit or out_of_scope), "
        "then fill its elements, then apply the rules. Reply with one JSON object only, with keys "
        "defect_type, elements, verdict (void | valid | handoff), provision (a node id such as ICA-27, or null), "
        "confidence (0 to 1).\n\nClause: " + clause_text + "\nAnswer:"
    )
    return "\n\n".join(parts)


def parse_answer(text: str) -> dict:
    """Read the model's JSON answer; anything unreadable becomes a handoff with confidence 0."""
    fallback = {"verdict": "handoff", "provision": None, "confidence": 0.0, "elements": {}, "defect_type": None}
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return fallback
    try:
        ans = json.loads(match.group(0))
    except json.JSONDecodeError:
        return fallback
    if not isinstance(ans, dict) or ans.get("verdict") not in VERDICTS:
        return fallback
    try:
        conf = min(max(float(ans.get("confidence", 0.0)), 0.0), 1.0)
    except (TypeError, ValueError):
        conf = 0.0
    elements = ans.get("elements") if isinstance(ans.get("elements"), dict) else {}
    return {
        "verdict": ans["verdict"],
        "provision": ans.get("provision") if isinstance(ans.get("provision"), str) else None,
        "confidence": conf,
        "elements": {k: str(v) for k, v in elements.items()},
        "defect_type": ans.get("defect_type"),
    }


def rule_verdict(defect_type: str, el: dict) -> str | None:
    """The verdict the decision rules give for these elements, or None if the elements cannot decide it."""
    if defect_type == "out_of_scope":
        return "handoff"
    if defect_type == "restraint_trade":
        if el.get("goodwill_sale") == "yes":
            return "handoff"
        activity, window = el.get("restrained_activity"), el.get("window")
        if window in ("after_term", "both"):
            return "void" if activity == "trade_or_business" else "handoff" if activity == "premises_use" else None
        if window == "during_term":
            return "valid" if activity == "premises_use" else "handoff" if activity == "trade_or_business" else None
        return None
    if defect_type == "bar_proceedings":
        forum = el.get("alternative_forum")
        if forum == "arbitration":
            return "valid"
        if el.get("degree") == "absolute":
            return "void"
        if forum == "named_court":
            return {"yes": "valid", "no": "void", "cannot_tell": "handoff"}.get(el.get("named_court_competent"))
        return "handoff" if el.get("degree") == "partial" else None
    if defect_type == "time_limit":
        # Bank guarantee (Exception 3) is ignored: a lease clause is never the bank's own guarantee (lawyer, session 1).
        # A time to sue of at least the statutory period has no effect on the right to sue (effect "none"): valid.
        effect = el.get("effect_on_expiry")
        return {"claim_barred": "void", "right_extinguished": "void", "none": "valid"}.get(effect)
    return None


def make_verify(model: str, backend: str = "hf", shots: bool = True, **gen_kw):
    """verify(clause_text, evidence, elements) -> {"verdict", "provision", "confidence", "elements", "defect_type"}.

    With no adapter this is the base model with the element-check prompt (B1 when shots=True).
    """

    def verify(clause_text: str, evidence: dict, elements: dict = ELEMENTS) -> dict:
        [raw] = generate([build_prompt(clause_text, evidence, shots)], model, backend=backend, **gen_kw)
        return parse_answer(raw)

    return verify
