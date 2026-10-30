"""Lease parser: deed text -> clauses, definitions and cross-references (PLAN.md section 4).

python -m src.graph.lease_parser data/pilot/planted/*.txt data/dev/planted/*.txt --out data/leases

Clause ids follow the deed's own numbering, the way the answer keys cite it:
"3(c)", "9(II)(i)", "5.5(d)", "12A", "GTC-42A" (Exhibit A of the P02/S02 deeds),
"E.1" (an exhibit's own numbering), "AI.43A" (clause 43A of Annexure I).
A clause's text includes its sub-clauses, so a parent clause can be read whole.
"""

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path

from src.common.schemas import Clause, Definition, Lease, LeaseRef

ROMAN_UP = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV",
            "XVI", "XVII", "XVIII", "XIX", "XX", "XXI", "XXII", "XXIII", "XXIV", "XXV", "XXVI", "XXVII",
            "XXVIII", "XXIX", "XXX", "XXXI", "XXXII", "XXXIII", "XXXIV", "XXXV"]
ROMAN_LO = [r.lower() for r in ROMAN_UP]

# Parts of a deed that restart the numbering. Annexures prefix their clauses ("AI.43A");
# exhibits, schedules and appendices prefix them with their letter or name.
ANNEXURE = re.compile(r"^\s*ANNEXURE\s*[—–\-:]?\s*([IVX]+|\d+)\s*$", re.I)
EXHIBIT = re.compile(r"^\s*EXHIBIT\s*[\"“']?([A-Z])[\"”']?\s*$")
SCHEDULE = re.compile(r"^\s*SCHEDULE\b[^a-z]{0,40}$")

# Clause markers at the start of a line: (kind, regex). Absolute kinds carry their whole id.
GTC = re.compile(r"^\s*GTC-([\dlO]{1,3})([A-Z]?)\s*:\s*(.*)$")  # OCR: "GTC-l3" is GTC-13
LETTERED = re.compile(r"^\s*([A-Z]\.\d+)\s+(.*)$")  # E.1, E.2 in an exhibit
SECTION = re.compile(r"^\s*SECTION\s+(\d{1,3}[A-Z]?)\.?\s+(.*)$")
DOTTED = re.compile(r"^\s*(\d{1,3}[A-Z]?(?:\.\d{1,3}[A-Z]?)+)\.?(?:\s+(.*))?$")
NUMBER = re.compile(r"^\s*(\d{1,3}[A-Z]?)\.(?:\s+(.*))?$")
UPPER_ROMAN = re.compile(r"^\s*\(([IVX]{1,6})\)(?:\s+(.*))?$")
LOWER = re.compile(r"^\s*\(?([a-z]{1,4})\)\.?(?:\s+(.*))?$")

OPERATIVE = re.compile(r"W[I1T]TNESS(?:ETH|ES AS)|NOW,? THEREFORE|NOW THIS|IT IS HEREBY (?:MUTUALLY )?AGREED|witnesseth")
DEFINITION = re.compile(r"[\"“]([A-Z][\w\s'’\-/&]{1,60}?)[\"”]\s*(?:shall\s+)?(?:means?|includes?|shall\s+have\s+the\s+meaning)")
SUBCLAUSE_REF = re.compile(r"\bsub-clauses?\s+(\([a-z]{1,4}\))(?!\s*of\b)", re.I)  # "sub-clause (a) above"
CLAUSE_REF = re.compile(
    r"\b(?:(?:sub-)?clauses?|sections?|cl\.|articles?)\s+((?:GTC-)?\d{1,3}[A-Z]?(?:\.\d{1,3}[A-Z]?)*(?:\s*\([A-Za-z]{1,6}\))*)"
    r"|\b(GTC-\d{1,3}[A-Z]?(?:\s*\([a-z]{1,4}\))*)",
    re.I,
)


