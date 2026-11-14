"""Build a labelled-item set from a hand-edited worksheet (PLAN.md section 14: the test set).

python -m src.graph.items start --drafts runs/test-drafts/drafts.csv        # worksheet from the drafting job
python -m src.graph.items build --batch T1 --check                          # dry run: plant, parse, check
python -m src.graph.items build --batch T1                                  # write batch T1
python -m src.graph.items items --include data/pool                        # items.jsonl = keys + corrections

The worksheet (data/test/worksheet.csv) has one row per draft. The item writer keeps a row by filling
`keep`, `item_id` and `batch`, edits `clause`, chooses where it goes in a host deed, and writes the labels
by hand; the model's suggestions sit beside them in `suggested_*` and are never copied over. `build` then:

1. writes every kept clause of the batches keyed so far, plus this batch, into a copy of its host deed
   (data/test/planted/<lease_id>.txt), straight after clause `after` (and `support` after `support_after`);
2. parses the copies into data/leases/ and checks each clause landed under the number in `clause_id`;
3. appends the batch to answer_key.jsonl, refusing to change an item keyed in an earlier batch
   (later changes go in corrections.jsonl, PLAN.md section 13);
4. writes items.csv and the batch's blank answer sheet for the lawyer (batches/<batch>_answer_sheet_blank.csv).

Host deeds are read from the first `--hosts` folder that has <lease_id>.txt. Every labelled set that points
into the rewritten leases (dev, pool, test) is checked against the new parse before anything is written.
"""

import argparse
import csv
import json
import re
from pathlib import Path

from src.common.jsonl import read_jsonl, read_leases, write_jsonl
from src.common.schemas import LabelledItem, Lease, StatuteNode, check_items
from src.graph.lease_parser import clause_spans, parse_lease

ROOT = Path(__file__).resolve().parents[2]
COLUMNS = [
    "keep", "item_id", "batch", "draft_id", "defect_type", "family", "form", "lease_id", "after", "clause_id",
    "clause", "support_after", "support_id", "support", "verdict", "provision", "elements", "path", "notes",
    "verdict_asked", "suggested_verdict", "suggested_provision", "suggested_elements", "problems", "style", "embedded",
    "author",  # who wrote the clause and labels as kept: a team member, or a model named by its id
]
YES = {"y", "yes", "x", "1", "true"}


# -- corrections: changes to a committed answer key, one JSON object per line


def read_corrections(path: str | Path) -> list[dict]:
    """[{"item_id", "set": {field: value}, "reason", "source"}]; no file means no corrections."""
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def apply_corrections(items: list[LabelledItem], corrections: list[dict]) -> list[LabelledItem]:
    by_id = {it.item_id: it for it in items}
    for c in corrections:
        if c["item_id"] not in by_id:
            raise ValueError(f"correction for unknown item {c['item_id']}")
        by_id[c["item_id"]] = LabelledItem.model_validate(by_id[c["item_id"]].model_dump() | c["set"])
    return [by_id[it.item_id] for it in items]


# -- worksheet


