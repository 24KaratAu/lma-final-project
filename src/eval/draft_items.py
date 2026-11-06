"""Draft test clauses with an open model, for the item writer to edit by hand (PLAN.md section 14).

python -m src.eval.draft_items --out /kaggle/working/runs/test-drafts            # on Kaggle, 2x T4
python -m src.eval.draft_items --backend mock --out runs/drafts-mock              # wiring check, anywhere

Drafts `overdraw` times the test quota in src/eval/draft_config.json, spread over every
phrasing family (including those held out of training), both forms and several drafting
styles. Nothing is thrown away: each draft carries the rule-check problems found in it,
so the writer can start from the clean ones. The suggested elements, verdict and provision
are the model's; the answer key is written by hand.

Writes drafts.jsonl, drafts.csv (one row per draft, for editing), config.json (run log)
and report.json. Only the item writer opens the output before the test set is frozen.
"""

import argparse
import csv
import json
import platform
import random
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from src.eval.run import _commit, _gpu, _peak_gb
from src.models.generate import generate
from src.models.verify import PROVISIONS, RULES, element_sheet
from src.train.gen_pairs import check

CONFIG = Path(__file__).with_name("draft_config.json")


def sample_specs(cfg: dict) -> list[dict]:
    """One request per draft: the quota per type and verdict group, times `overdraw`, round-robin over the families."""
    rng = random.Random(cfg["seed"])
    specs = []
    for dtype, groups in cfg["quota"].items():
        fams = cfg["families"][dtype]
        for group, n in groups.items():
            if group == "void":
                pool = [(f, ["void"]) for f in fams if "void" in f["verdicts"]]
            else:
                pool = [(f, [v for v in f["verdicts"] if v != "void"]) for f in fams if set(f["verdicts"]) - {"void"}]
            for i in range(n * cfg["overdraw"]):
                fam, verdicts = pool[i % len(pool)]
                specs.append(
                    {
                        "draft_id": f"D-{len(specs):04d}",
                        "defect_type": dtype,
                        "family": fam["id"],
                        "desc": fam["desc"],
                        "hint": fam.get("hint", ""),
                        "held_out_of_training": fam.get("held_out_of_training", False),
                        "verdict": rng.choice(verdicts),
                        "form": "cross" if dtype != "out_of_scope" and rng.random() < cfg["cross_share"] else "single",
                        "style": rng.choice(cfg["styles"]),
                        "embedded": rng.random() < cfg["embed_share"],
                    }
                )
    return specs


def draft_prompt(spec: dict) -> str:
    dtype = spec["defect_type"]
    where = (
        "Put the operative sentence inside a longer clause that mostly deals with related, ordinary matters, "
        "so that it is not the first sentence."
        if spec["embedded"]
        else "The clause may be short or long."
    )
    cross = (
        "Whether the clause is void must depend on a defined term or another clause of the same lease "
        "(e.g. 'during the Restricted Period', 'the Expert'); write that definition or clause in `definitions`, "
        "worded as it would appear elsewhere in the deed."
        if spec["form"] == "cross"
        else "The clause must be understandable on its own; leave `definitions` empty."
    )
    if dtype == "out_of_scope":
        elements, provision = "Leave `elements` empty: {}.", "null"
    else:
        elements = "Elements, as a flat object (use exactly these names and values):\n" + element_sheet(dtype)
        provision = '"' + '" or "'.join(sorted(PROVISIONS[dtype])) + '"'
    return "\n\n".join(
        [
            "You are drafting one clause for a registered Indian commercial lease deed (office, retail, warehouse or "
            "factory premises). Use Indian names, cities, amounts in rupees and realistic periods; do not copy the "
            "examples in the rules below.",
            f"Drafting style: {spec['style']}. {where}",
            f"Kind of clause: {spec['desc']}.{' ' + spec['hint'] + '.' if spec['hint'] else ''}\n"
            f"Defect type: {dtype}.\nIts correct verdict under the rules below must be: {spec['verdict']}.\n{cross}",
            RULES,
            elements,
            "Reply with one JSON object only: "
            '{"clause": "...", "definitions": ["..."], "elements": {"name": "value", ...}, "verdict": "...", "provision": ...}'
            f"\nprovision must be exactly one of: {provision}.",
        ]
    )


