"""Gate 0 pilot (PLAN.md section 2): a frontier model reads each whole planted lease and flags void clauses.

python -m src.baselines.pilot --models claude-opus-5-5 claude-sonnet-5-5

One fresh Claude Code print-mode call per lease and model, tools off, the same neutral prompt
(it does not say clauses were planted). Every raw answer is saved under runs/pilot-<model>/.
A flag counts for an item when the quoted opening words of the flagged clause appear in the
item's clause. Misses: void items not flagged. False alarms: valid or hand-off items flagged.
"""

import argparse
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from src.common.jsonl import read_jsonl, read_leases
from src.common.schemas import LabelledItem

SYSTEM = "You are a careful Indian commercial lawyer reviewing lease deeds. Answer only with JSON."
PROMPT = """Read the lease deed below. List every clause that is void, or void to an extent, under Section 27 \
(restraint of trade) or Section 28 (restraint of legal proceedings, including time limits on enforcing rights) of \
the Indian Contract Act, 1872. Do not list clauses that are valid or that you cannot decide.

Reply with a JSON list only, one object per clause:
[{{"clause": "<the clause number as the deed writes it>", "quote": "<the first 12 words of the clause, copied exactly>", \
"section": "27" or "28", "reason": "<one sentence>"}}]

LEASE DEED:
{deed}"""


def call(model: str, deed: str) -> dict:
    exe = shutil.which("claude") or "claude"
    cmd = [exe, "-p", "--tools", "", "--model", model, "--output-format", "json", "--system-prompt", SYSTEM]
    res = subprocess.run(cmd, input=PROMPT.format(deed=deed), capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(res.stdout)


def flags(result_text: str) -> list[dict]:
    m = re.search(r"\[.*\]", result_text, re.S)
    try:
        out = json.loads(m.group(0)) if m else []
    except json.JSONDecodeError:
        return []
    return [f for f in out if isinstance(f, dict)]


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def matches(quote: str, clause_text: str, n: int = 6) -> bool:
    """The first n words of the quote appear, in order and together, in the clause."""
    q = _words(quote)[:n]
    return bool(q) and f" {' '.join(q)} " in f" {' '.join(_words(clause_text))} "


def score(items: list[LabelledItem], leases: dict, flagged: dict[str, list[dict]]) -> dict:
    rows, tp, fn, fp = [], 0, 0, 0
    for it in items:
        text = next(c.text for c in leases[it.lease_id].clauses if c.clause_id == it.clause_id)
        hit = any(matches(f.get("quote", ""), text) for f in flagged.get(it.lease_id, []))
        gold_void = it.gold_verdict == "void"
        tp += gold_void and hit
        fn += gold_void and not hit
        fp += hit and not gold_void
        rows.append({"item_id": it.item_id, "gold": it.gold_verdict, "flagged": hit})
    n_void = sum(it.gold_verdict == "void" for it in items)
    matched = {(lid, i) for lid, fs in flagged.items() for i, f in enumerate(fs)
               if any(matches(f.get("quote", ""), next(c.text for c in leases[it.lease_id].clauses if c.clause_id == it.clause_id))
                      for it in items if it.lease_id == lid)}
    other = sum(len(fs) for fs in flagged.values()) - len(matched)
    return {"void_items": n_void, "caught": tp, "missed": fn, "lookalikes": len(items) - n_void,
            "false_alarms": fp, "other_flags": other, "items": rows}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["claude-opus-5-5", "claude-sonnet-5-5"])
    ap.add_argument("--items", default="data/pilot/answer_key.jsonl")
    ap.add_argument("--planted", default="data/pilot/planted")
    ap.add_argument("--leases", default="data/leases")
    ap.add_argument("--out", default="runs")
    args = ap.parse_args(argv)
    items = read_jsonl(args.items, LabelledItem)
    leases = read_leases(args.leases)
    version = subprocess.run([shutil.which("claude") or "claude", "--version"], capture_output=True, text=True).stdout.strip()
    summary = {}
    for model in args.models:
        run_dir = Path(args.out) / f"pilot-{model}"
        run_dir.mkdir(parents=True, exist_ok=True)
        flagged = {}
        for lease_id in sorted({it.lease_id for it in items}):
            raw_path = run_dir / f"{lease_id}.json"
            if not raw_path.exists():  # resume: never pay twice for the same lease
                raw = call(model, (Path(args.planted) / f"{lease_id}.txt").read_text(encoding="utf-8"))
                raw_path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
            flagged[lease_id] = flags(json.loads(raw_path.read_text())["result"])
            print(f"{model} {lease_id}: {len(flagged[lease_id])} clauses flagged", flush=True)
        result = score(items, leases, flagged)
        result |= {"model": model, "claude_code": version, "date": datetime.now(timezone.utc).isoformat()}
        (run_dir / "score.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        summary[model] = {k: v for k, v in result.items() if k != "items"}
        print(json.dumps(summary[model]))
    return summary


if __name__ == "__main__":
    main()
