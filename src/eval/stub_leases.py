"""Stopgap lease files for the dev set until the lease parser lands (PLAN.md section 5, Phase 1).

python -m src.eval.stub_leases --out runs/stub

Writes <out>/items.jsonl (the 20 pilot + 41 dev items) and <out>/leases/<lease_id>.json holding
only the target clauses, cut from the planted deeds by their opening words. No definitions or
cross-references, so it serves the no-retrieval runs (B1, B2) only.
"""

import argparse
import re
from pathlib import Path

from src.common.jsonl import read_jsonl, write_jsonl
from src.common.schemas import Clause, LabelledItem, Lease

# ponytail: hand-made anchors for the 61 dev items; delete this file once src/graph's lease parser gives clause ids.
# item_id -> opening words of the clause (unique in its deed), optionally the words its last line contains.
ANCHORS = {
    "PL-01": ("THE LESSEE agrees that, in consideration of THE LESSOR having agreed",),
    "PL-02": ("During the term of this Lease Deed and any renewal thereof, THE LESSEE",),
    "PL-03": ("Any claim by THE LESSEE for refund of the Interest Free Refundable",),
    "PL-04": ("The maintenance charges, operation charges and extra hour charges",),
    "PL-05": ("(g) During the Term, Lessee shall not",),
    "PL-06": ("Lessee covenants that for a period of one (1) year",),
    "PL-07": ("(d) The parties record that a difference has arisen",),
    "PL-08": ("Subject to GTC-42 above, the courts at Ranga Reddy",),
    "PL-09": ("Lessee shall notify Lessor in writing of any such damage",),
    "PL-10": ("The LESSOR agrees that during the lease period and any extension",),
    "PL-11": ("The parties agree that they intend to discharge", "of the arbitration shall be English"),
    "PL-12": ("The LESSEE shall, within thirty (30) days from the Commencement Date",),
    "PL-13": ("Any claim of the LESSOR in respect of any damage to the Schedule",),
    "PL-14": ("9.2 LESSOR No. 15 has",),
    "PL-15": ("27.1 The proceedings shall be held at Bangalore",),
    "PL-16": ("22.6 Any suit, arbitration",),
    "PL-17": ("3.3 Should the LESSEE terminate",),
    "PL-18": ("e) The Lessee shall not be entitled to institute",),
    "PL-19": ("In the event of any dispute or difference arising between the Lessors", "exclusive jurisdiction over any dispute"),
    "PL-20": ("q) Any claim by the Lessee against the Lessors",),
    "DV-01": ("The monthly rent under sub-clause (a) above has been computed",),
    "DV-02": ("During the term of the lease and any renewal thereof, the Lessee shall not use",),
    "DV-03": ("The share of the maintenance and other charges of the RTOSOA",),
    "DV-04": ("During the term of the lease and any renewal thereof, the Lessee shall not, either by itself",),
    "DV-05": ("On the termination of this lease, the Lessor shall inspect",),
    "DV-06": ("In consideration of the Lessor having agreed to renew",),
    "DV-07": ("Reference of Existing Difference",),
    "DV-08": ("Arbitration and Jurisdiction: In case of any dispute",),
    "DV-09": ("(c) The super built up area of the Demised Premises shall be measured",),
    "DV-10": ("(d) The Lessor has, under a separate agreement of even date",),
    "DV-11": ("(c) Lessee shall not be entitled to institute any suit",),
    "DV-12": ("Lessee covenants that it shall not, during the Restricted Period",),
    "DV-13": ("(h) The Lessor shall not, during the term of this Lease and for a further",),
    "DV-14": ("Notwithstanding anything contained in GTC-42, the amounts",),
    "DV-15": ("Subject to GTC-42, the courts at Pune",),
    "DV-16": ("g) That if any difference arises between the parties",),
    "DV-17": ("h) That during the lease period and any extended lease period, the Lessor",),
    "DV-18": ("c) That any dispute or difference arising between the parties",),
    "DV-19": ("d) That subject to sub-clause (c) above",),
    "DV-20": ("e) That notwithstanding sub-clause (c) above",),
    "DA-01": ("Limitation of Claims: Notwithstanding anything contained in Clause 13",),
    "DA-02": ("The Lessee shall serve a Refund Claim Notice",),
    "DA-03": ("Any claim of the Lessee for recovery of the cost of major repairs",),
    "DA-04": ("A party alleging that the other party has committed a default",),
    "DA-05": ("The Lessee shall, within fifteen (15) days of receiving the refund",),
    "DA-06": ("The Lessee shall not, during the Restricted Period, carry on",),
    "DA-07": ("The Lessor shall not, during the term of this Deed and any renewal",),
    "DA-08": ("Notwithstanding GTC-42, no claim of the Lessee",),
    "DA-09": ("(d) The Lessee shall pay the full amount of any electricity bill",),
    "DA-10": ("The Lessee shall, within ninety (90) days from the date of expiry",),
    "DA-11": ("(d) The Lessor shall not be liable under this GTC-25",),
    "DA-12": ("(g) Lessee shall not use the Demised Premises or any part thereof for the operation",),
    "DA-13": ("During the term of this Lease and any renewal thereof, the Lessee shall not, and shall procure",),
    "DA-14": ("For a period of two (2) years after the Lessee surrenders",),
    "DA-15": ("f) That any suit or other legal proceeding by the Lessor",),
    "DA-16": ("i) That if the Lessor does not object",),
    "DA-17": ("i) That the Lessee shall lodge a written claim",),
    "DA-18": ("h) That the Lessor shall, as security",),
    "DA-19": ("j) That the Lessee shall give the Lessor written notice",),
    "DA-20": ("j) That the Lessee shall not use the demised premises",),
    "DA-21": ("k) That during the lease period and any extension thereof, the Lessee",),
}
ITEMS = ["data/pilot/answer_key.jsonl", "data/dev/answer_key.jsonl"]
# A line that starts the next clause: "(d) ", "d) ", "16A.", "9.2 ", "GTC-12B:", "E.1 ".
NEXT_LABEL = re.compile(r"^\s*(\(?[a-zA-Z]{1,4}\)\s|\(?[a-zA-Z]{1,4}\)$|\d+(\.\d+)*[A-Z]?\.?(\s|$)|GTC-\d+|E\.\d)")
PAGE = re.compile(r"^\s*(Page \d+ of \d+|\d+)\s*$")


