"""Tests for graph retrieval (src/retrieval/graph.py) on the fixture lease and the real statute graph."""

from pathlib import Path

from src.common.jsonl import read_leases
from src.common.schemas import StatuteEdge, StatuteNode
from src.retrieval import graph, retrieve

ROOT = Path(__file__).resolve().parents[1]
L00 = read_leases(ROOT / "tests/fixtures/leases")["L00"]
NODES, EDGES = graph.statute()


def statute_ids(path):
    return [p for p in path if p.startswith("ICA-")]


def test_provisions_come_first_and_number_k():
    out = retrieve("L00-17", L00, mode="graph", k=5)
    assert len(statute_ids(out["path"])) == 5 and out["path"][:5] == statute_ids(out["path"])
    assert all(NODES[p].type in ("section", "exception", "explanation") for p in out["path"][:5])
    assert [n["id"] for n in out["nodes"]] == out["path"]


def test_a_seeded_section_brings_its_exceptions():
    path = retrieve("L00-17", L00, mode="graph", k=5)["path"]
    assert "ICA-28" in path and "ICA-28-E1" in path


def test_a_dispute_clause_brings_the_deeds_arbitration_clause():
    out = retrieve("L00-17", L00, mode="graph")
    assert "L00-18" in out["path"]
    assert next(n for n in out["nodes"] if n["id"] == "L00-18")["type"] == "lease_clause"


def test_a_clause_brings_the_definitions_it_uses():
    assert "L00-1.1" in retrieve("L00-14", L00, mode="graph")["path"]
    assert "L00-1.2" in retrieve("L00-22", L00, mode="graph")["path"]


def test_a_clause_with_no_links_brings_no_lease_clauses():
    assert all(n["type"] != "lease_clause" for n in retrieve("L00-5", L00, mode="graph")["nodes"])


def test_rulings_on_the_retrieved_provisions_follow_them(monkeypatch):
    ruling = StatuteNode(id="RUL-07", type="ruling", label="Hakam Singh (1971) 1 SCC 286", text="Parties may choose a competent court.")
    edges = (*EDGES, StatuteEdge(src="RUL-07", dst="ICA-28", type="interprets", source="manual"))
    monkeypatch.setattr(graph, "statute", lambda: ({**NODES, "RUL-07": ruling}, edges))
    path = retrieve("L00-19", L00, mode="graph", k=5)["path"]
    assert "ICA-28" in path[:5] and path[5] == "RUL-07"


def test_neighbours_go_both_ways_along_exceptions():
    assert "ICA-28-E1" in graph.neighbours("ICA-28", EDGES)
    assert "ICA-28" in graph.neighbours("ICA-28-E1", EDGES)
