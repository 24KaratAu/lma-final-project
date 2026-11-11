"""Every reported configuration on one labelled set, split into chunks that fit a Kaggle session (PLAN.md section 5, Phase 3).

python -m src.eval.run_all --items data/test/items.jsonl --list --chunks 2              # the plan: chunks and hours
python -m src.eval.run_all --items data/test/items.jsonl --chunk 1 --chunks 2 \
    --adapter /kaggle/input/.../qlora-1000/adapter --out /kaggle/working/runs             # one Kaggle session
python -m src.eval.run_all --items data/test/items.jsonl --where laptop \
    --frontier-model <model id> --frontier-backend <backend> --out runs                   # B2 (frontier) on the laptop
python -m src.eval.run_all --table runs                                                  # results table from metrics.json

Each configuration is one src.eval.run call with a fixed run id, so rerunning a chunk after a
cutoff resumes where it stopped. Decoding is greedy, so repeat runs give the same answers;
seeds only matter for training. Configurations that need an adapter are skipped without one.
"""

import argparse
import json
from pathlib import Path

from src.common.jsonl import read_jsonl
from src.common.schemas import LabelledItem
from src.eval import run

OPEN = "Qwen/Qwen2.5-7B-Instruct"

# name, where, runner arguments, model calls per item (for the time estimate)
CONFIGS = [
    ("B1-none", "kaggle", ["--agent", "pipeline", "--mode", "none"], 1),
    ("B1-flat", "kaggle", ["--agent", "pipeline", "--mode", "flat"], 1),
    ("agent-fixed-noadapter", "kaggle", ["--agent", "fixed"], 1),
    ("agent-fixed", "kaggle", ["--agent", "fixed", "ADAPTER"], 1),
    ("agent-controller", "kaggle", ["--agent", "controller", "REASONING", "ADAPTER"], 6),
    ("B2-none", "laptop", ["--agent", "pipeline", "--mode", "none"], 1),
    ("B2-flat", "laptop", ["--agent", "pipeline", "--mode", "flat"], 1),
]
SECONDS_PER_CALL = {"kaggle": 10.0, "laptop": 15.0}  # 7B on a T4, unbatched with long prompts: 8.2 s measured (section 9)


def plan(n_items: int, adapter: str | None, where: str = "kaggle") -> list[dict]:
    out = []
    for name, place, args, calls in CONFIGS:
        if place != where or ("ADAPTER" in args and not adapter):
            continue
        out.append({"name": name, "args": args, "hours": round(n_items * calls * SECONDS_PER_CALL[place] / 3600, 2)})
    return out


def chunk(configs: list[dict], chunks: int) -> list[list[dict]]:
    """Longest first, each into the chunk with the fewest hours so far."""
    bins = [[] for _ in range(chunks)]
    for c in sorted(configs, key=lambda c: -c["hours"]):
        min(bins, key=lambda b: sum(x["hours"] for x in b)).append(c)
    return bins


def argv_for(cfg: dict, a) -> list[str]:
    model, backend = (a.frontier_model, a.frontier_backend) if cfg["name"].startswith("B2") else (OPEN, "hf")
    args = []
    for x in cfg["args"]:
        if x == "ADAPTER":
            args += ["--adapter", a.adapter]
        elif x == "REASONING":
            args += ["--reasoning", a.reasoning]
        else:
            args.append(x)
    return ["--items", a.items, "--leases", a.leases, "--model", model, "--backend", backend,
            "--run-id", f"{cfg['name']}-{Path(a.items).parent.name}", "--out", a.out] + args


def table(runs: str) -> str:
    """One row per run: overall scores, then accuracy on cross-clause items."""
    cols = ["verdict_accuracy", "defect_recall", "defect_precision", "defect_f1", "false_alarm_rate", "citation_correct", "section_recall@5"]
    rows = ["| Run | n | " + " | ".join(cols) + " | cross-clause accuracy |", "|" + "---|" * (len(cols) + 3)]
    for m in sorted(Path(runs).glob("*/metrics.json")):
        res = json.loads(m.read_text())
        o, cross = res["overall"], res.get("form=cross", {})
        fmt = lambda v: "–" if v is None else f"{v:.2f}"
        rows.append(f"| {m.parent.name} | {o['n']} | " + " | ".join(fmt(o.get(c)) for c in cols) + f" | {fmt(cross.get('verdict_accuracy'))} |")
    return "\n".join(rows)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="data/test/items.jsonl")
    ap.add_argument("--leases", default="data/leases")
    ap.add_argument("--adapter", default=None, help="the fine-tuned verifier (qlora-<n>/adapter)")
    ap.add_argument("--reasoning", default="think", help="the controller variant chosen on dev")
    ap.add_argument("--where", default="kaggle", choices=["kaggle", "laptop"])
    ap.add_argument("--frontier-model", default=None, help="B2 model id (laptop runs)")
    ap.add_argument("--frontier-backend", default=None, help="B2 backend of src.models.generate (laptop runs)")
    ap.add_argument("--chunks", type=int, default=1)
    ap.add_argument("--chunk", type=int, default=None, help="run only this chunk (1-based)")
    ap.add_argument("--list", action="store_true", help="print the chunks and estimated hours, run nothing")
    ap.add_argument("--table", default=None, help="print the results table for the runs under this folder")
    ap.add_argument("--out", default="runs")
    a = ap.parse_args(argv)

    if a.table:
        print(table(a.table))
        return
    if a.where == "laptop" and not a.list and not (a.frontier_model and a.frontier_backend):
        ap.error("--where laptop needs --frontier-model and --frontier-backend")
    n = len(read_jsonl(a.items, LabelledItem))
    bins = chunk(plan(n, a.adapter, a.where), a.chunks)
    for i, b in enumerate(bins, 1):
        print(f"chunk {i}: {sum(c['hours'] for c in b):.1f} h estimated: " + ", ".join(f"{c['name']} ({c['hours']} h)" for c in b))
    if a.list:
        return bins
    todo = bins[a.chunk - 1] if a.chunk else [c for b in bins for c in b]
    for cfg in todo:
        print(f"== {cfg['name']}", flush=True)
        run.main(argv_for(cfg, a))
    print(table(a.out))
    return bins


if __name__ == "__main__":
    main()
