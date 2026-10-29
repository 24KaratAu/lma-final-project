"""Generate training pairs with an open model and keep the ones that pass the rule checks.

python -m src.train.gen_pairs --n 100 --out runs/gen-trial            # the 100-pair trial (TA point 2)
python -m src.train.gen_pairs --n 3000 --out runs/gen-full            # the full pool, once the trial is reported

Writes kept.jsonl, rejected.jsonl (with reasons) and report.json (rejection rate and reasons).
"""

import argparse
import json
import random
import re
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from src.common.schemas import LabelledItem
from src.models.generate import generate
from src.models.verify import PROVISIONS, RULES, element_sheet, build_prompt, rule_verdict

CONFIG = Path(__file__).with_name("gen_config.json")


def sample_specs(cfg: dict, n: int) -> list[dict]:
    """n requests spread evenly over the families that are not held out."""
    rng = random.Random(cfg["seed"])
    families = [(dtype, fam) for dtype, fams in cfg["families"].items() for fam in fams if not fam.get("held_out")]
    specs = []
    for i in range(n):
        dtype, fam = families[i % len(families)]
        specs.append(
            {
                "pair_id": f"G-{i:05d}",
                "defect_type": dtype,
                "family": fam["id"],
                "desc": fam["desc"],
                "verdict": rng.choice(fam["verdicts"]),
                "form": "cross" if dtype != "out_of_scope" and rng.random() < cfg["cross_share"] else "single",
            }
        )
    return specs


def gen_prompt(spec: dict) -> str:
    cross = (
        "The clause must depend on a defined term or another clause of the lease to be understood "
        "(e.g. 'during the Restricted Period'); give that definition or clause text in `definitions`."
        if spec["form"] == "cross"
        else "The clause must be understandable on its own; leave `definitions` empty."
    )
    dtype = spec["defect_type"]
    if dtype == "out_of_scope":
        elements, provision = "Leave `elements` empty: {}.", "null"
    else:
        # Only this type's elements, flat; the full sheet made the model nest them under type names.
        elements = "Elements, as a flat object (use exactly these names and values):\n" + element_sheet(dtype)
        provision = '"' + '" or "'.join(sorted(PROVISIONS[dtype])) + '"'
    return "\n\n".join(
        [
            "Write one clause of an Indian commercial lease deed, in the style of a real registered deed "
            "(vary between older formal drafting and modern corporate drafting; vary names, places, numbers).",
            f"Kind of clause: {spec['desc']}.\nDefect type: {dtype}.\nIts correct verdict must be: {spec['verdict']}.\n{cross}",
            RULES,
            elements,
            "Reply with one JSON object only: "
            '{"clause": "...", "definitions": ["..."], "elements": {"name": "value", ...}, "verdict": "...", "provision": ...}'
            f"\nprovision must be exactly one of: {provision}.",
        ]
    )


def check(spec: dict, raw: str, seen: set, cfg: dict) -> tuple[dict | None, list[str]]:
    """Return (pair, []) if the output passes every rule check, else (None, reasons)."""
    match = re.search(r"\{.*\}", raw, re.S)
    try:
        out = json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        out = None
    if not isinstance(out, dict) or not isinstance(out.get("clause"), str):
        return None, ["unparseable"]

    reasons = []
    clause = out["clause"].strip()
    lo, hi = cfg["clause_words"]
    if not lo <= len(clause.split()) <= hi:
        reasons.append("length")
    elements = out.get("elements") if isinstance(out.get("elements"), dict) else {}
    if isinstance(elements.get(spec["defect_type"]), dict):  # nested under the type name: unwrap
        elements = elements[spec["defect_type"]]
    elements = {k: str(v) for k, v in elements.items()}
    try:
        LabelledItem(
            item_id=spec["pair_id"], lease_id="G", clause_id="G-1", defect_type=spec["defect_type"], form=spec["form"],
            phrasing_family=spec["family"], gold_verdict=out.get("verdict"), gold_provision=out.get("provision"),
            gold_elements=elements,
        )
    except ValidationError:
        reasons.append("schema")
    if out.get("verdict") != spec["verdict"]:
        reasons.append("wrong_verdict")
    by_rules = rule_verdict(spec["defect_type"], elements)
    if by_rules is None:
        reasons.append("elements_undecided")
    elif by_rules != out.get("verdict"):
        reasons.append("rules_disagree")
    if spec["defect_type"] != "out_of_scope" and out.get("provision") not in PROVISIONS[spec["defect_type"]]:
        reasons.append("bad_provision")
    defs = [d for d in out.get("definitions") or [] if isinstance(d, str) and d.strip()]
    if spec["form"] == "cross" and not defs:
        reasons.append("cross_without_definition")
    key = re.sub(r"\W+", " ", clause.lower()).strip()
    if key in seen:
        reasons.append("duplicate")
    if reasons:
        return None, reasons
    seen.add(key)
    pair = {k: spec[k] for k in ("pair_id", "defect_type", "family", "form")}
    return pair | {"clause": clause, "definitions": defs, "elements": elements, "verdict": out["verdict"], "provision": out.get("provision")}, []


def to_example(pair: dict) -> tuple[str, str]:
    """(prompt, target) for fine-tuning: the same element-check prompt verify() uses, zero-shot."""
    text = pair["clause"] + ("\n\nDefinitions:\n" + "\n".join(pair["definitions"]) if pair["definitions"] else "")
    target = {k: pair[k] for k in ("defect_type", "elements", "verdict", "provision")} | {"confidence": 0.9}
    return build_prompt(text, None, shots=False), json.dumps(target)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(CONFIG))
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--backend", default=None, help="override the config backend (e.g. mock)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    specs = sample_specs(cfg, args.n)
    raws = generate(
        [gen_prompt(s) for s in specs], cfg["model"], backend=args.backend or cfg["backend"],
        temperature=cfg["temperature"], max_new_tokens=cfg["max_new_tokens"], seed=cfg["seed"], batch_size=cfg.get("batch_size", 4),
    )

    kept, rejected, reasons, seen = [], [], Counter(), set()
    for spec, raw in zip(specs, raws):
        pair, why = check(spec, raw, seen, cfg)
        if pair:
            kept.append(pair)
        else:
            rejected.append(spec | {"reasons": why, "raw": raw})
            reasons.update(why)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("kept.jsonl", kept), ("rejected.jsonl", rejected)):
        with open(out / name, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    report = {
        "n": len(specs),
        "kept": len(kept),
        "rejection_rate": round(len(rejected) / len(specs), 4) if specs else None,
        "reasons": dict(reasons.most_common()),
        "kept_by_family": dict(Counter(p["family"] for p in kept)),
        "config": cfg,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("n", "kept", "rejection_rate", "reasons")}, indent=2))
    return report


if __name__ == "__main__":
    main()
