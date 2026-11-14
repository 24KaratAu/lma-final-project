"""Tests for the rulings sheet and its ruling nodes and `interprets` edges (src/graph/rulings.py)."""

from pathlib import Path

import pytest

from src.common.jsonl import read_jsonl
from src.common.schemas import StatuteEdge, StatuteNode
from src.graph.rulings import COLUMNS, merge, read_sheet, ruling_graph

ROOT = Path(__file__).resolve().parents[1]
NODES = read_jsonl(ROOT / "data/statute/nodes.jsonl", StatuteNode)
EDGES = read_jsonl(ROOT / "data/statute/edges.jsonl", StatuteEdge)
SHEET = read_sheet(ROOT / "data/statute/rulings.csv")


def row(rid="RUL-01", interprets="ICA-28", holding="Parties may choose among competent courts.", **kw):
    r = dict.fromkeys(COLUMNS, "") | {"ruling_id": rid, "case": "Hakam Singh v Gammon (India) Ltd",
                                      "citation": "(1971) 1 SCC 286", "interprets": interprets, "holding": holding,
                                      "source_url": "https://example.org/hakam-singh", "read_by": "Saksham", "read_on": "2026-11-16"}
    return r | kw


def test_sheet_lists_the_lawyers_judgments_with_valid_provisions():
    provisions = {n.id for n in NODES if n.type in ("section", "exception", "explanation")}
    assert len(SHEET) == 18 and len({r["ruling_id"] for r in SHEET}) == 18
    for r in SHEET:
        assert r["case"] and r["citation"] and r["lawyer_note"], r["ruling_id"]
        assert {t.strip() for t in r["interprets"].split(";")} <= provisions, r["ruling_id"]


def test_committed_graph_matches_the_sheet():
    # someone who fills in a row must rerun `python -m src.graph.rulings`
    nodes, edges = merge(NODES, EDGES, SHEET)
    assert nodes == NODES and edges == EDGES


def test_only_rows_read_by_a_person_enter_the_graph():
    for missing in ("holding", "source_url", "read_by", "read_on"):
        assert ruling_graph([row(**{missing: ""})], NODES) == ([], [])


def test_a_read_row_gives_a_ruling_node_and_manual_interprets_edges():
    nodes, edges = ruling_graph([row(interprets="ICA-28; ICA-28-E1")], NODES)
    assert [(n.id, n.type, n.text) for n in nodes] == [("RUL-01", "ruling", "Parties may choose among competent courts.")]
    assert nodes[0].label == "Hakam Singh v Gammon (India) Ltd (1971) 1 SCC 286"
    assert [(e.src, e.dst, e.type, e.source) for e in edges] == [
        ("RUL-01", "ICA-28", "interprets", "manual"), ("RUL-01", "ICA-28-E1", "interprets", "manual")]


@pytest.mark.parametrize("interprets", ["ICA-999", "ICA-29-Ia", ""])
def test_a_ruling_must_interpret_a_provision_in_the_graph(interprets):
    with pytest.raises(ValueError, match="interprets"):
        ruling_graph([row(interprets=interprets)], NODES)


def test_ruling_ids_are_unique():
    with pytest.raises(ValueError, match="unique"):
        ruling_graph([row(), row()], NODES)


def test_merge_replaces_old_rulings_and_is_idempotent():
    once = merge(NODES, EDGES, [row()])
    assert merge(*once, [row()]) == once
    nodes, edges = merge(*once, [row(holding="")])  # the row is no longer read: its node and edge go
    assert nodes == [n for n in NODES if n.type != "ruling"] and edges == [e for e in EDGES if e.type != "interprets"]
