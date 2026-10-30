"""Section recall@k of retrieval alone, on a labelled set (PLAN.md section 5, mid-submission).

python -m src.retrieval.evaluate --items data/dev/items.jsonl --leases data/leases --modes flat dense

"exact": the gold provision (e.g. ICA-28-E1) is in the top k.
"section": some node of the gold provision's section (ICA-28, its exceptions...) is in the top k.
Items with no gold provision (out of scope) are skipped.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.common.jsonl import read_jsonl, read_leases
from src.common.schemas import LabelledItem
from src.retrieval import retrieve

KS = (1, 3, 5, 10)


def section_of(node_id: str) -> str:
    return "-".join(node_id.split("-")[:2])


def evaluate(items: list[LabelledItem], leases: dict, mode: str) -> dict:
    rows = []
    for it in items:
        if it.gold_provision is None:
            continue
        path = retrieve(it.clause_id, leases[it.lease_id], mode=mode, k=max(KS))["path"]
        rows.append((it, path))

    def recall(subset, k, section=False):
        if not subset:
            return None
        if section:
            hits = sum(any(section_of(p) == section_of(it.gold_provision) for p in path[:k]) for it, path in subset)
        else:
            hits = sum(it.gold_provision in path[:k] for it, path in subset)
        return round(hits / len(subset), 4)

    def block(subset):
        return {"n": len(subset)} | {f"exact@{k}": recall(subset, k) for k in KS} | {f"section@{k}": recall(subset, k, True) for k in KS}

    out = {"overall": block(rows)}
    for field in ("defect_type", "form"):
        for value in sorted({getattr(it, field) for it, _ in rows}):
            out[f"{field}={value}"] = block([r for r in rows if getattr(r[0], field) == value])
    out["top5"] = {it.item_id: path[:5] for it, path in rows}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="data/dev/items.jsonl")
    ap.add_argument("--leases", default="data/leases")
    ap.add_argument("--modes", nargs="+", default=["flat", "dense"])
    ap.add_argument("--out", default="runs")
    args = ap.parse_args(argv)
    items = read_jsonl(args.items, LabelledItem)
    leases = read_leases(args.leases)
    run_dir = Path(args.out) / f"retrieval-{datetime.now():%m%d-%H%M}"
    run_dir.mkdir(parents=True, exist_ok=True)
    result = {mode: evaluate(items, leases, mode) for mode in args.modes}
    (run_dir / "retrieval.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    for mode, r in result.items():
        print(mode, json.dumps(r["overall"]))
    return result


if __name__ == "__main__":
    main()
