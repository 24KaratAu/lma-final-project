"""Controller agent: gather evidence with the tools, then hand it to verify() (PLAN.md section 5, Phase 2).

Policies (config "policy"):
  fixed       no model in the loop: the clause's own definitions and linked clauses, a statute
              search on its text, then verify. The fixed-pipeline variant of the agent.
  controller  a model picks one tool call per step until it calls verify or the step budget runs out.

Reasoning variants for the controller (config "reasoning"):
  direct      reply with the next action only
  think       one or two sentences of reasoning, then the action (ReAct style)
  plan        a short plan on the first step, kept in view on later steps, then the action

Hand-off: verify() decides the verdict; if its confidence is below config "handoff_below"
the clause is handed off. Running out of steps is not a hand-off by itself: verify still
runs on the evidence gathered so far, and the run log notes the budget was spent.
"""

import json
import re

from src.agent.tools import Toolbox, load_statute
from src.common.schemas import ELEMENTS, Lease, Prediction, ToolCall

REASONING = {
    "direct": "Reply with the JSON action only.",
    "think": "First write 'Thought:' and one or two sentences on what is still missing, then the JSON action on the last line.",
    "plan": "First write 'Plan:' and up to four short steps: which defined terms and linked clauses to read, and which provision and exceptions to check. Then the JSON action on the last line.",
}

TOOL_HELP = """\
Tools (one per step):
  get_clause         {"clause_id": "..."}   another clause of this lease, by id or by its number in the deed
  lookup_definition  {"term": "..."}        the lease's definition of a capitalised or quoted term
  search_graph       {"query": "..."}       Contract Act provisions matching the query, each section with its exceptions
  expand             {"node_id": "..."}     what a statute node (e.g. ICA-28) or a lease clause links to
  verify             {}                     finish: the verifier decides with the evidence gathered so far
Reply format: {"tool": "<name>", "args": {...}}"""


def run_agent(lease: Lease, config: dict) -> list[Prediction]:
    """Same contract as src/agent/pipeline.run_agent, with tools instead of one retrieve call.

    config keys:
      targets        list of {"item_id", "clause_id"}; ids only, never gold labels
      verify         verify(clause_text, evidence, elements) -> {"verdict", "provision", "confidence", ...}
      policy         "fixed" or "controller" (default "fixed")
      planner        planner(prompt) -> str, the model that picks tool calls (controller only)
      reasoning      "direct", "think" or "plan" (default "think")
      max_steps      tool calls before verify is forced (default 6)
      k              statute search depth (default 5)
      evidence_k     statute nodes passed to verify, in the order found (default 8); lease clauses all go
      handoff_below  hand off when verify's confidence is below this (default None: never)
      statute        (nodes, edges); default data/statute
      log            optional list; one dict per clause with the transcript is appended
    """
    nodes, edges = config.get("statute") or load_statute()
    clauses = {c.clause_id: c for c in lease.clauses}
    preds = []
    for target in config["targets"]:
        clause = clauses[target["clause_id"]]
        tools = Toolbox(lease, nodes, edges, k=config.get("k", 5))
        if config.get("policy", "fixed") == "controller":
            transcript, spent = _control(clause, tools, config)
        else:
            transcript, spent = _fixed(clause, tools), False
        tools.calls.append(ToolCall(tool="verify", args={}))
        out = config["verify"](clause.text, {"nodes": _evidence(tools, config.get("evidence_k", 8)), "path": tools.path()}, ELEMENTS)
        verdict = out["verdict"]
        threshold = config.get("handoff_below")
        if threshold is not None and out.get("confidence", 0.0) < threshold:
            verdict = "handoff"
        preds.append(
            Prediction(
                item_id=target["item_id"],
                verdict=verdict,
                cited_node=out.get("provision"),
                path=tools.path(),
                elements=out.get("elements", {}),
                tool_calls=tools.calls,
            )
        )
        if config.get("log") is not None:
            config["log"].append({"item_id": target["item_id"], "budget_spent": spent, "transcript": transcript, "verify": out})
    return preds