@dataclass
class Node:
    kind: str
    label: str
    absolute: bool
    heading: str = ""
    lines: list[str] = field(default_factory=list)
    children: list["Node"] = field(default_factory=list)
    cid: str = ""


def _num_key(label: str) -> tuple[int, str]:
    m = re.match(r"(\d+)([A-Z]*)", label)
    return int(m.group(1)), m.group(2)


def _letter_index(s: str) -> int:
    return ord(s) - ord("a") if len(s) == 1 else -1


def _heading(text: str) -> str:
    """The clause title: text before a colon, or a short all-caps line."""
    text = text.strip()
    m = re.match(r"^([A-Z][^:.]{2,70}):", text)
    if m:
        return m.group(1).strip()
    if text and len(text) <= 80 and text.upper() == text and re.search(r"[A-Z]{3}", text):
        return text.rstrip(".").strip()
    return ""


class Parser:
    def __init__(self, lease_id: str):
        self.lease_id = lease_id
        self.root = Node("root", "", True)
        self.stack: list[Node] = [self.root]
        self.prefix = ""
        self.last_top: tuple[int, str] | None = None

    # -- stack helpers
    def _in_stack(self, kind: str) -> int | None:
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].kind == kind:
                return i
        return None

    def _place(self, node: Node) -> None:
        i = self._in_stack(node.kind)
        if i is not None:
            del self.stack[i:]
        self.stack[-1].children.append(node)
        self.stack.append(node)

    def _top(self, label: str, text: str, kind: str = "top") -> None:
        del self.stack[1:]
        node = Node(kind, self.prefix + label, True, _heading(text or ""))
        self.root.children.append(node)
        self.stack.append(node)
        if text:
            node.lines.append(text)

    def _new_part(self, prefix: str) -> None:
        self.prefix = prefix
        self.last_top = None
        del self.stack[1:]

    # -- markers
    def _expected_lower(self, label: str) -> str | None:
        """'letter' or 'roman' if `label` can start or continue a list here, else None."""
        i = self._in_stack("letter")
        prev_letter = self.stack[i].label.strip("()") if i is not None else None
        j = self._in_stack("roman")
        prev_roman = self.stack[j].label.strip("()") if j is not None else None
        if len(label) == 1 and prev_letter and _letter_index(label) == _letter_index(prev_letter) + 1:
            return "letter"
        if label in ROMAN_LO and (
            (prev_roman and ROMAN_LO.index(label) == ROMAN_LO.index(prev_roman) + 1 if prev_roman in ROMAN_LO else False)
            or label == "i"
        ):
            return "roman"
        if label == "a":
            return "letter"
        return None

    def feed(self, line: str) -> None:
        raw = line.rstrip()
        if not raw.strip() or re.search(r"\.{5,}", raw):  # blank or a table-of-contents line
            return
        if re.fullmatch(r"\s*-?\s*\d{1,3}\s*-?\s*", raw):  # page number
            return
        if m := ANNEXURE.match(raw):
            num = m.group(1)
            self._new_part(f"A{num.upper()}.")
            return
        if m := EXHIBIT.match(raw):
            self._new_part(f"{m.group(1)}.")
            return
        if SCHEDULE.match(raw) and not self.prefix.startswith("SCH"):
            self._new_part("SCH.")
            return
        if m := GTC.match(raw):
            num = m.group(1).replace("l", "1").replace("O", "0")
            self._top_absolute(f"GTC-{num}{m.group(2)}", m.group(3))
            return
        if (m := LETTERED.match(raw)) and self.prefix == f"{m.group(1)[0]}.":
            self._top_absolute(m.group(1), m.group(2))
            return
        if m := SECTION.match(raw):
            if self._accept_top(m.group(1)):
                self._top(m.group(1), m.group(2))
                return
        if m := DOTTED.match(raw):
            label = m.group(1)
            if self._accept_dotted(label):
                node = Node("dotted", self.prefix + label, True, _heading(m.group(2) or ""))
                self._place(node)
                if m.group(2):
                    node.lines.append(m.group(2))
                return
        if m := NUMBER.match(raw):
            if self._accept_top(m.group(1)):
                self._top(m.group(1), m.group(2))
                return
        if (m := UPPER_ROMAN.match(raw)) and len(self.stack) > 1:
            label = m.group(1)
            j = self._in_stack("uroman")
            prev = self.stack[j].label.strip("()") if j is not None else None
            if label == "I" or (prev in ROMAN_UP and label in ROMAN_UP and ROMAN_UP.index(label) == ROMAN_UP.index(prev) + 1):
                self._sub("uroman", f"({label})", m.group(2))
                return
        if (m := LOWER.match(raw)) and len(self.stack) > 1:
            label = m.group(1)
            kind = self._expected_lower(label)
            if kind:
                self._sub(kind, f"({label})", m.group(2))
                return
        if len(self.stack) > 1:
            node = self.stack[-1]
            if not node.lines and not node.heading and node.absolute:
                node.heading = _heading(raw)  # "1." on its own line, title on the next
            node.lines.append(raw.strip())
        else:
            self.root.lines.append(raw.strip())

    def _sub(self, kind: str, label: str, text: str | None) -> None:
        node = Node(kind, label, False)
        self._place(node)
        if text:
            node.lines.append(text)

    def _top_absolute(self, label: str, text: str) -> None:
        del self.stack[1:]
        node = Node("top", label, True, _heading(text))
        self.root.children.append(node)
        self.stack.append(node)
        if text:
            node.lines.append(text)

    def _accept_top(self, label: str) -> bool:
        key = _num_key(label)
        prev = self.last_top
        ok = key[0] <= 3 if prev is None else (prev < key and key[0] <= prev[0] + 3)
        if ok:
            self.last_top = key
        return ok

    def _accept_dotted(self, label: str) -> bool:
        """A dotted number belongs under the current top-level clause, or starts one in a deed numbered 1.1, 1.2..."""
        head = _num_key(label.split(".")[0])
        prev = self.last_top
        if label in ("1.0", "1.1") and prev is not None and prev > head:
            prev = None  # numbering restarts after a numbered list of representations or recitals (P04)
        if prev is None:
            ok = head[0] <= 3
        else:
            ok = prev <= head and head[0] <= prev[0] + 3
        if ok and (prev is None or head > prev):
            self.last_top = head
        return ok

    # -- output
    def lease(self) -> Lease:
        clauses: list[Clause] = []
        seen: dict[str, int] = {}

        def full_text(node: Node) -> str:
            parts = [" ".join(node.lines)]
            for ch in node.children:
                parts.append(f"{ch.label} {full_text(ch)}" if not ch.absolute else f"{ch.label.split('.')[-1]} {full_text(ch)}")
            return re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()

        def walk(node: Node, base: str) -> None:
            for ch in node.children:
                cid = ch.label if ch.absolute else base + ch.label
                key = cid
                if key in seen:
                    seen[key] += 1
                    cid = f"{key}#{seen[key]}"
                else:
                    seen[key] = 1
                ch.cid = f"{self.lease_id}-{cid}"
                clauses.append(Clause(clause_id=ch.cid, number=cid, heading=ch.heading, text=full_text(ch)))
                walk(ch, cid)

        preamble = re.sub(r"\s+", " ", " ".join(self.root.lines)).strip()
        if preamble:
            clauses.append(Clause(clause_id=f"{self.lease_id}-preamble", number="", heading="Preamble", text=preamble))
        walk(self.root, "")
        definitions = find_definitions(clauses)
        return Lease(lease_id=self.lease_id, clauses=clauses, definitions=definitions, refs=find_refs(self.lease_id, clauses, definitions))


