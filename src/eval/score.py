"""Score a preds.jsonl against a labelled set (mid-submission metrics, PLAN.md section 13).

python -m src.eval.score data/dev/items.jsonl runs/<run_id>/preds.jsonl

A "defect" is a gold verdict of void. Missing predictions count as wrong
(not void, no citation, empty path) and are reported as `missing`.
"""

import argparse
import json
from pathlib import Path

from src.common.jsonl import read_jsonl
from src.common.schemas import LabelledItem, Prediction


def _ratio(a: int, b: int) -> float | None:
    return round(a / b, 4) if b else None


def metrics(pairs: list[tuple[LabelledItem, Prediction | None]], k: int = 5) -> dict:
    tp = fn = fp = tn = correct = cited = cite_n = hit = 0
    for it, p in pairs:
        gold_void = it.gold_verdict == "void"
        pred_void = p is not None and p.verdict == "void"
        tp += gold_void and pred_void
        fn += gold_void and not pred_void
        fp += pred_void and not gold_void
        tn += not gold_void and not pred_void
        correct += p is not None and p.verdict == it.gold_verdict
        if it.gold_provision is not None:
            cite_n += 1
            cited += p is not None and p.cited_node == it.gold_provision
            # ponytail: recall@k reads the first k ids of the prediction's evidence path; switch to a ranked
            # node list if retrieval starts putting lease clauses ahead of statute nodes in the path.
            hit += p is not None and it.gold_provision in p.path[:k]
    recall, precision = _ratio(tp, tp + fn), _ratio(tp, tp + fp)
    f1 = round(2 * precision * recall / (precision + recall), 4) if precision and recall else 0.0 if tp + fn else None
    return {
        "n": len(pairs),
        "missing": sum(p is None for _, p in pairs),
        "verdict_accuracy": _ratio(correct, len(pairs)),
        "defect_recall": recall,
        "defect_precision": precision,
        "defect_f1": f1,
        "false_alarm_rate": _ratio(fp, fp + tn),
        "citation_correct": _ratio(cited, cite_n),
        f"section_recall@{k}": _ratio(hit, cite_n),
        "counts": {"tp": tp, "fn": fn, "fp": fp, "tn": tn},
    }


def score(items: list[LabelledItem], preds: list[Prediction], k: int = 5) -> dict:
    """Overall, by defect type and by form."""
    by_id = {p.item_id: p for p in preds}
    pairs = [(it, by_id.get(it.item_id)) for it in items]
    out = {"overall": metrics(pairs, k)}
    for field in ("defect_type", "form"):
        for value in sorted({getattr(it, field) for it in items}):
            out[f"{field}={value}"] = metrics([pr for pr in pairs if getattr(pr[0], field) == value], k)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("items")
    ap.add_argument("preds")
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()
    result = score(read_jsonl(args.items, LabelledItem), read_jsonl(args.preds, Prediction), args.k)
    Path(args.preds).with_name("metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
