"""Two runs on the same labelled set: defect F1 of each, the difference and its bootstrap interval (PLAN.md section 14, H3).

python -m src.eval.compare --items data/test/items.jsonl \
    --system runs/agent-controller-test --baseline runs/B2-none-test --margin 0.05

The verdict on the margin uses the point estimates. The interval is a paired bootstrap:
the same resampled items are scored for both runs, so it is the interval of the difference,
not of each score. A missing prediction counts as "not void", as in src/eval/score.py.
F1 is computed from the counts, so it can differ from metrics.json in the fourth decimal
(score.py rounds precision and recall first).
"""

import argparse
import json
import random
from pathlib import Path

from src.common.jsonl import read_jsonl
from src.common.schemas import LabelledItem, Prediction


def _f1(rows: list[tuple[bool, bool]]) -> float:
    """Defect F1 from (gold is void, predicted void) pairs; 0 when there is no true positive."""
    tp = sum(g and p for g, p in rows)
    wrong = sum(g != p for g, p in rows)  # fp + fn
    return 2 * tp / (2 * tp + wrong) if tp else 0.0


def compare(items: list[LabelledItem], system: list[Prediction], baseline: list[Prediction],
            margin: float = 0.05, n_boot: int = 10000, seed: int = 0) -> dict:
    sys_void = {p.item_id for p in system if p.verdict == "void"}
    base_void = {p.item_id for p in baseline if p.verdict == "void"}
    rows = [(it.gold_verdict == "void", it.item_id in sys_void, it.item_id in base_void) for it in items]
    f_sys, f_base = _f1([(g, s) for g, s, _ in rows]), _f1([(g, b) for g, _, b in rows])
    rng, diffs = random.Random(seed), []
    for _ in range(n_boot):
        sample = rng.choices(rows, k=len(rows))
        diffs.append(_f1([(g, s) for g, s, _ in sample]) - _f1([(g, b) for g, _, b in sample]))
    diffs.sort()
    return {
        "n": len(rows),
        "system_f1": round(f_sys, 4),
        "baseline_f1": round(f_base, 4),
        "difference": round(f_sys - f_base, 4),
        "ci95": [round(diffs[int(0.025 * n_boot)], 4), round(diffs[int(0.975 * n_boot) - 1], 4)],
        "margin": margin,
        "within_margin": f_sys >= f_base - margin,
        "n_boot": n_boot,
        "seed": seed,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="data/test/items.jsonl")
    ap.add_argument("--system", required=True, help="run folder of the full system")
    ap.add_argument("--baseline", required=True, help="run folder of the baseline (B2-none for H3)")
    ap.add_argument("--margin", type=float, default=0.05)
    ap.add_argument("--n-boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    result = compare(read_jsonl(a.items, LabelledItem), read_jsonl(Path(a.system) / "preds.jsonl", Prediction),
                     read_jsonl(Path(a.baseline) / "preds.jsonl", Prediction), a.margin, a.n_boot, a.seed)
    result = {"system": Path(a.system).name, "baseline": Path(a.baseline).name} | result
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    main()
