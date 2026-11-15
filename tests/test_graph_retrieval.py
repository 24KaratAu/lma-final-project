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


def with_rulings(monkeypatch, *rulings):
    """The statute graph with only these (id, provision, holding) rulings."""
    nodes = {i: n for i, n in NODES.items() if n.type != "ruling"}
    edges = tuple(e for e in EDGES if e.type != "interprets")
    for rid, dst, holding in rulings:
        nodes[rid] = StatuteNode(id=rid, type="ruling", label=f"Case {rid}", text=holding)
        edges += (StatuteEdge(src=rid, dst=dst, type="interprets", source="manual"),)
    monkeypatch.setattr(graph, "statute", lambda: (nodes, edges))


def test_rulings_on_the_retrieved_provisions_follow_them(monkeypatch):
    with_rulings(monkeypatch, ("RUL-07", "ICA-28", "An agreement to sue in one of several courts with jurisdiction is valid."))
    path = retrieve("L00-19", L00, mode="graph", k=5)["path"]
    assert "ICA-28" in path[:5] and path[5] == "RUL-07"


def test_the_ruling_that_matches_the_clause_comes_first_and_one_sharing_no_word_is_left_out(monkeypatch):
    with_rulings(monkeypatch,
                 ("RUL-10", "ICA-28", "Shortening limitation for a suit is void."),
                 ("RUL-07", "ICA-28", "An agreement to sue in one of several courts with jurisdiction is valid."),
                 ("RUL-09", "ICA-28", "Subject to the jurisdiction of the courts at Kolkata excludes other courts."))
    path = retrieve("L00-19", L00, mode="graph", k=5)["path"]
    assert [p for p in path if p.startswith("RUL-")] == ["RUL-09", "RUL-07"]


def test_neighbours_go_both_ways_along_exceptions():
    assert "ICA-28-E1" in graph.neighbours("ICA-28", EDGES)
    assert "ICA-28" in graph.neighbours("ICA-28-E1", EDGES)
