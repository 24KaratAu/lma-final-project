"""The agent's tools and controller on the fixture lease, with scripted models (no GPU)."""

import json
from pathlib import Path

import pytest

from src.agent import controller
from src.agent.tools import Toolbox, load_statute
from src.common.jsonl import read_jsonl, read_leases
from src.common.schemas import LabelledItem
from src.eval import run

FIX = Path(__file__).parent / "fixtures"
STATUTE = load_statute(str(FIX / "statute"))


@pytest.fixture
def lease():
    return read_leases(FIX / "leases")["L00"]


@pytest.fixture
def tools(lease):
    return Toolbox(lease, *STATUTE)


def echo_verify(clause_text, evidence, elements):
    """A verify() that answers void, citing the first statute node it was given."""
    statute = [n["id"] for n in evidence["nodes"] if n["id"].startswith("ICA")]
    return {"verdict": "void", "provision": statute[0] if statute else None, "confidence": 0.4, "elements": {}}


def test_get_clause_by_id_and_number(tools):
    assert tools.get_clause("L00-14")["number"] == "14"
    assert tools.get_clause("14")["clause_id"] == "L00-14"
    assert tools.get_clause("cl. 14")["links"] == [{"type": "uses_term", "clause_id": "L00-1.1"}]
    assert "error" in tools.get_clause("99")


def test_lookup_definition(tools):
    got = tools.lookup_definition("restricted period")
    assert got["definitions"][0]["clause_id"] == "L00-1.1"
    assert "L00-1.1" in tools.evidence
    assert "error" in tools.lookup_definition("Turnover")


def test_search_graph_adds_exceptions_after_their_section(tools):
    ids = [n["id"] for n in tools.search_graph("restrained from carrying on any trade or business", k=1)["nodes"]]
    assert ids[0] in ("ICA-27", "ICA-27-E1") and {"ICA-27", "ICA-27-E1"} <= set(ids)


def test_expand_statute_and_lease(tools):
    assert {n["id"] for n in tools.expand("ICA-28")["neighbours"]} == {"ICA-28-E1", "ICA-28-E2", "ICA-28-E3"}
    assert tools.expand("L00-22")["neighbours"][0]["clause_id"] == "L00-1.2"
    assert tools.path()[-1] == "L00-1.2"  # lease clauses after statute nodes


def test_bad_calls_are_logged_not_raised(tools):
    assert "error" in tools.call("delete_everything", {})
    assert "error" in tools.call("get_clause", {"wrong": 1})
    assert [c.tool for c in tools.calls] == ["delete_everything", "get_clause"]


def test_parse_action():
    assert controller.parse_action('Thought: need the term.\n{"tool": "lookup_definition", "args": {"term": "X"}}') == ("lookup_definition", {"term": "X"})
    assert controller.parse_action('Plan: {a} then\n{"tool": "verify"}') == ("verify", {})
    assert controller.parse_action("no json here") is None


def test_fixed_policy_reads_linked_definition_and_statute(lease):
    [p] = controller.run_agent(lease, {"targets": [{"item_id": "FX-01", "clause_id": "L00-14"}], "verify": echo_verify, "statute": STATUTE})
    assert "L00-1.1" in p.path and "ICA-27" in p.path
    assert [c.tool for c in p.tool_calls] == ["get_clause", "search_graph", "verify"]
    assert p.verdict == "void"


