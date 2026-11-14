"""Ruling nodes and `interprets` edges from the rulings sheet (PLAN.md section 7).

python -m src.graph.rulings            # add the read rulings to data/statute/nodes.jsonl and edges.jsonl
python -m src.graph.rulings --check    # report what would change, write nothing

The sheet (data/statute/rulings.csv) has one row per judgment. A row becomes a ruling node only once a
person has read the judgment and filled in `holding` (one sentence, in their own words), `source_url`,
`read_by` and `read_on`. `lawyer_note` is the lawyer's one-line summary from Session 1, a pointer for the
reader, and never goes into the graph. No edge is added without a human reading the ruling.

Each read row gives a node {"id": "RUL-07", "type": "ruling", "label": "<case> <citation>", "text": <holding>}
and one edge per provision in `interprets` (";"-separated): {"src": "RUL-07", "dst": "ICA-28",
"type": "interprets", "source": "manual"}. Rerunning replaces every ruling node and `interprets` edge, so
the graph always matches the sheet.
"""

import argparse
import csv
from pathlib import Path

from src.common.jsonl import read_jsonl, write_jsonl
from src.common.schemas import StatuteEdge, StatuteNode

ROOT = Path(__file__).resolve().parents[2]
SHEET = ROOT / "data/statute/rulings.csv"
STATUTE = ROOT / "data/statute"
COLUMNS = ["ruling_id", "case", "citation", "interprets", "limb", "lawyer_note", "holding", "source_url", "read_by", "read_on"]
READ = ("holding", "source_url", "read_by", "read_on")  # all four filled = read by a person
INTERPRETED_TYPES = ("section", "exception", "explanation")


def read_sheet(path: str | Path = SHEET) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]
    if rows and list(rows[0]) != COLUMNS:
        raise ValueError(f"{path}: columns must be {COLUMNS}")
    return rows


def is_read(row: dict) -> bool:
    return all(row[c] for c in READ)


def ruling_graph(rows: list[dict], nodes: list[StatuteNode]) -> tuple[list[StatuteNode], list[StatuteEdge]]:
    """Ruling nodes and their `interprets` edges for the read rows. Raises on a bad row."""
    provisions = {n.id for n in nodes if n.type in INTERPRETED_TYPES}
    seen, out_nodes, out_edges = set(), [], []
    for r in rows:
        rid = r["ruling_id"]
        if not rid.startswith("RUL-") or rid in seen:
            raise ValueError(f"ruling_id {rid!r}: must start with RUL- and be unique")
        seen.add(rid)
        if not is_read(r):
            continue
        targets = [t.strip() for t in r["interprets"].split(";") if t.strip()]
        unknown = [t for t in targets if t not in provisions]
        if not targets or unknown:
            raise ValueError(f"{rid}: interprets {r['interprets']!r} must name provisions in the statute graph {unknown}")
        out_nodes.append(StatuteNode(id=rid, type="ruling", label=f"{r['case']} {r['citation']}", text=r["holding"]))
        out_edges += [StatuteEdge(src=rid, dst=t, type="interprets", source="manual") for t in targets]
    return out_nodes, out_edges


def merge(nodes: list[StatuteNode], edges: list[StatuteEdge], rows: list[dict]) -> tuple[list[StatuteNode], list[StatuteEdge]]:
    """The statute graph with its ruling nodes and `interprets` edges replaced by those from the sheet."""
    base_nodes = [n for n in nodes if n.type != "ruling"]
    base_edges = [e for e in edges if e.type != "interprets"]
    r_nodes, r_edges = ruling_graph(rows, base_nodes)
    return base_nodes + r_nodes, base_edges + r_edges


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", default=str(SHEET))
    ap.add_argument("--statute", default=str(STATUTE), help="folder holding nodes.jsonl and edges.jsonl")
    ap.add_argument("--check", action="store_true", help="report only, write nothing")
    a = ap.parse_args(argv)
    folder = Path(a.statute)
    rows = read_sheet(a.sheet)
    nodes, edges = merge(read_jsonl(folder / "nodes.jsonl", StatuteNode), read_jsonl(folder / "edges.jsonl", StatuteEdge), rows)
    read = [r["ruling_id"] for r in rows if is_read(r)]
    print(f"{len(read)} of {len(rows)} rulings read: {len([n for n in nodes if n.type == 'ruling'])} ruling nodes, "
          f"{len([e for e in edges if e.type == 'interprets'])} interprets edges")
    unread = [r["ruling_id"] for r in rows if not is_read(r)]
    if unread:
        print("not read yet (need holding, source_url, read_by, read_on): " + ", ".join(unread))
    if not a.check:
        write_jsonl(folder / "nodes.jsonl", nodes)
        write_jsonl(folder / "edges.jsonl", edges)


if __name__ == "__main__":
    main()