def deed(lease_id: str) -> list[str]:
    folder = "pilot" if lease_id.startswith("P") else "dev"
    return Path(f"data/{folder}/planted/{lease_id}.txt").read_text(encoding="utf-8").splitlines()


def cut(lines: list[str], start: str, until: str | None = None) -> str:
    hits = [i for i, line in enumerate(lines) if start in line]
    if len(hits) != 1:
        raise ValueError(f"{start!r} found {len(hits)} times")
    out = [lines[hits[0]].strip()]
    for line in lines[hits[0] + 1:]:
        if until:
            if until in out[-1]:
                break
            if line.strip() and not PAGE.match(line):
                out.append(line.strip())
        elif not line.strip() or NEXT_LABEL.match(line):
            break
        else:
            out.append(line.strip())
    return " ".join(out)


def build(out: Path) -> tuple[list[LabelledItem], dict[str, Lease]]:
    items = [it for path in ITEMS for it in read_jsonl(path, LabelledItem)]
    if missing := {it.item_id for it in items} ^ set(ANCHORS):
        raise ValueError(f"items and anchors differ: {sorted(missing)}")
    leases = {}
    for lease_id in sorted({it.lease_id for it in items}):
        lines = deed(lease_id)
        clauses = [
            Clause(clause_id=it.clause_id, number=it.clause_id.split("-", 1)[1], heading="", text=cut(lines, *ANCHORS[it.item_id]))
            for it in items if it.lease_id == lease_id
        ]
        leases[lease_id] = Lease(lease_id=lease_id, clauses=clauses)
    write_jsonl(out / "items.jsonl", items)
    (out / "leases").mkdir(parents=True, exist_ok=True)
    for lease_id, lease in leases.items():
        (out / "leases" / f"{lease_id}.json").write_text(lease.model_dump_json(indent=1), encoding="utf-8")
    return items, leases


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="runs/stub")
    items, leases = build(Path(ap.parse_args().out))
    print(f"{len(items)} items in {len(leases)} leases")