@pytest.mark.parametrize("reasoning", sorted(controller.REASONING))
def test_controller_follows_the_planner(lease, reasoning):
    script = iter([
        'Plan: read the term, then s.27.\n{"tool": "lookup_definition", "args": {"term": "Restricted Period"}}',
        '{"tool": "search_graph", "args": {"query": "restraint of trade"}}',
        '{"tool": "search_graph", "args": {"query": "restraint of trade"}}',  # repeated: not run again
        '{"tool": "verify", "args": {}}',
    ])
    prompts, log = [], []

    def planner(prompt):
        prompts.append(prompt)
        return next(script)

    cfg = {"targets": [{"item_id": "FX-01", "clause_id": "L00-14"}], "verify": echo_verify, "policy": "controller",
           "planner": planner, "reasoning": reasoning, "statute": STATUTE, "log": log}
    [p] = controller.run_agent(lease, cfg)
    assert [c.tool for c in p.tool_calls] == ["search_graph", "lookup_definition", "search_graph", "search_graph", "verify"]
    assert "L00-1.1" in p.path and "ICA-27" in p.path
    assert "already done" in json.dumps(log[0]["transcript"][3]["observation"])
    assert not log[0]["budget_spent"]
    assert "Steps left: 6" in prompts[0] and "L00-1.1 (uses_term)" in prompts[0]
    assert controller.REASONING[reasoning] in prompts[0]
    if reasoning == "plan":
        assert "Your plan: read the term, then s.27." in prompts[1]


def test_controller_budget_and_handoff(lease):
    log = []
    cfg = {"targets": [{"item_id": "FX-01", "clause_id": "L00-14"}], "verify": echo_verify, "policy": "controller",
           "planner": lambda p: '{"tool": "expand", "args": {"node_id": "ICA-' + str(len(log) + p.count("Step ") + 27) + '"}}',
           "max_steps": 2, "handoff_below": 0.5, "statute": STATUTE, "log": log}
    [p] = controller.run_agent(lease, cfg)
    assert log[0]["budget_spent"] and len(p.tool_calls) == 4  # seed search, two steps, then verify is forced
    assert p.verdict == "handoff"  # confidence 0.4 < 0.5


def test_controller_stops_after_two_unreadable_replies(lease):
    [p] = controller.run_agent(lease, {"targets": [{"item_id": "FX-01", "clause_id": "L00-14"}], "verify": echo_verify,
                                       "policy": "controller", "planner": lambda p: "I am not sure.", "statute": STATUTE})
    assert [c.tool for c in p.tool_calls] == ["search_graph", "verify"]  # the seed search still runs


def test_controller_stops_when_a_call_is_repeated_twice(lease):
    log = []
    [p] = controller.run_agent(lease, {"targets": [{"item_id": "FX-01", "clause_id": "L00-14"}], "verify": echo_verify,
                                       "policy": "controller", "planner": lambda p: '{"tool": "get_clause", "args": {"clause_id": "2"}}',
                                       "seed_search": False, "statute": STATUTE, "log": log})
    assert [c.tool for c in p.tool_calls] == ["get_clause", "get_clause", "verify"]
    assert not log[0]["budget_spent"]


def test_lookup_definition_finds_a_term_defined_inside_a_clause(lease):
    text = 'The date of handover, on expiry or earlier termination, is hereinafter referred to as the “Exit Date”.'
    lease = lease.model_copy(update={"clauses": lease.clauses + [lease.clauses[0].model_copy(update={"clause_id": "L00-30", "number": "30", "text": text})]})
    got = Toolbox(lease, *STATUTE).lookup_definition("Exit Date")
    assert got["definitions"][0]["clause_id"] == "L00-30" and "Exit Date" in got["definitions"][0]["text"]


@pytest.mark.parametrize("agent", ["fixed", "controller"])
def test_runner_with_agent_and_mock(tmp_path, agent):
    out = run.main(["--items", str(FIX / "items.jsonl"), "--leases", str(FIX / "leases"), "--model", "m", "--backend", "mock",
                    "--agent", agent, "--run-id", "a", "--out", str(tmp_path)])
    n = len(read_jsonl(FIX / "items.jsonl", LabelledItem))
    assert len((out / "preds.jsonl").read_text().splitlines()) == n
    assert len((out / "traces.jsonl").read_text().splitlines()) == n
    assert json.loads((out / "config.json").read_text())["agent"] == agent
