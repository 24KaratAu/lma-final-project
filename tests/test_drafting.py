"""Test-item drafting job (src/eval/draft_items.py), with the mock backend."""

import csv
import json

from src.eval import draft_items

CFG = json.loads(draft_items.CONFIG.read_text())


def test_specs_cover_quota_families_and_forms():
    specs = draft_items.sample_specs(CFG)
    assert len(specs) == sum(n for g in CFG["quota"].values() for n in g.values()) * CFG["overdraw"]
    assert len({s["draft_id"] for s in specs}) == len(specs)
    assert {s["family"] for s in specs} == {f["id"] for fams in CFG["families"].values() for f in fams}
    assert any(s["held_out_of_training"] for s in specs)
    for dtype, groups in CFG["quota"].items():
        mine = [s for s in specs if s["defect_type"] == dtype]
        if "void" in groups:
            assert sum(s["verdict"] == "void" for s in mine) == groups["void"] * CFG["overdraw"]
    assert all(s["form"] == "single" for s in specs if s["defect_type"] == "out_of_scope")
    assert any(s["form"] == "cross" for s in specs)
    assert draft_items.sample_specs(CFG) == specs  # seeded


def test_prompt_carries_family_style_and_form():
    spec = next(s for s in draft_items.sample_specs(CFG) if s["form"] == "cross" and s["defect_type"] == "time_limit")
    prompt = draft_items.draft_prompt(spec)
    assert spec["desc"] in prompt and spec["style"] in prompt and "`definitions`" in prompt
    assert "affected_party" in prompt and "restrained_party" not in prompt


def test_to_draft_keeps_bad_output_with_its_problems():
    spec = next(s for s in draft_items.sample_specs(CFG) if s["family"] == "TL-2" and s["form"] == "single")
    good = {
        "clause": "The Lessee shall pay each monthly bill within fifteen days of receiving it from the Lessor.",
        "definitions": [],
        "elements": {"affected_party": "tenant", "what_is_limited": "contractual_step", "period_and_trigger": "15 days from the bill", "effect_on_expiry": "none", "bank_guarantee": "no"},
        "verdict": "valid",
        "provision": "ICA-28",
    }
    d = draft_items.to_draft(spec, json.dumps(good), set(), CFG)
    assert d["problems"] == [] and d["suggested_verdict"] == "valid" and d["verdict_asked"] == "valid"
    bad = draft_items.to_draft(spec, "not json at all", set(), CFG)
    assert bad["problems"] == ["unparseable"] and bad["clause"] == "not json at all"


def test_main_writes_drafts_with_mock(tmp_path):
    report = draft_items.main(["--backend", "mock", "--limit", "12", "--out", str(tmp_path)])
    assert report["n"] == 12
    rows = list(csv.DictReader(open(tmp_path / "drafts.csv", encoding="utf-8")))
    assert len(rows) == 12 and "clause" in rows[0]
    log = json.loads((tmp_path / "config.json").read_text())
    assert log["backend"] == "mock" and log["n_requests"] == 12 and "git_commit" in log