def read_worksheet(path: str | Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def start_worksheet(drafts_csv: str | Path) -> list[dict]:
    """One row per draft, clean drafts first (the order of drafts.csv), label columns left empty."""
    rows = []
    with open(drafts_csv, newline="", encoding="utf-8") as f:
        for d in csv.DictReader(f):
            definitions = json.loads(d["definitions"] or "[]")
            elements = json.loads(d["suggested_elements"] or "{}")
            rows.append(
                {c: "" for c in COLUMNS}
                | {
                    "draft_id": d["draft_id"],
                    "defect_type": d["defect_type"],
                    "family": d["family"],
                    "form": d["form"],
                    "clause": d["clause"],
                    "support": "\n".join(definitions),
                    "verdict_asked": d["verdict_asked"],
                    "suggested_verdict": d["suggested_verdict"],
                    "suggested_provision": d["suggested_provision"],
                    "suggested_elements": "; ".join(f"{k}={v}" for k, v in elements.items()),
                    "problems": "; ".join(json.loads(d["problems"] or "[]")),
                    "style": d["style"],
                    "embedded": d["embedded"],
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows([{c: r.get(c, "") for c in columns} for r in rows])


def parse_elements(s: str) -> dict[str, str]:
    """'restrained_party=tenant; window=after_term' or a JSON object."""
    if s.startswith("{"):
        return json.loads(s)
    out = {}
    for part in filter(None, (p.strip() for p in s.split(";"))):
        name, _, value = part.partition("=")
        if not value:
            raise ValueError(f"element {part!r} is not name=value")
        out[name.strip()] = value.strip()
    return out


def section_of(provision: str) -> str:
    return "-".join(provision.split("-")[:2])


def to_item(row: dict) -> LabelledItem:
    lease = row["lease_id"]
    provision = row["provision"] or None
    support = [f"{lease}-{s}" for s in row["support_id"].split()]
    if row["path"]:
        path = [p if p.startswith("ICA-") or p.startswith(f"{lease}-") else f"{lease}-{p}" for p in row["path"].split()]
    else:
        path = support + ([section_of(provision)] + ([provision] if provision != section_of(provision) else []) if provision else [])
    return LabelledItem(
        item_id=row["item_id"],
        lease_id=lease,
        clause_id=f"{lease}-{row['clause_id']}",
        defect_type=row["defect_type"],
        form=row["form"],
        phrasing_family=row["family"],
        gold_verdict=row["verdict"],
        gold_provision=provision,
        gold_elements=parse_elements(row["elements"]),
        gold_path=path,
    )


# -- planting


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def plant(text: str, lease_id: str, inserts: list[tuple[str, str]]) -> str:
    """Write each (after, block) into the deed straight after clause `after`, in the order given."""
    spans = clause_spans(text, lease_id)
    lines = text.splitlines()
    at: dict[int, list[str]] = {}
    for after, block in inserts:
        if after not in spans:
            raise ValueError(f"{lease_id}: no clause {after!r} to insert after")
        at.setdefault(spans[after][1], []).append(block)
    for end in sorted(at, reverse=True):
        new = [""]
        for block in at[end]:
            new += block.strip("\n").splitlines() + [""]
        lines[end:end] = new
    return "\n".join(lines) + "\n"


def check_landed(lease: Lease, number: str, block: str, what: str) -> None:
    """The clause parsed under `number` holds the end of the block written for it (its number aside)."""
    tail = " ".join(_norm(block).split()[1:])[-60:]
    clause = next((c for c in lease.clauses if c.number == number), None)
    if clause is None:
        found = [c.number for c in lease.clauses if tail in c.text]
        raise ValueError(f"{what}: {lease.lease_id} has no clause {number!r} after planting (the text landed in {found or 'no clause'})")
    if tail not in clause.text:
        raise ValueError(f"{what}: clause {lease.lease_id}-{number} does not hold the text written for it")


def cite(item: LabelledItem) -> str:
    return "cl. " + item.clause_id.removeprefix(f"{item.lease_id}-")


def build(rows: list[dict], batch: str, folder: Path, hosts: list[Path], leases_dir: Path, nodes: list[StatuteNode],
          other_sets: list[list[LabelledItem]], write: bool) -> dict:
    key_path = folder / "answer_key.jsonl"
    keyed = read_jsonl(key_path, LabelledItem) if key_path.exists() else []
    keyed_ids = {it.item_id for it in keyed}
    kept = [r for r in rows if r["keep"].lower() in YES]
    for r in kept:
        missing = [c for c in ("item_id", "batch", "lease_id", "after", "clause_id", "clause", "verdict") if not r[c]]
        if missing:
            raise ValueError(f"{r['item_id'] or r['draft_id']}: fill {', '.join(missing)}")
    ids = [r["item_id"] for r in kept]
    if dupes := sorted({i for i in ids if ids.count(i) > 1}):
        raise ValueError(f"item_id used twice: {dupes}")
    if lost := sorted(keyed_ids - set(ids)):
        raise ValueError(f"keyed items missing from the worksheet: {lost}")
    rows_now = [r for r in kept if r["item_id"] in keyed_ids or r["batch"] == batch]
    if not any(r["batch"] == batch for r in rows_now):
        raise ValueError(f"no kept rows in batch {batch!r}")

    # 1-2: plant and parse
    by_lease: dict[str, list[dict]] = {}
    for r in rows_now:
        by_lease.setdefault(r["lease_id"], []).append(r)
    planted, new_leases = {}, {}
    for lease_id, lease_rows in sorted(by_lease.items()):
        src = next((h / f"{lease_id}.txt" for h in hosts if (h / f"{lease_id}.txt").exists()), None)
        if src is None:
            raise ValueError(f"no host deed {lease_id}.txt in {', '.join(map(str, hosts))}")
        inserts = []
        for r in lease_rows:
            if r["support"]:
                if not (r["support_after"] and r["support_id"]):
                    raise ValueError(f"{r['item_id']}: support text needs support_after and support_id")
                inserts.append((r["support_after"], r["support"]))
            inserts.append((r["after"], r["clause"]))
        text = plant(src.read_text(encoding="utf-8"), lease_id, inserts)
        lease = parse_lease(text, lease_id)
        for r in lease_rows:
            check_landed(lease, r["clause_id"], r["clause"], r["item_id"])
            if r["support"]:
                check_landed(lease, r["support_id"].split()[0], r["support"], f"{r['item_id']} support")
        planted[lease_id], new_leases[lease_id] = text, lease

    # 3: labels; earlier batches must not change
    items = [to_item(r) for r in rows_now]
    by_id = {it.item_id: it for it in items}
    changed = [it.item_id for it in keyed if by_id[it.item_id] != it]
    if changed:
        raise ValueError(f"already keyed, change them in corrections.jsonl instead: {changed}")
    leases = read_leases(leases_dir) | new_leases
    check_items(items, leases, nodes)
    for other in other_sets:  # dev and pool items that point into a rewritten lease still resolve
        check_items([it for it in other if it.lease_id in new_leases], leases, nodes)
    new = [it for it in items if it.item_id not in keyed_ids]
    report = {"batch": batch, "new_items": len(new), "keyed_before": len(keyed), "leases": sorted(new_leases)}
    if not write:
        return report

    # 4: write
    (folder / "planted").mkdir(parents=True, exist_ok=True)
    for lease_id, text in planted.items():
        (folder / "planted" / f"{lease_id}.txt").write_text(text, encoding="utf-8")
        (leases_dir / f"{lease_id}.json").write_text(new_leases[lease_id].model_dump_json(indent=1), encoding="utf-8")
    write_jsonl(key_path, keyed + new)
    all_items = keyed + new
    write_csv(folder / "items.csv", [{"item_id": it.item_id, "lease_id": it.lease_id, "clause": cite(it)} for it in all_items],
              ["item_id", "lease_id", "clause"])
    write_csv(folder / "batches" / f"{batch}_answer_sheet_blank.csv",
              [{"item_id": it.item_id, "lease_id": it.lease_id, "clause": cite(it)} for it in new],
              ["item_id", "lease_id", "clause", "answer", "section_or_exception", "reason"])
    return report


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start", help="start the worksheet from the drafting job's drafts.csv")
    s.add_argument("--drafts", required=True)
    s.add_argument("--dir", default="data/test")
    s.add_argument("--force", action="store_true", help="overwrite an existing worksheet")
    b = sub.add_parser("build", help="plant a batch, check it, and append it to the answer key")
    b.add_argument("--batch", required=True)
    b.add_argument("--dir", default="data/test")
    b.add_argument("--hosts", nargs="+", default=["data/test/leases", "data/pool/planted"],
                   help="folders holding the host deeds, first match wins")
    b.add_argument("--leases", default="data/leases")
    b.add_argument("--check", action="store_true", help="dry run: write nothing")
    i = sub.add_parser("items", help="items.jsonl = answer key + corrections")
    i.add_argument("--dir", default="data/test")
    i.add_argument("--include", nargs="*", default=[], help="other keyed folders to put first (answer_key.jsonl + corrections.jsonl)")
    i.add_argument("--leases", default="data/leases")
    args = ap.parse_args(argv)
    folder = Path(args.dir)

    if args.cmd == "start":
        out = folder / "worksheet.csv"
        if out.exists() and not args.force:
            raise SystemExit(f"{out} exists; it holds your edits. Pass --force to overwrite it.")
        rows = start_worksheet(args.drafts)
        write_csv(out, rows, COLUMNS)
        print(f"{out}: {len(rows)} drafts")
        return
    nodes = read_jsonl(ROOT / "data/statute/nodes.jsonl", StatuteNode)
    if args.cmd == "build":
        dev = read_jsonl(ROOT / "data/dev/items.jsonl", LabelledItem)
        pool = apply_corrections(read_jsonl(ROOT / "data/pool/answer_key.jsonl", LabelledItem),
                                 read_corrections(ROOT / "data/pool/corrections.jsonl"))
        report = build(read_worksheet(folder / "worksheet.csv"), args.batch, folder, [Path(h) for h in args.hosts],
                       Path(args.leases), nodes, [dev, pool], write=not args.check)
        print(json.dumps(report, indent=2) + ("\n(dry run: nothing written)" if args.check else ""))
        return
    items = []
    for d in [*map(Path, args.include), folder]:
        items += apply_corrections(read_jsonl(d / "answer_key.jsonl", LabelledItem), read_corrections(d / "corrections.jsonl"))
    check_items(items, read_leases(args.leases), nodes)
    write_jsonl(folder / "items.jsonl", items)
    print(f"{folder / 'items.jsonl'}: {len(items)} items")


if __name__ == "__main__":
    main()
