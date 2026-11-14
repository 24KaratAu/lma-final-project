"""Tests for the statute graph, the lease parser and flat retrieval. No GPU, PDF or model download needed."""

from pathlib import Path

import pytest

from src.common.jsonl import read_jsonl, read_leases
from src.common.schemas import LabelledItem, StatuteEdge, StatuteNode, check_graph, check_items
from src.graph.items import apply_corrections, read_corrections
from src.graph.lease_parser import parse_lease
from src.graph.statute import parse_section, regex_edges, split_sections
from src.retrieval import retrieve
from src.retrieval.flat import FlatIndex

ROOT = Path(__file__).parent.parent
NODES = read_jsonl(ROOT / "data/statute/nodes.jsonl", StatuteNode)
EDGES = read_jsonl(ROOT / "data/statute/edges.jsonl", StatuteEdge)
LEASES = read_leases(ROOT / "data/leases")
DEV = read_jsonl(ROOT / "data/dev/items.jsonl", LabelledItem)


def test_statute_graph_is_valid_and_has_the_provisions_we_cite():
    check_graph(NODES, EDGES)
    ids = {n.id for n in NODES}
    assert {"ICA-27", "ICA-27-E1", "ICA-28", "ICA-28-E1", "ICA-28-E2", "ICA-28-E3"} <= ids
    assert {"src": "ICA-28-E3", "dst": "ICA-28", "type": "exception_to", "source": "parsed"} in [e.model_dump() for e in EDGES]
    s28 = next(n for n in NODES if n.id == "ICA-28")
    assert "restricted absolutely" in s28.text and "Exception" not in s28.text


def test_parse_section_splits_exceptions_explanations_and_illustrations():
    lines = [
        "Agreement void.—Every agreement of this kind, as defined in section 2, is void.",
        "Exception 1.—Saving of one kind.—This section shall not apply to it.",
        "Explanation.—A word means a thing.",
        "Illustrations",
        "(a) A agrees with B. The agreement is void.",
        "(b) A agrees with C. The agreement is valid.",
    ]
    nodes, edges = parse_section("99", lines)
    assert [n.id for n in nodes] == ["ICA-99", "ICA-99-E1", "ICA-99-X1", "ICA-99-Ia", "ICA-99-Ib"]
    assert [e.type for e in edges] == ["exception_to", "explains", "illustrates", "illustrates"]
    two = nodes + [StatuteNode(id="ICA-2", type="section", label="Section 2", text="Interpretation.")]
    assert [(e.src, e.dst) for e in regex_edges(two)] == [("ICA-99", "ICA-2")]


def test_split_sections_needs_increasing_numbers():
    lines = ["1. Short title.—This Act.", "text", "2. Interpretation.—In this Act,", "1. Not a section", "3. Next.—x"]
    assert [n for n, _ in split_sections(lines)] == ["1", "2", "3"]


DEED = """\
THIS DEED is made between:
1. Lessor No. 1
2. Lessor No. 2
3. Lessor No. 3
4. Lessor No. 4
NOW THIS DEED WITNESSETH AS FOLLOWS:
1.
Grant: The Lessor grants the lease.
2.
Rent: The rent is as follows.
(a)
Rent of Rs. 100 per month.
5
(b)
Interest at 10% on late rent, see sub-clause (a) above.
3.
Covenants:
(I) The Lessee shall
(a) pay rent;
(b) keep the premises clean.
(II) The Lessee shall not
(a) sublet;
(b). bring any claim under clause 2 after 30 days.
EXHIBIT "A"
GTC-l3: USE OF PREMISES
(a) The premises shall be used as an office.
EXHIBIT "E"
E.1 "Protest Window" means the period of seven days.
ANNEXURE—I
1.
Restraint: The Lessee shall not compete within the Protest Window.
1A.
The Lessor shall not compete either.
"""