def to_draft(spec: dict, raw: str, seen: set, cfg: dict) -> dict:
    """The draft with the model's suggested labels and the rule-check problems found in it (empty if none)."""
    pair, problems = check({"pair_id": spec["draft_id"]} | spec, raw, seen, cfg)
    if pair is None:
        try:
            out = json.loads(raw[raw.index("{") : raw.rindex("}") + 1])
        except ValueError:
            out = {}
        out = out if isinstance(out, dict) else {}
        pair = {
            "clause": str(out.get("clause") or raw).strip(),
            "definitions": [d for d in out.get("definitions") or [] if isinstance(d, str)],
            "elements": out.get("elements") if isinstance(out.get("elements"), dict) else {},
            "verdict": out.get("verdict"),
            "provision": out.get("provision"),
        }
    keep = ("draft_id", "defect_type", "family", "held_out_of_training", "form", "style", "embedded")
    return {k: spec[k] for k in keep} | {
        "verdict_asked": spec["verdict"],
        "clause": pair["clause"],
        "definitions": pair["definitions"],
        "suggested_elements": pair["elements"],
        "suggested_verdict": pair["verdict"],
        "suggested_provision": pair["provision"],
        "problems": problems,
    }


def write_csv(path: Path, drafts: list[dict]) -> None:
    cols = list(drafts[0]) if drafts else []
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for d in sorted(drafts, key=lambda d: (bool(d["problems"]), d["defect_type"], d["family"], d["draft_id"])):
            w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in d.items()})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(CONFIG))
    ap.add_argument("--model", default=None, help="override the config model (e.g. Qwen/Qwen2.5-7B-Instruct if 14B does not fit)")
    ap.add_argument("--backend", default=None, help="override the config backend (e.g. mock)")
    ap.add_argument("--limit", type=int, default=None, help="draft only the first N requests (quick check)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    model, backend = args.model or cfg["model"], args.backend or cfg["backend"]
    specs = sample_specs(cfg)[: args.limit]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    gpu_type, gpu_count = _gpu()
    log = {
        "run_id": out.name,
        "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": _commit(),
        "platform": platform.platform(),
        "gpu_type": gpu_type,
        "gpu_count": gpu_count,
        "model": model,
        "backend": backend,
        "seed": cfg["seed"],
        "n_requests": len(specs),
        "config": cfg,
    }
    (out / "config.json").write_text(json.dumps(log, indent=2), encoding="utf-8")

    start = time.time()
    raws = generate(
        [draft_prompt(s) for s in specs], model, backend=backend, temperature=cfg["temperature"],
        max_new_tokens=cfg["max_new_tokens"], seed=cfg["seed"], batch_size=cfg.get("batch_size", 4),
    )
    seen = set()
    drafts = [to_draft(s, r, seen, cfg) for s, r in zip(specs, raws)]
    hours = (time.time() - start) / 3600

    with open(out / "drafts.jsonl", "w", encoding="utf-8") as f:
        f.writelines(json.dumps(d, ensure_ascii=False) + "\n" for d in drafts)
    write_csv(out / "drafts.csv", drafts)
    clean = [d for d in drafts if not d["problems"]]
    report = {
        "n": len(drafts),
        "clean": len(clean),
        "problems": dict(Counter(p for d in drafts for p in d["problems"]).most_common()),
        "clean_by_family": dict(sorted(Counter(d["family"] for d in clean).items())),
        "clean_by_type_and_verdict": dict(sorted(Counter(f"{d['defect_type']}/{d['verdict_asked']}" for d in clean).items())),
    }
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    log |= {"gpu_hours_this_session": round(hours * gpu_count, 3), "peak_gpu_gb": _peak_gb()}
    (out / "config.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("n", "clean", "problems")}, indent=2))
    return report


if __name__ == "__main__":
    main()