def find_definitions(clauses: list[Clause]) -> list[Definition]:
    """Quoted terms followed by "means" or "includes", in the clause that defines them (the deepest one)."""
    defs: dict[str, Definition] = {}
    for c in clauses:
        for m in DEFINITION.finditer(c.text):
            term = re.sub(r"\s+", " ", m.group(1)).strip()
            end = c.text.find(".", m.end())
            text = c.text[m.start() : end + 1 if end != -1 else len(c.text)]
            prev = defs.get(term)
            # sub-clauses come after their parent, so the later (deeper) clause wins when one contains the other
            if prev is None or c.clause_id.startswith(prev.clause_id):
                defs[term] = Definition(term=term, clause_id=c.clause_id, text=text[:600])
    return list(defs.values())


def _ref_candidates(ref: str, src_number: str) -> list[str]:
    """Clause numbers a reference may mean: as written, and under the same Exhibit/Annexure prefix."""
    ref = re.sub(r"\s+", "", ref)
    out = [ref]
    prefix = src_number.split(".")[0] + "." if re.match(r"^(A[IVX]+|[A-Z])\.", src_number) else ""
    if prefix:
        out.insert(0, prefix + ref)
    return out


def find_refs(lease_id: str, clauses: list[Clause], definitions: list[Definition]) -> list[LeaseRef]:
    numbers = {c.number: c.clause_id for c in clauses}
    refs = set()
    for c in clauses:
        for m in CLAUSE_REF.finditer(c.text):
            ref = m.group(1) or m.group(2)
            for cand in _ref_candidates(ref, c.number):
                # "sub-clause (c) above": fall back from 3(c)(i) to 3(c) to 3
                while cand:
                    dst = numbers.get(cand)
                    if dst:
                        break
                    cand = re.sub(r"\([^()]*\)$", "", cand) if cand.endswith(")") else ""
                if dst and dst != c.clause_id and not dst.startswith(c.clause_id + "(") and not c.clause_id.startswith(dst):
                    refs.add((c.clause_id, dst, "refers_to"))
                    break
        for m in SUBCLAUSE_REF.finditer(c.text):
            parent = re.sub(r"\([^()]*\)$", "", c.number)
            for cand in (parent + m.group(1), c.number + m.group(1)):
                dst = numbers.get(cand)
                if dst and not dst.startswith(c.clause_id) and not c.clause_id.startswith(dst):
                    refs.add((c.clause_id, dst, "refers_to"))
                    break
        for d in definitions:
            if d.clause_id != c.clause_id and not c.clause_id.startswith(d.clause_id) and not d.clause_id.startswith(c.clause_id):
                if re.search(rf"\b{re.escape(d.term)}\b", c.text):
                    refs.add((c.clause_id, d.clause_id, "uses_term"))
    return [LeaseRef(src=s, dst=d, type=t) for s, d, t in sorted(refs)]


def operative_start(lines: list[str]) -> int:
    """Index of the line that opens the operative part ("NOW THIS DEED WITNESSETH..."), or 0.

    Numbered lists before it (parties, recitals) are preamble, not clauses.
    """
    for i, ln in enumerate(lines[: len(lines) // 2]):
        if OPERATIVE.search(ln) and not re.match(r"^\s*\d", ln):
            return i
    return 0


def parse_lease(text: str, lease_id: str) -> Lease:
    p = Parser(lease_id)
    lines = text.splitlines()
    start = operative_start(lines)
    p.root.lines += [ln.strip() for ln in lines[:start] if ln.strip()]
    for line in lines[start:]:
        p.feed(line)
    return p.lease()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", help="deed text files, named <lease_id>.txt")
    ap.add_argument("--out", default="data/leases")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in map(Path, args.files):
        lease = parse_lease(f.read_text(encoding="utf-8"), f.stem)
        (out / f"{lease.lease_id}.json").write_text(lease.model_dump_json(indent=1), encoding="utf-8")
        print(f"{lease.lease_id}: {len(lease.clauses)} clauses, {len(lease.definitions)} definitions, {len(lease.refs)} refs")


if __name__ == "__main__":
    main()