def test_lease_parser_follows_the_deed_numbering():
    lease = parse_lease(DEED, "T01")
    assert [c.clause_id for c in lease.clauses] == [
        "T01-preamble", "T01-1", "T01-2", "T01-2(a)", "T01-2(b)", "T01-3", "T01-3(I)", "T01-3(I)(a)", "T01-3(I)(b)",
        "T01-3(II)", "T01-3(II)(a)", "T01-3(II)(b)", "T01-GTC-13", "T01-GTC-13(a)", "T01-E.1", "T01-AI.1", "T01-AI.1A",
    ]
    by_id = {c.clause_id: c for c in lease.clauses}
    assert "Lessor No. 4" in by_id["T01-preamble"].text  # numbered parties are not clauses
    assert "5" not in by_id["T01-2(a)"].text.split()  # a page number on its own line is dropped
    assert "Rent of Rs. 100" in by_id["T01-2"].text  # a parent's text includes its sub-clauses
    assert by_id["T01-1"].heading == "Grant"
    assert [d.term for d in lease.definitions] == ["Protest Window"]
    refs = {(r.src, r.dst, r.type) for r in lease.refs}
    assert ("T01-AI.1", "T01-E.1", "uses_term") in refs
    assert ("T01-2(b)", "T01-2(a)", "refers_to") in refs
    assert ("T01-3(II)(b)", "T01-2", "refers_to") in refs
    assert not any(src == "T01-2" and dst.startswith("T01-2(") for src, dst, _ in refs)  # not to its own sub-clauses


# Numbering styles of the pool deeds (data/pool/), each cut down to a few lines: (deed, clause ids expected)
LAYOUTS = {
    "roman ARTICLEs, (i) and bare-letter sub-clauses (L01, L12)": (
        "NOW THIS DEED WITNESSETH AS FOLLOWS:\n"
        "                    ARTICLE I - TERM\n"
        "a     The tenure of this lease shall be ten years.\n"
        "b     The Lessee may terminate it early.\n"
        "ARTICLE.II-LEASE RENT\n"
        "(i)   The rent is Rs. 100.\n"
        "(ii)  It is paid monthly; see Article I (b).\n",
        ["preamble", "I", "I(a)", "I(b)", "II", "II(i)", "II(ii)"],
    ),
    "ARTICLE n over n.1 clauses, numbers run into the text (L06, L11, L14)": (
        "NOW THEREFORE THIS DEED WITNESSETH:\n"
        "ARTICLE 1\n"
        "1.1The Lessor grants the lease.\n"
        "1.2. Term: five years.\n"
        "2. A numbered line inside an article is text.\n"
        "ARTICLE 2\n"
        "2.1 Rent is Rs. 100.\n"
        "3.4 A number from another article is text.\n",
        ["preamble", "1", "1.1", "1.2", "2", "2.1"],
    ),
    "lettered parts in capitals (L19)": (
        "THIS LEASE DEED is made at New Delhi.\n"
        "A.   THIS DEED WITNESSETH AS UNDER\n"
        "(i)  The lessors let the premises.\n"
        "B.   THE LESSEE HEREBY COVENANTS AS FOLLOWS:\n"
        "(i)  To pay the rent.\n"
        "(ii) To keep the premises clean.\n",
        ["preamble", "A", "A(i)", "B", "B(i)", "B(ii)"],
    ),
    "1), A. parts and i. items (L09)": (
        "NOW, THEREFORE THIS DOCUMENT WITNESSETH AS FOLLOWS:\n"
        "1)\nDEFINITIONS AND INTERPRETATION\n"
        "A. DEFINITIONS\n"
        "i.\n“Building” shall mean the tower.\n"
        "ii.\n“Term” shall mean five years.\n"
        "B. INTERPRETATION\nHeadings are for convenience.\n"
        "2)\nRENT\na)\nRent is Rs. 100.\n",
        ["preamble", "1", "1(A)", "1(A)(i)", "1(A)(ii)", "1(B)", "2", "2(a)"],
    ),
    "numbering lost to OCR, 13A, and 14.(ii) on one line (L02, L17)": (
        "NOW THIS DEED WITNESSETH:\n"
        "1.\nThat the Lessor lets the premises.\n"
        "2.\nThat the rent is Rs. 100.\n"
        "0.\nThat the Lessor may take a loan.\n"
        "13.\nThat the Lessee shall not alter the premises.\n"
        "13A.\nThat the Lessee shall insure, and the Lessor may relet the premises under clause\n"
        "14(a) in any manner it likes.\n"
        "14.(i). If the Lessee defaults, the Lessor may terminate, as provided in sub-clause\n"
        "14(a) of the Schedule.\n"
        "14.(ii)  The deposit shall be refunded.\n"
        "14(iii).  Notices go by post.\n"
        "15.\nThis deed is signed below.\nA. Murugan\n",
        ["preamble", "1", "2", "13", "13A", "14", "14(i)", "14(ii)", "14(iii)", "15"],
    ),
}


