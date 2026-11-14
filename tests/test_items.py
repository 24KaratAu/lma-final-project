"""Tests for the worksheet -> labelled-item builder (src/graph/items.py), on a made-up deed."""

import csv
import json
from pathlib import Path

import pytest

from src.common.jsonl import read_jsonl
from src.common.schemas import LabelledItem, StatuteNode
from src.graph.items import COLUMNS, apply_corrections, build, parse_elements, plant, read_worksheet, start_worksheet, write_csv
from src.graph.lease_parser import parse_lease

ROOT = Path(__file__).parent.parent
NODES = read_jsonl(ROOT / "data/statute/nodes.jsonl", StatuteNode)

DEED = """THIS LEASE DEED is made at Pune.
NOW THIS DEED WITNESSETH AS FOLLOWS:
1. Definitions
(a) "Premises" means the third floor of the Tower.
(b) "Term" means five years.
2. The Lessee shall pay rent of Rs. 100 a month.
3. Disputes shall be referred to arbitration at Pune.
4. This deed is signed in duplicate.
"""

BAR = (
    "2A. The Lessee shall not institute any suit or other proceeding against the Lessor in respect of any claim\n"
    "under this Deed, and the decision of the Lessor on any such claim shall be final."
)
RESTRAINT = (
    "3A. For the Restricted Period the Lessee shall not carry on any business similar to that carried on at the "
    "Premises within five kilometres of the Tower."
)
RESTRICTED = '(c) "Restricted Period" means two years from the end of the Term.'


def row(**kw) -> dict:
    return {c: "" for c in COLUMNS} | {"keep": "y"} | kw


def rows() -> list[dict]:
    return [
        row(item_id="TE-001", batch="T1", lease_id="H01", after="2", clause_id="2A", clause=BAR,
            defect_type="bar_proceedings", family="BP-4", form="single", verdict="void", provision="ICA-28",
            elements="restricted_party=tenant; degree=absolute; alternative_forum=none"),
        row(item_id="TE-002", batch="T2", lease_id="H01", after="3", clause_id="3A", clause=RESTRAINT,
            support_after="1(b)", support_id="1(c)", support=RESTRICTED,
            defect_type="restraint_trade", family="RT-1", form="cross", verdict="void", provision="ICA-27",
            elements="restrained_party=tenant; window=after_term; goodwill_sale=no"),
        row(keep="", item_id="", draft_id="D-0007", clause="a draft that was not kept"),
    ]


@pytest.fixture
def folder(tmp_path) -> Path:
    (tmp_path / "hosts").mkdir()
    (tmp_path / "hosts/H01.txt").write_text(DEED, encoding="utf-8")
    (tmp_path / "leases").mkdir()
    return tmp_path


def run(folder: Path, worksheet: list[dict], batch: str, write: bool = True) -> dict:
    return build(worksheet, batch, folder / "test", [folder / "hosts"], folder / "leases", NODES, [], write)


def test_plant_writes_clauses_after_the_clause_and_its_sub_clauses():
    text = plant(DEED, "H01", [("1", RESTRICTED), ("3", RESTRAINT)])
    numbers = [c.number for c in parse_lease(text, "H01").clauses]
    assert numbers == ["", "1", "1(a)", "1(b)", "1(c)", "2", "3", "3A", "4"]  # "" is the preamble


def test_build_plants_checks_and_keys_one_batch_at_a_time(folder):
    report = run(folder, rows(), "T1")
    assert report["new_items"] == 1
    key = read_jsonl(folder / "test/answer_key.jsonl", LabelledItem)
    assert [it.item_id for it in key] == ["TE-001"]
    assert key[0].clause_id == "H01-2A" and key[0].gold_path == ["ICA-28"]
    assert "3A." not in (folder / "test/planted/H01.txt").read_text()  # batch T2 is not written yet

    run(folder, rows(), "T2")
    key = read_jsonl(folder / "test/answer_key.jsonl", LabelledItem)
    assert [it.item_id for it in key] == ["TE-001", "TE-002"]
    assert key[1].gold_path == ["H01-1(c)", "ICA-27"]  # the supporting definition, then the section
    lease = json.loads((folder / "leases/H01.json").read_text())
    assert {"H01-2A", "H01-3A", "H01-1(c)"} <= {c["clause_id"] for c in lease["clauses"]}
    with open(folder / "test/batches/T2_answer_sheet_blank.csv", newline="") as f:
        assert list(csv.DictReader(f)) == [
            {"item_id": "TE-002", "lease_id": "H01", "clause": "cl. 3A", "answer": "", "section_or_exception": "", "reason": ""}
        ]
    with open(folder / "test/items.csv", newline="") as f:
        assert [r["item_id"] for r in csv.DictReader(f)] == ["TE-001", "TE-002"]


def test_build_check_writes_nothing(folder):
    run(folder, rows(), "T1", write=False)
    assert not (folder / "test").exists()


def test_build_refuses_to_change_a_keyed_item(folder):
    run(folder, rows(), "T1")
    edited = rows()
    edited[0]["verdict"] = "handoff"
    with pytest.raises(ValueError, match="corrections.jsonl"):
        run(folder, edited, "T2")


def test_build_says_where_a_misnumbered_clause_landed(folder):
    bad = rows()
    bad[0]["clause_id"] = "2B"
    with pytest.raises(ValueError, match="no clause '2B'"):
        run(folder, bad, "T1")


def test_build_asks_for_missing_fields(folder):
    bad = rows()
    bad[0]["verdict"] = ""
    with pytest.raises(ValueError, match="fill verdict"):
        run(folder, bad, "T1")


def test_corrections_change_only_the_fields_named():
    item = LabelledItem(item_id="X-1", lease_id="H01", clause_id="H01-2A", defect_type="bar_proceedings", form="single",
                        phrasing_family="BP-4", gold_verdict="handoff", gold_provision="ICA-28")
    fixed = apply_corrections([item], [{"item_id": "X-1", "set": {"gold_verdict": "void"}, "reason": "lawyer", "source": "S2"}])
    assert fixed[0].gold_verdict == "void" and fixed[0].clause_id == "H01-2A"


def test_parse_elements_takes_pairs_or_json():
    assert parse_elements("a=b; c = d") == {"a": "b", "c": "d"} == parse_elements('{"a": "b", "c": "d"}')
    assert parse_elements("") == {}


def test_worksheet_starts_from_the_drafts_without_copying_the_labels(tmp_path):
    draft = {
        "draft_id": "D-0001", "defect_type": "time_limit", "family": "TL-1", "held_out_of_training": "False",
        "form": "cross", "style": "modern", "embedded": "False", "verdict_asked": "void", "clause": "Claims are barred...",
        "definitions": json.dumps(['"Claim Period" means six months.']), "suggested_elements": json.dumps({"affected_party": "tenant"}),
        "suggested_verdict": "void", "suggested_provision": "ICA-28", "problems": "[]",
    }
    write_csv(tmp_path / "drafts.csv", [draft], list(draft))
    [r] = start_worksheet(tmp_path / "drafts.csv")
    assert r["support"] == '"Claim Period" means six months.'
    assert r["suggested_elements"] == "affected_party=tenant"
    assert r["verdict"] == r["provision"] == r["elements"] == r["keep"] == ""  # labels are written by hand
    write_csv(tmp_path / "worksheet.csv", [r], COLUMNS)
    assert read_worksheet(tmp_path / "worksheet.csv")[0]["clause"] == "Claims are barred..."