def _evidence(tools: Toolbox, k: int, lease_chars: int = 1500) -> list[dict]:
    """The first k statute nodes found, then every lease clause and definition read (cut to keep the prompt short)."""
    statute = [n for n in tools.evidence_nodes() if n["id"] in tools.nodes][:k]
    lease = [n | {"text": n["text"][:lease_chars]} for n in tools.evidence_nodes() if n["id"] not in tools.nodes]
    return lease + statute


def _fixed(clause, tools: Toolbox) -> list[dict]:
    """Definitions and clauses the target links to, then a statute search on its text."""
    steps = []
    for link in tools.links(clause.clause_id):
        steps.append(("get_clause", {"clause_id": link["clause_id"]}))
    steps.append(("search_graph", {"query": clause.text}))
    return [{"tool": t, "args": a, "observation": tools.call(t, a)} for t, a in steps]


def _control(clause, tools: Toolbox, config: dict) -> tuple[list[dict], bool]:
    reasoning = config.get("reasoning", "think")
    max_steps = config.get("max_steps", 6)
    transcript, plan = [], None
    for step in range(max_steps):
        reply = config["planner"](_prompt(clause, tools, transcript, reasoning, plan, max_steps - step))
        if reasoning == "plan" and plan is None:
            m = re.search(r"Plan:(.*?)(\{|$)", reply, re.S)
            plan = m.group(1).strip() if m else ""
        action = parse_action(reply)
        if action is None:
            transcript.append({"tool": None, "args": {}, "observation": {"error": "no JSON action found"}, "reply": reply})
            if len(transcript) >= 2 and transcript[-2]["tool"] is None:
                return transcript, False  # two unreadable replies in a row: stop and verify
            continue
        tool, args = action
        if tool == "verify":
            return transcript, False
        if any(t["tool"] == tool and t["args"] == args for t in transcript):
            obs = {"error": "already done; use the result above or call verify"}
            tools.calls.append(ToolCall(tool=tool, args=args))
        else:
            obs = tools.call(tool, args)
        transcript.append({"tool": tool, "args": args, "observation": obs, "reply": reply})
    return transcript, True


def _prompt(clause, tools: Toolbox, transcript: list[dict], reasoning: str, plan: str | None, steps_left: int) -> str:
    links = tools.links(clause.clause_id)
    parts = [
        "You check one clause of an Indian commercial lease for enforceability under Sections 27 and 28 of the "
        "Indian Contract Act, 1872. Gather what a lawyer would need to decide it: the definitions of terms it uses, "
        "clauses it depends on, and the statute provision with its exceptions. Then call verify.",
        TOOL_HELP,
        f"Clause {clause.number or clause.clause_id} ({clause.clause_id}) {clause.heading}".rstrip() + f":\n{clause.text}",
    ]
    if links:
        parts.append("This clause links to: " + ", ".join(f"{l['clause_id']} ({l['type']})" for l in links))
    if plan:
        parts.append("Your plan: " + plan)
    for i, t in enumerate(transcript, 1):
        parts.append(f"Step {i}: {json.dumps({'tool': t['tool'], 'args': t['args']})}\nResult: {json.dumps(t['observation'], ensure_ascii=False)}")
    parts.append(f"Evidence gathered: {', '.join(tools.path()) or 'none'}. Steps left: {steps_left}.")
    parts.append(REASONING[reasoning])
    return "\n\n".join(parts)


def parse_action(text: str) -> tuple[str, dict] | None:
    """The last JSON object in the reply that names a tool."""
    decoder, found = json.JSONDecoder(), None
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text[m.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("tool"), str):
            found = (obj["tool"].strip(), obj.get("args") if isinstance(obj.get("args"), dict) else {})
    return found
