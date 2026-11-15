"""Paired comparison of two runs (H3): point estimates, bootstrap interval, margin."""

from pathlib import Path

from src.common.jsonl import read_jsonl
from src.common.schemas import LabelledItem, Prediction
from src.eval import compare, run, run_all
from src.eval.score import score

FIX = Path(__file__).parent / "fixtures"
ITEMS = read_jsonl(FIX / "items.jsonl", LabelledItem)


def preds(void_ids):
    return [Prediction(item_id=it.item_id, verdict="void" if it.item_id in void_ids else "valid") for it in ITEMS]


def test_f1_matches_the_scorer_and_identical_runs_differ_by_zero():
    gold = {it.item_id for it in ITEMS if it.gold_verdict == "void"}
    noisy = preds(set(list(gold)[1:]) | {next(it.item_id for it in ITEMS if it.gold_verdict != "void")})
    res = compare.compare(ITEMS, noisy, noisy, n_boot=200)
    assert res["system_f1"] == score(ITEMS, noisy)["overall"]["defect_f1"]
    assert res["difference"] == 0 and res["ci95"] == [0.0, 0.0] and res["within_margin"]


def test_a_worse_system_is_outside_the_margin():
    gold = {it.item_id for it in ITEMS if it.gold_verdict == "void"}
    res = compare.compare(ITEMS, preds(set()), preds(gold), margin=0.05, n_boot=200)
    assert res["baseline_f1"] == 1.0 and res["system_f1"] == 0.0 and not res["within_margin"]
    assert res["ci95"][0] <= res["difference"] <= res["ci95"][1] < 0
    assert res == compare.compare(ITEMS, preds(set()), preds(gold), margin=0.05, n_boot=200)  # same seed, same interval


def test_table_leaves_recall_blank_without_retrieval(tmp_path):
    for mode in ("none", "flat"):
        run.main(["--items", str(FIX / "items.jsonl"), "--leases", str(FIX / "leases"), "--model", "m", "--backend", "mock",
                  "--mode", mode, "--run-id", mode, "--out", str(tmp_path)])
    head, _, flat, none = run_all.table(str(tmp_path)).splitlines()
    assert "exact provision recall@5" in head and "section_recall" not in head
    assert none.split("|")[-3].strip() == "–" and flat.split("|")[-3].strip() != "–"
