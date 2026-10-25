"""Fixture test: the contracts load, agree with each other, and run end to end with no GPU."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.agent.pipeline import run_agent
from src.common.jsonl import read_jsonl, read_leases, write_jsonl
from src.common.mocks import make_oracle_retrieve, make_oracle_verify, mock_generate
from src.common.schemas import LabelledItem, Prediction, StatuteEdge, StatuteNode, check_graph, check_items

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def nodes():
    return read_jsonl(FIX / "statute/nodes.jsonl", StatuteNode)


@pytest.fixture(scope="module")
def edges():
    return read_jsonl(FIX / "statute/edges.jsonl", StatuteEdge)


@pytest.fixture(scope="module")
def leases():
    return read_leases(FIX / "leases")


@pytest.fixture(scope="module")
def items():
    return read_jsonl(FIX / "items.jsonl", LabelledItem)


def test_fixture_sizes(nodes, leases, items):
    assert (len(nodes), len(leases), len(items)) == (8, 1, 10)


def test_graph_is_consistent(nodes, edges):
    check_graph(nodes, edges)


def test_items_point_to_real_clauses_and_nodes(items, leases, nodes):
    check_items(items, leases, nodes)


def test_fixtures_cover_every_label(items):
    assert {it.defect_type for it in items} == {"restraint_trade", "bar_proceedings", "time_limit", "out_of_scope"}
    assert {it.gold_verdict for it in items} == {"void", "valid", "handoff"}
    assert {it.form for it in items} == {"single", "cross"}


@pytest.mark.parametrize(
    "change",
    [
        {"gold_elements": {"window_length": "3 years"}},  # not an element of restraint_trade
        {"gold_elements": {"window": "forever"}},  # not an allowed value
        {"gold_verdict": "unclear"},
        {"form": "multi"},
        {"clause_id": "L99-14"},  # clause from another lease
        {"defect_type": "out_of_scope"},  # out_of_scope must be handoff with no provision
        {"extra_field": 1},
    ],
)
def test_bad_items_are_rejected(items, change):
    with pytest.raises(ValidationError):
        LabelledItem.model_validate(items[0].model_dump() | change)


def test_mock_generate_answers_every_prompt():
    out = mock_generate(["a", "b", "c"], model="mock")
    assert len(out) == 3 and out[0] == out[2]


def test_pipeline_end_to_end(tmp_path, items, leases, nodes):
    lease = leases["L00"]
    config = {
        "targets": [{"item_id": it.item_id, "clause_id": it.clause_id} for it in items],
        "retrieve": make_oracle_retrieve(items, nodes),
        "verify": make_oracle_verify(items, leases),
    }
    write_jsonl(tmp_path / "preds.jsonl", run_agent(lease, config))
    preds = {p.item_id: p for p in read_jsonl(tmp_path / "preds.jsonl", Prediction)}

    assert set(preds) == {it.item_id for it in items}
    for it in items:
        p = preds[it.item_id]
        assert (p.verdict, p.cited_node, p.path) == (it.gold_verdict, it.gold_provision, it.gold_path)
