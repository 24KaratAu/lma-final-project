"""Tests for generate/verify, the evaluation harness and the training-pair checks. No GPU needed."""

import json
from pathlib import Path

import pytest

from src.common.jsonl import read_jsonl
from src.common.schemas import LabelledItem, Prediction
from src.eval import run
from src.eval.score import score
from src.models.generate import generate
from src.models.verify import build_prompt, make_verify, parse_answer, rule_verdict
from src.train import gen_pairs

ROOT = Path(__file__).parent.parent
FIX = ROOT / "tests/fixtures"
PILOT = read_jsonl(ROOT / "data/pilot/answer_key.jsonl", LabelledItem)
FIXTURE_ITEMS = read_jsonl(FIX / "items.jsonl", LabelledItem)


# FX-09 still carries the pre-review bank-guarantee label; the lawyer's correction makes it void (PLAN.md section 13).
@pytest.mark.parametrize("item", PILOT + [i for i in FIXTURE_ITEMS if i.item_id != "FX-09"], ids=lambda i: i.item_id)
def test_rules_reproduce_gold_verdicts(item):
    assert rule_verdict(item.defect_type, item.gold_elements) == item.gold_verdict


def test_rules_cannot_decide_without_elements():
    assert rule_verdict("time_limit", {}) is None


def test_parse_answer():
    good = parse_answer('Sure.\n{"verdict": "void", "provision": "ICA-27", "confidence": 2, "elements": {"window": "after_term"}}')
    assert (good["verdict"], good["provision"], good["confidence"], good["elements"]) == ("void", "ICA-27", 1.0, {"window": "after_term"})
    for bad in ["no json here", '{"verdict": "maybe"}', "{not json}"]:
        assert parse_answer(bad)["verdict"] == "handoff"


def test_prompt_carries_clause_and_evidence():
    p = build_prompt("CLAUSE-TEXT", {"nodes": [{"id": "ICA-27", "text": "STATUTE-TEXT"}]}, shots=False)
    assert "CLAUSE-TEXT" in p and "[ICA-27] STATUTE-TEXT" in p and "Examples" not in p


def test_mock_verify_hands_off():
    assert make_verify("m", "mock")("any clause", {"nodes": []})["verdict"] == "handoff"
    with pytest.raises(ValueError):
        generate(["x"], "m", backend="nope")


def _pred(item, **kw):
    return Prediction(item_id=item.item_id, verdict=item.gold_verdict, cited_node=item.gold_provision, path=item.gold_path, **kw)


def test_score_perfect_and_counts():
    perfect = score(PILOT, [_pred(it) for it in PILOT])["overall"]
    assert perfect["defect_recall"] == perfect["defect_f1"] == perfect["citation_correct"] == 1.0
    assert perfect["false_alarm_rate"] == 0.0 and perfect["missing"] == 0

    # every clause called void, nothing cited: all defects caught, every look-alike a false alarm
    all_void = score(PILOT, [Prediction(item_id=it.item_id, verdict="void") for it in PILOT])
    o = all_void["overall"]
    n_void = sum(it.gold_verdict == "void" for it in PILOT)
    assert (o["counts"]["tp"], o["counts"]["fp"]) == (n_void, len(PILOT) - n_void)
    assert o["false_alarm_rate"] == 1.0 and o["citation_correct"] == 0.0
    assert {"defect_type=time_limit", "form=cross"} <= set(all_void)


def test_score_counts_missing_as_wrong():
    o = score(PILOT, [])["overall"]
    assert o["missing"] == len(PILOT) and o["defect_recall"] == 0.0 and o["defect_f1"] == 0.0


def test_run_end_to_end_with_mock_and_resume(tmp_path):
    args = ["--items", str(FIX / "items.jsonl"), "--leases", str(FIX / "leases"), "--model", "m", "--backend", "mock", "--out", str(tmp_path), "--run-id", "r"]
    run_dir = run.main(args)
    preds = read_jsonl(run_dir / "preds.jsonl", Prediction)
    assert len(preds) == len(FIXTURE_ITEMS) and all(p.verdict == "handoff" for p in preds)
    config = json.loads((run_dir / "config.json").read_text())
    assert {"git_commit", "seed", "platform", "gpu_type", "gpu_hours_this_session"} <= set(config)
    run.main(args)  # resume: nothing left to do, no duplicates
    assert len(read_jsonl(run_dir / "preds.jsonl", Prediction)) == len(FIXTURE_ITEMS)


CFG = json.loads(gen_pairs.CONFIG.read_text())


def test_specs_skip_held_out_families():
    held = {f["id"] for fams in CFG["families"].values() for f in fams if f.get("held_out")}
    specs = gen_pairs.sample_specs(CFG, 60)
    assert held and not held & {s["family"] for s in specs}
    assert gen_pairs.sample_specs(CFG, 60) == specs  # seeded


def test_check_keeps_good_pair_and_rejects_bad_ones():
    spec = {"pair_id": "G-1", "defect_type": "time_limit", "family": "TL-1", "desc": "", "verdict": "void", "form": "single"}
    good = {
        "clause": "Any claim by the Lessee against the Lessor shall be barred unless a suit is filed within three months of the event giving rise to it.",
        "definitions": [],
        "elements": {"affected_party": "tenant", "what_is_limited": "time_to_sue", "period_and_trigger": "3 months", "effect_on_expiry": "claim_barred", "bank_guarantee": "no"},
        "verdict": "void",
        "provision": "ICA-28",
    }
    seen = set()
    pair, why = gen_pairs.check(spec, json.dumps(good), seen, CFG)
    assert why == [] and pair["verdict"] == "void"
    assert "duplicate" in gen_pairs.check(spec, json.dumps(good), seen, CFG)[1]

    bad = good | {"verdict": "valid", "provision": "ICA-27"}
    assert {"wrong_verdict", "rules_disagree", "bad_provision"} <= set(gen_pairs.check(spec, json.dumps(bad), set(), CFG)[1])
    assert gen_pairs.check(spec | {"form": "cross"}, json.dumps(good), set(), CFG)[1] == ["cross_without_definition"]
    assert gen_pairs.check(spec, "garbage", set(), CFG)[1] == ["unparseable"]
    nested = good | {"elements": {"time_limit": good["elements"]}}  # how Qwen answered in the first trial
    assert gen_pairs.check(spec, json.dumps(nested), set(), CFG)[1] == []
    assert "restrained_party" not in gen_pairs.gen_prompt(spec) and '"ICA-28" or "ICA-28-E3"' in gen_pairs.gen_prompt(spec)

    prompt, target = gen_pairs.to_example(pair)
    assert pair["clause"] in prompt and parse_answer(target)["verdict"] == "void"


def test_trial_writes_report_with_mock(tmp_path):
    report = gen_pairs.main(["--n", "10", "--backend", "mock", "--out", str(tmp_path)])
    assert report["n"] == 10 and report["rejection_rate"] == 1.0  # the mock writes no clause
    assert (tmp_path / "rejected.jsonl").exists()
