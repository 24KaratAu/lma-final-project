"""Pilot (PLAN.md section 2, Gate 0 item 1): frontier models read whole planted pilot deeds.

python -m src.eval.pilot --models claude-sonnet-5-5 claude-opus-5-5 --out runs/pilot

One fresh call per deed and model, same neutral prompt. Raw answers are saved. A flagged clause
is matched to a planted item by the words it quotes; misses are void items not flagged void,
false alarms are valid or hand-off items flagged void. Flags on unplanted clauses are listed, not scored.
"""

import argparse
import json
import re
from pathlib import Path

from src.common.jsonl import read_jsonl
from src.common.schemas import LabelledItem
from src.eval.stub_leases import ANCHORS, cut, deed
from src.models.generate import generate

PROMPT = """You are reviewing an Indian commercial lease deed for clauses that are void, wholly or partly, under section 27 (restraint of trade) or section 28 (restraint of legal proceedings, including time limits on rights) of the Indian Contract Act, 1872.

Read the whole deed. List every clause you consider void under either section. Do not list clauses that are valid.

Reply with one JSON array only, one object per clause:
[{{"clause": "clause number as printed", "quote": "the first 15 words of the clause, copied exactly", "section": "s.27 or s.28", "reason": "one sentence"}}]
Reply [] if there are none.

DEED:
{deed}"""


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def match(quote: str, clauses: dict[str, str]) -> str | None:
    """Item whose clause text contains most of the quoted words in order (at least 6 of the first 10)."""
    q = words(quote)[:10]
    best, best_n = None, 0
    for item_id, text in clauses.items():
        t = " ".join(words(text))
        n = max((k for k in range(len(q), 0, -1) for i in range(len(q) - k + 1) if " ".join(q[i:i + k]) in t), default=0)
        if n > best_n:
            best, best_n = item_id, n
    return best if best_n >= 6 else None


def parse(raw: str) -> list[dict]:
    m = re.search(r"\[.*\]", raw, re.S)
    try:
        out = json.loads(m.group(0)) if m else []
    except json.JSONDecodeError:
        return []
    return [x for x in out if isinstance(x, dict)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--out", default="runs/pilot")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    items = read_jsonl("data/pilot/answer_key.jsonl", LabelledItem)
    report = {}
    for model in args.models:
        flagged, other = set(), []
        for lease_id in sorted({it.lease_id for it in items}):
            raw_path = out / f"{model}-{lease_id}.txt"
            if not raw_path.exists():  # resume: a saved raw answer is never asked again
                [raw] = generate([PROMPT.format(deed="\n".join(deed(lease_id)))], model, backend="claude_cli")
                raw_path.write_text(raw, encoding="utf-8")
            lines = deed(lease_id)
            clauses = {it.item_id: cut(lines, *ANCHORS[it.item_id]) for it in items if it.lease_id == lease_id}
            # Fallback for planted text inside an existing clause (e.g. "cl. 12, last para."), quoted from the clause's start.
            numbers = {it.clause_id.split("-", 1)[1].upper(): it.item_id for it in items if it.lease_id == lease_id}
            for flag in parse(raw_path.read_text(encoding="utf-8")):
                item_id = match(str(flag.get("quote", "")), clauses) or numbers.get(str(flag.get("clause", "")).strip(" .").upper())
                if item_id:
                    flagged.add(item_id)
                else:
                    other.append({"lease_id": lease_id} | flag)
        void = {it.item_id for it in items if it.gold_verdict == "void"}
        rest = {it.item_id for it in items} - void
        report[model] = {
            "planted_void": len(void),
            "look_alikes": len(rest),
            "misses": sorted(void - flagged),
            "false_alarms": sorted(rest & flagged),
            "flags_on_unplanted_clauses": other,
        }
        print(model, f"misses {len(void - flagged)}/{len(void)}, false alarms {len(rest & flagged)}/{len(rest)}, other flags {len(other)}")
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
