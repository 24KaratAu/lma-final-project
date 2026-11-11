"""Run the pipeline over a labelled set, log the run, and score it (PLAN.md section 11).

python -m src.eval.run --items data/dev/items.jsonl --leases data/leases \
    --model Qwen/Qwen2.5-7B-Instruct --backend hf --mode none --out runs
python -m src.eval.run ... --agent controller --reasoning think --max-steps 6     # the agent (src/agent/controller.py)

Writes runs/<run_id>/config.json, preds.jsonl and metrics.json (and traces.jsonl for the agent). Predictions
are appended as each lease finishes, so a rerun with the same --run-id
resumes after a cutoff and skips items already done.
"""

import argparse
import json
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from src.agent import controller
from src.agent.pipeline import run_agent
from src.common.jsonl import read_jsonl, read_leases
from src.common.schemas import LabelledItem, Prediction
from src.eval.score import score
from src.models.generate import generate
from src.models.verify import make_verify


def _gpu() -> tuple[str, int]:
    try:
        import torch

        n = torch.cuda.device_count()
        return (torch.cuda.get_device_name(0) if n else "none"), n
    except ImportError:
        return "none", 0


def _peak_gb() -> float | None:
    """Peak GPU memory over all devices, for the base-model choice (fits a 16 GB T4? an 11 GB Ada GPU?)."""
    try:
        import torch

        return round(sum(torch.cuda.max_memory_allocated(i) for i in range(torch.cuda.device_count())) / 2**30, 2) or None
    except ImportError:
        return None


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        # Kaggle copy made with `git archive --add-virtual-file=COMMIT:<hash>` has no .git
        return Path("COMMIT").read_text().strip() if Path("COMMIT").exists() else "unknown"


def _no_retrieval(clause_id, lease, mode="none", k=5):
    return {"nodes": [], "path": []}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True)
    ap.add_argument("--leases", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--backend", default="hf", choices=["hf", "claude_cli", "mock"])
    ap.add_argument("--mode", default="none", choices=["none", "flat", "graph"], help="retrieval for --agent pipeline")
    ap.add_argument("--agent", default="pipeline", choices=["pipeline", "fixed", "controller"],
                    help="pipeline: one retrieve + verify; fixed: the agent's tools in a fixed order; controller: the model picks the tools")
    ap.add_argument("--reasoning", default="think", choices=sorted(controller.REASONING))
    ap.add_argument("--max-steps", type=int, default=6)
    ap.add_argument("--handoff-below", type=float, default=None, help="hand off when verify's confidence is below this")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--zero-shot", action="store_true", help="drop the few-shot examples")
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--out", default="runs")
    args = ap.parse_args(argv)

    setting = args.mode if args.agent == "pipeline" else args.agent + ("-" + args.reasoning if args.agent == "controller" else "")
    run_id = args.run_id or f"{args.model.split('/')[-1]}-{setting}-s{args.seed}-{datetime.now():%m%d-%H%M}"
    run_dir = Path(args.out) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    preds_path = run_dir / "preds.jsonl"

    gpu_type, gpu_count = _gpu()
    config = vars(args) | {
        "run_id": run_id,
        "git_commit": _commit(),
        "platform": platform.platform(),
        "gpu_type": gpu_type,
        "gpu_count": gpu_count,
        "started": datetime.now(timezone.utc).isoformat(),
    }
    (run_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    if args.agent != "pipeline" or args.mode == "none":
        retrieve = _no_retrieval
    else:
        from src.retrieval import retrieve  # Saksham's retrieve(clause_id, lease, mode, k)

    gen_kw = {"seed": args.seed} | ({"adapter": args.adapter} if args.adapter else {})
    verify = make_verify(args.model, args.backend, shots=not args.zero_shot, **gen_kw)
    # The controller picks tools with the same loaded model (and adapter, if any), greedy, so one copy fits on a T4.
    planner = lambda prompt: generate([prompt], args.model, backend=args.backend, max_new_tokens=300, **gen_kw)[0]

    items = read_jsonl(args.items, LabelledItem)
    leases = read_leases(args.leases)
    done = {p.item_id for p in read_jsonl(preds_path, Prediction)} if preds_path.exists() else set()

    start = time.time()
    for lease_id in sorted({it.lease_id for it in items}):
        targets = [{"item_id": it.item_id, "clause_id": it.clause_id} for it in items if it.lease_id == lease_id and it.item_id not in done]
        if not targets:
            continue
        if args.agent == "pipeline":
            preds = run_agent(leases[lease_id], {"targets": targets, "retrieve": retrieve, "verify": verify, "mode": args.mode, "k": args.k})
        else:
            log = []
            preds = controller.run_agent(leases[lease_id], {
                "targets": targets, "verify": verify, "policy": args.agent, "planner": planner, "reasoning": args.reasoning,
                "max_steps": args.max_steps, "k": args.k, "handoff_below": args.handoff_below, "log": log})
            with open(run_dir / "traces.jsonl", "a", encoding="utf-8") as f:
                f.writelines(json.dumps(t, ensure_ascii=False) + "\n" for t in log)
        with open(preds_path, "a", encoding="utf-8") as f:
            f.writelines(p.model_dump_json() + "\n" for p in preds)
        print(f"{lease_id}: {len(preds)} predictions", flush=True)

    hours = (time.time() - start) / 3600
    config |= {
        "finished": datetime.now(timezone.utc).isoformat(),
        "gpu_hours_this_session": round(hours * gpu_count, 3),
        "peak_gpu_gb": _peak_gb(),
    }
    (run_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    result = score(items, read_jsonl(preds_path, Prediction), args.k)
    (run_dir / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["overall"], indent=2))
    return run_dir


if __name__ == "__main__":
    main()
