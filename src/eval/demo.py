"""A readable walk-through of one test clause, and of the results, for the demo and the viva.

python -m src.eval.demo clause TE-017      # one clause: lease links and statute search run live, then the logged decision
python -m src.eval.demo results            # the test results in plain words, with H3 recomputed
python -m src.eval.demo clause TE-017 --slow   # print line by line (for screen recordings)

Runs on a laptop CPU. The tools (lease and statute graph) run live; the model's decisions are read from
the logged test runs in runs/test/, because the model needs a GPU. Nothing here changes any file.
"""

import argparse
import json
import sys
import textwrap
import time
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from src.agent.tools import Toolbox, load_statute
from src.common.jsonl import read_jsonl, read_leases
from src.common.schemas import LabelledItem, Prediction

WIDTH = 96
FULL = "agent-controller-test"
NAMES = {
    "B1-none-test": "Small model alone (B1)",
    "B1-flat-test": "Small model + flat statute search",
    "B1-graph-test": "Small model + statute graph",
    "agent-fixed-noadapter-test": "Agent, fixed order, no fine-tuning",
    "agent-fixed-test": "Agent, fixed order, fine-tuned verifier",
    FULL: "Full system (agent + fine-tuned verifier)",
    "B2-none-test": "Frontier model alone (B2)",
    "B2-flat-test": "Frontier model + flat statute search",
}
VERDICT = {"void": "VOID", "valid": "VALID", "handoff": "HAND OFF"}
STEP = {
    "get_clause": lambda a: f"read clause {a.get('clause_id')}",
    "lookup_definition": lambda a: f"looked up \"{a.get('term')}\"",
    "search_graph": lambda a: "searched the statute",
    "expand": lambda a: f"followed the links from {a.get('node_id')}",
}

B, DIM, END = "\033[1m", "\033[2m", "\033[0m"
COLOUR = {"void": "\033[1;31m", "valid": "\033[1;32m", "handoff": "\033[1;33m", "head": "\033[1;36m", "ok": "\033[1;32m", "bad": "\033[1;31m"}
SLOW = False


def out(line: str = "", pause: float = 0.0) -> None:
    print(line, flush=True)
    if SLOW:
        time.sleep(0.05 + pause)


def head(title: str) -> None:
    out(f"{COLOUR['head']}━━ {title} {'━' * max(3, WIDTH - len(title) - 4)}{END}")


def section(n: int, title: str, where: str) -> None:
    out(pause=0.6 if n > 1 else 0.0)
    out(f"{B}{n}. {title}{END}  {DIM}{where}{END}", 0.3)


def wrap(text: str, indent: int = 4) -> list[str]:
    return textwrap.wrap(" ".join(text.split()), WIDTH - indent)


def verdict(v: str | None) -> str:
    return f"{COLOUR.get(v, '')}{VERDICT.get(v, str(v))}{END}"


def title_of(node) -> str:
    return node.text.split(".—")[0].strip().rstrip(".")


