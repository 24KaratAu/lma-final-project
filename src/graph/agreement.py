"""Agreement between the answer key and the lawyer's blind answers on the test set (PLAN.md section 14).

python -m src.graph.agreement    # print the tables in docs/legal/agreement.md

The key is the label written with each item, before the lawyer's review (data/test/answer_key.jsonl for
TE-001 - TE-270, data/pool/answer_key.jsonl for PO-01 - PO-70; neither file is edited after keying). The
lawyer answered every item blind: Batches T1-T6 (docs/legal/test_T<n>_answers.csv) and Batch B
(docs/legal/batch_b_answers.csv). Groups by defect type and form come from the final labels
(data/test/items.jsonl), so TE-140 and PO-65, out of scope in the key, count as bars on proceedings.

The lawyer's "refer" is the key's "handoff". Provision is compared two ways: at section level (s.27, s.28,
or out of scope) and with exceptions ("s.28, Exception 1" is ICA-28-E1). Kappa is Cohen's; its 95% interval
is a percentile bootstrap over items (2,000 resamples, seed 0).
"""

import csv
import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEYS = [ROOT / "data/test/answer_key.jsonl", ROOT / "data/pool/answer_key.jsonl"]
FINAL = ROOT / "data/test/items.jsonl"
LAWYER = sorted((ROOT / "docs/legal").glob("test_T*_answers.csv")) + [ROOT / "docs/legal/batch_b_answers.csv"]
TYPES = ("restraint_trade", "bar_proceedings", "time_limit", "out_of_scope")


def verdict(answer: str) -> str:
    return {"refer": "handoff"}.get(answer.strip(), answer.strip())


def provision(cited: str) -> str | None:
    """The lawyer's 's.28(a)', 's.27, Exception 1', 'outside scope (s.74)' as a node id, or None."""
    cited = cited.strip()
    if cited.startswith("outside scope"):
        return None
    base = "ICA-27" if cited.startswith("s.27") else "ICA-28"
    return f"{base}-E{cited.split('Exception')[1].strip()}" if "Exception" in cited else base


def section(node: str | None) -> str | None:
    return None if node is None else node[:6]


def kappa(pairs: list[tuple]) -> float:
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in ca) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def interval(pairs: list[tuple], resamples: int = 2000, seed: int = 0) -> tuple[float, float]:
    rng = random.Random(seed)
    vals = sorted(kappa([pairs[rng.randrange(len(pairs))] for _ in pairs]) for _ in range(resamples))
    return vals[int(0.025 * resamples)], vals[int(0.975 * resamples) - 1]


def load() -> list[dict]:
    key = {x["item_id"]: x for f in KEYS for x in map(json.loads, open(f, encoding="utf-8"))}
    final = {x["item_id"]: x for x in map(json.loads, open(FINAL, encoding="utf-8"))}
    law = {r["item_id"]: r for f in LAWYER for r in csv.DictReader(open(f, newline="", encoding="utf-8"))}
    if not set(key) == set(final) == set(law):
        raise ValueError(f"items differ: key {len(key)}, final {len(final)}, lawyer {len(law)}")
    return [{"item": i, "pool": i.startswith("PO"), "type": final[i]["defect_type"], "form": final[i]["form"],
             "key_verdict": key[i]["gold_verdict"], "lawyer_verdict": verdict(law[i]["answer"]),
             "key_provision": key[i]["gold_provision"], "lawyer_provision": provision(law[i]["section_or_exception"]),
             "final_verdict": final[i]["gold_verdict"]} for i in final]


def summary(rows: list[dict]) -> dict:
    v = [(r["key_verdict"], r["lawyer_verdict"]) for r in rows]
    s = [(section(r["key_provision"]), section(r["lawyer_provision"])) for r in rows]
    p = [(r["key_provision"], r["lawyer_provision"]) for r in rows]
    same = lambda pairs: sum(a == b for a, b in pairs)
    one_class = len({x for pair in v for x in pair}) < 2
    return {"n": len(rows), "verdict": same(v), "kappa": None if one_class else kappa(v),
            "interval": None if one_class else interval(v), "section": same(s), "section_kappa": kappa(s),
            "provision": same(p)}


def groups(rows: list[dict]) -> list[tuple[str, list[dict]]]:
    return ([("All", rows), ("New items (TE, T1-T6)", [r for r in rows if not r["pool"]]),
             ("Pool items (PO, Batch B)", [r for r in rows if r["pool"]])]
            + [(t, [r for r in rows if r["type"] == t]) for t in TYPES]
            + [(f"{f}-clause", [r for r in rows if r["form"] == f]) for f in ("single", "cross")])


def table(rows: list[dict]) -> str:
    out = ["| Group | Items | Verdict agrees | Kappa (95% interval) | Section agrees | With exceptions |",
           "|---|---|---|---|---|---|"]
    for name, sub in groups(rows):
        s = summary(sub)
        k = "–" if s["kappa"] is None else f"{s['kappa']:.3f} ({s['interval'][0]:.3f}–{s['interval'][1]:.3f})"
        out.append(f"| {name} | {s['n']} | {s['verdict']} ({s['verdict'] / s['n']:.1%}) | {k} "
                   f"| {s['section']} ({s['section'] / s['n']:.1%}) | {s['provision']} ({s['provision'] / s['n']:.1%}) |")
    return "\n".join(out)


def main():
    rows = load()
    print(table(rows))
    differ = [r for r in rows if r["key_verdict"] != r["lawyer_verdict"]]
    print(f"\nSection-level kappa, all items: {summary(rows)['section_kappa']:.3f}")
    print("\nVerdicts that differ (key -> lawyer):")
    for (k, lw), n in Counter((r["key_verdict"], r["lawyer_verdict"]) for r in differ).most_common():
        print(f"  {k} -> {lw}: {n}  " + ", ".join(r["item"] for r in differ if (r["key_verdict"], r["lawyer_verdict"]) == (k, lw)))
    print("Final label is the lawyer's blind answer:", sum(r["final_verdict"] == r["lawyer_verdict"] for r in differ),
          "| the key's:", sum(r["final_verdict"] == r["key_verdict"] for r in differ),
          "| neither:", ", ".join(r["item"] for r in differ if r["final_verdict"] not in (r["key_verdict"], r["lawyer_verdict"])))
    print("Provisions that differ:", ", ".join(f"{r['item']} ({r['key_provision']} -> {r['lawyer_provision']})"
                                              for r in rows if r["key_provision"] != r["lawyer_provision"]))


if __name__ == "__main__":
    main()