@pytest.mark.parametrize("layout", LAYOUTS)
def test_lease_parser_reads_the_pool_deed_layouts(layout):
    deed, expected = LAYOUTS[layout]
    lease = parse_lease(deed, "T02")
    assert [c.number or "preamble" for c in lease.clauses] == expected


def test_lease_parser_keeps_stray_lines_as_text():
    by_number = {c.number: c.text for c in parse_lease(LAYOUTS["numbering lost to OCR, 13A, and 14.(ii) on one line (L02, L17)"][0], "T02").clauses}
    assert "may take a loan" in by_number["2"]  # "0." after "2." is not a clause
    assert "14(a) in any manner" in by_number["13A"]  # a line that starts with a reference stays text
    assert "14(a) of the Schedule" in by_number["14(i)"]
    assert "A. Murugan" in by_number["15"]  # a signatory's initial is not sub-clause (A)
    by_number = {c.number: c.text for c in parse_lease(LAYOUTS["ARTICLE n over n.1 clauses, numbers run into the text (L06, L11, L14)"][0], "T02").clauses}
    assert "A numbered line inside an article is text" in by_number["1.2"]


def test_pool_items_point_to_parsed_clauses():
    pool = read_jsonl(ROOT / "data/pool/answer_key.jsonl", LabelledItem)
    check_items(apply_corrections(pool, read_corrections(ROOT / "data/pool/corrections.jsonl")), LEASES, NODES)


TEST_DIR = ROOT / "data/test"


@pytest.mark.skipif(not (TEST_DIR / "items.jsonl").exists(), reason="the test set reaches main only at the freeze")
def test_test_items_are_the_keys_plus_corrections_and_point_to_parsed_clauses():
    items = read_jsonl(TEST_DIR / "items.jsonl", LabelledItem)
    expected = []
    for d in (ROOT / "data/pool", TEST_DIR):
        expected += apply_corrections(read_jsonl(d / "answer_key.jsonl", LabelledItem), read_corrections(d / "corrections.jsonl"))
    assert items == expected
    check_items(items, LEASES, NODES)


def test_dev_items_point_to_parsed_clauses():
    check_items(DEV, LEASES, NODES)
    assert len(DEV) == len({it.item_id for it in DEV}) == 61


@pytest.mark.parametrize("lease_id", sorted(LEASES))
def test_committed_leases_match_a_fresh_parse(lease_id):
    src = next(p for d in ("test", "pool", "dev", "pilot") if (p := ROOT / f"data/{d}/planted/{lease_id}.txt").exists())
    assert parse_lease(src.read_text(encoding="utf-8"), lease_id) == LEASES[lease_id]


def test_bm25_and_dense_rank_the_matching_node_first():
    nodes = [
        StatuteNode(id="A", type="section", label="Section A", text="restraint of trade is void"),
        StatuteNode(id="B", type="section", label="Section B", text="restraint of legal proceedings is void"),
    ]
    assert [n.id for n in FlatIndex.bm25(nodes).search("legal proceedings in court", 1)] == ["B"]
    toy = lambda texts: [[1.0, 0.0] if "trade" in t else [0.0, 1.0] for t in texts]  # noqa: E731
    assert [n.id for n in FlatIndex.dense(nodes, toy).search("a trade restraint", 2)] == ["A", "B"]


def test_retrieve_flat_returns_k_statute_nodes():
    item = next(it for it in DEV if it.item_id == "DV-08")  # the S01 arbitration clause
    out = retrieve(item.clause_id, LEASES[item.lease_id], mode="flat", k=5)
    assert len(out["path"]) == 5 and out["path"] == [n["id"] for n in out["nodes"]]
    assert any(p.startswith("ICA-28") for p in out["path"])
    assert retrieve(item.clause_id, LEASES[item.lease_id], mode="none")["path"] == []
    with pytest.raises(NotImplementedError):
        retrieve(item.clause_id, LEASES[item.lease_id], mode="graph")