def rnd(x: float, places: int) -> str:
    """Round half up, as in the report (0.8065 -> 0.807)."""
    return str(Decimal(str(x)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def short(text: str, n: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _jsonl(path: Path) -> dict[str, dict]:
    return {json.loads(line)["item_id"]: json.loads(line) for line in open(path)} if path.exists() else {}


def clause(item_id: str, items: str, leases: str, runs: Path) -> int:
    gold = {i.item_id: i for i in read_jsonl(items, LabelledItem)}
    if item_id not in gold:
        print(f"no item {item_id} in {items}", file=sys.stderr)
        return 1
    g = gold[item_id]
    lease = read_leases(leases)[g.lease_id]
    nodes, edges = load_statute()
    tools = Toolbox(lease, nodes, edges)
    c = tools.clauses[g.clause_id]

    head(f"Clause {item_id} · deed {g.lease_id}, clause {c.number}")
    for line in wrap(f"“{c.text}”"):
        out("    " + line)

    section(1, "What the clause depends on", "lease graph, live")
    terms = [d.term for d in lease.definitions if d.term in c.text]
    if not terms:
        out(f"    {DIM}No term from this deed's definitions list appears in the clause.{END}")
    for term in dict.fromkeys(terms):
        found = tools.lookup_definition(term).get("definitions", [{}])[0]
        where = tools.clauses[found["clause_id"]].number if found.get("clause_id") in tools.clauses else "?"
        out(f"    {B}{term}{END}  {DIM}(clause {where}){END}")
        out(f"      {short(found.get('text', ''), WIDTH - 6)}", 0.2)

    section(2, "Which law applies", "statute graph search on the clause text, live")
    for n in tools.search_graph(c.text)["nodes"][:3]:
        node = tools.nodes[n["id"]]
        out(f"    {n['id']:<10} {node.label}: {short(title_of(node), WIDTH - 16 - len(node.label))}", 0.15)

    trace = _jsonl(runs / FULL / "traces.jsonl").get(item_id)
    config = runs / FULL / "config.json"
    commit = json.load(open(config))["git_commit"][:7] if config.exists() else "?"
    section(3, "What the full system decided", f"logged run on Kaggle (2 x T4), commit {commit}")
    if trace is None:
        out(f"    {DIM}No logged run found in {runs / FULL}.{END}")
    else:
        steps = [STEP.get(t["tool"], lambda a: str(t["tool"]))(t["args"]) for t in trace["transcript"] if t["tool"]]
        for line in textwrap.wrap(f"The agent {', then '.join(steps) or 'went straight to the verifier'}.", WIDTH - 4):
            out("    " + line, 0.1)
        v = trace["verify"]
        out(f"    Verdict:  {verdict(v['verdict'])}   provision: {B}{v.get('provision') or '–'}{END}", 0.2)
        facts = v.get("elements", {})
        if facts:
            out("    Facts found:")
            for k, x in facts.items():
                out(f"      {k.replace('_', ' ') + ':':<26}{str(x).replace('_', ' ')}", 0.1)
        elif v.get("defect_type") == "out_of_scope":
            out("    Facts found: none. The verifier judged the clause to be outside ss.27–28.")

    section(4, "Checked against the lawyer's label", "blind answer, data/test/items.jsonl")
    mine = trace["verify"]["verdict"] if trace else None
    mark = f"{COLOUR['ok']}✓ correct{END}" if mine == g.gold_verdict else f"{COLOUR['bad']}✗ wrong{END}"
    out(f"    Lawyer:   {verdict(g.gold_verdict)}   provision: {B}{g.gold_provision or '–'}{END}     {mark if trace else ''}", 0.3)
    others = []
    for run in ("B1-none-test", "B2-none-test"):
        p = _jsonl(runs / run / "preds.jsonl").get(item_id)
        if p:
            tick = f"{COLOUR['ok']}✓{END}" if p["verdict"] == g.gold_verdict else f"{COLOUR['bad']}✗{END}"
            others.append(f"{NAMES[run]}: {verdict(p['verdict'])} {tick}")
    if others:
        out("    " + "    ".join(others))
    out()
    return 0


def results(items: str, runs: Path) -> int:
    from src.eval.compare import compare

    found = [r for r in NAMES if (runs / r / "metrics.json").exists()]
    if not found:
        print(f"no runs found in {runs}", file=sys.stderr)
        return 1
    n = json.load(open(runs / found[0] / "metrics.json"))["overall"]["n"]
    head(f"Results on the test set: {n} clauses, scored against the lawyer's labels")
    out()
    out(f"    {'':<44}{'accuracy':>9}   {'defect F1':<9}")
    for r in found:
        m = json.load(open(runs / r / "metrics.json"))["overall"]
        bar = "█" * round((m["defect_f1"] - 0.75) * 150)
        style = B if r in (FULL, "B2-none-test") else ""
        out(f"    {style}{NAMES[r]:<44}{rnd(m['verdict_accuracy'], 2):>9}   {rnd(m['defect_f1'], 3)}{END}  {DIM}{bar}{END}", 0.15)
    if FULL in found and "B2-none-test" in found:
        gold = read_jsonl(items, LabelledItem)
        h3 = compare(gold, read_jsonl(runs / FULL / "preds.jsonl", Prediction),
                     read_jsonl(runs / "B2-none-test" / "preds.jsonl", Prediction))
        lo, hi = h3["ci95"]
        out(pause=0.8)
        out(f"{B}H3, fixed before testing:{END} is the full system within 0.05 defect F1 of the frontier model?", 0.3)
        out(f"    Difference {h3['difference']:+.3f}  (95% paired-bootstrap interval {lo:+.3f} to {hi:+.3f})", 0.3)
        answer = f"{COLOUR['ok']}Yes{END}" if h3["within_margin"] else f"{COLOUR['bad']}No: H3 is not supported{END}"
        out(f"    {answer}")
    out()
    return 0


def main(argv=None) -> int:
    global SLOW
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["clause", "results"])
    ap.add_argument("item_id", nargs="?")
    ap.add_argument("--items", default="data/test/items.jsonl")
    ap.add_argument("--leases", default="data/leases")
    ap.add_argument("--runs", default="runs/test", help="folder with the logged test runs")
    ap.add_argument("--slow", action="store_true", help="print line by line")
    a = ap.parse_args(argv)
    SLOW = a.slow
    if a.what == "clause":
        if not a.item_id:
            ap.error("clause needs an item id, e.g. TE-017")
        return clause(a.item_id, a.items, a.leases, Path(a.runs))
    return results(a.items, Path(a.runs))


if __name__ == "__main__":
    sys.exit(main())
