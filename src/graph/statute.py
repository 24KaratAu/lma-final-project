"""Statute graph from the India Code PDF of the Indian Contract Act, 1872 (PLAN.md section 7).

python -m src.graph.statute --pdf data/raw/statute/A1872-09.pdf --out data/statute

Nodes: every section in force, its exceptions, explanations and illustrations.
Edges: exception_to, explains and illustrates from the layout (source "parsed"),
and refers_to wherever a node's text names another section of the Act (source "regex").
Repealed sections are left out. The PDF itself stays in data/raw/, which git ignores.
"""

import argparse
import re
import subprocess
from pathlib import Path

from src.common.jsonl import write_jsonl
from src.common.schemas import StatuteEdge, StatuteNode, check_graph

PREFIX = "ICA"
SOURCE_URL = "https://www.indiacode.nic.in/bitstream/123456789/2187/2/A187209.pdf"

SECTION = re.compile(r"^(\d{1,3}[A-Z]{0,2})\.\s*\[?\s*([A-Z\[“\"].*)$")
EXCEPTION = re.compile(r"^\[?Exception\s*(\d*)(?:\.?\s*—\s*|\s+(?=in favour))(.*)$")
EXPLANATION = re.compile(r"^\[?Explanation\s*([0-9IV]*)\.?\s*—\s*(.*)$")
ILLUSTRATIONS = re.compile(r"^Illustrations?\.?$")
ILLUSTRATION = re.compile(r"^\(([a-z]{1,2})\)\s+(.*)$")
SECTION_REF = re.compile(r"\bsections?\s+(\d{1,3}[A-Z]?)((?:\s*(?:,|and|or|to)\s*\d{1,3}[A-Z]?)*)", re.I)
OTHER_ACT = re.compile(r"^[^.;]{0,60}?\bof\s+the\s+[A-Z][\w ,()]*?Act\b")
ROMAN = {"I": "1", "II": "2", "III": "3", "IV": "4", "V": "5"}


def pdf_text(pdf: Path) -> str:
    return subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=True).stdout


def clean_pages(raw: str) -> list[str]:
    """Body lines of the Act with page numbers, footnotes and amendment marks removed."""
    lines = []
    for page in raw.split("\f"):
        page_lines = page.split("\n")
        # Footnotes are numbered from 1 on every page and sit at its foot; section 1 is the only
        # section numbered 1, and its heading has a dash.
        for i in range(len(page_lines) - 1, -1, -1):
            if re.match(r"^1\.\s", page_lines[i]) and "—" not in page_lines[i]:
                page_lines = page_lines[:i]
                break
        lines += page_lines
    body_start = next(i for i, ln in enumerate(lines) if ln.startswith("1. Short title.—"))
    out = []
    for ln in lines[body_start:]:
        ln = ln.strip()
        if not ln or re.fullmatch(r"[\d*.\s]+", ln):  # page numbers, footnote marks, "* * *"
            continue
        ln = re.sub(r"(?<=[A-Za-z\.\)\],;:”])\d{1,2}(?=[\s.,;:—\]\[]|$)", "", ln)  # superscript footnote marks
        ln = re.sub(r"^\d{1,2}\[", "[", ln)
        ln = ln.replace("[", "").replace("]", "").replace("*", "").strip()
        if ln:
            out.append(ln)
    return out


def _sec_key(num: str) -> tuple[int, str]:
    m = re.match(r"(\d+)([A-Z]*)", num)
    return int(m.group(1)), m.group(2)


def split_sections(lines: list[str]) -> list[tuple[str, list[str]]]:
    """[(section number, its lines)], in order. A heading must come after the previous section number."""
    sections: list[tuple[str, list[str]]] = []
    for ln in lines:
        m = SECTION.match(ln)
        if m:
            num = m.group(1)
            prev = _sec_key(sections[-1][0]) if sections else (0, "")
            key = _sec_key(num)
            if prev < key and key[0] <= prev[0] + 30:
                sections.append((num, [m.group(2)]))
                continue
        if sections:
            sections[-1][1].append(ln)
    return sections


def _join(lines: list[str]) -> str:
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def parse_section(num: str, lines: list[str]) -> tuple[list[StatuteNode], list[StatuteEdge]]:
    sid = f"{PREFIX}-{num}"
    parts: list[list] = [["section", None, []]]  # [kind, number, lines]
    in_illustrations = False
    for ln in lines:
        if m := EXCEPTION.match(ln):
            parts.append(["exception", m.group(1) or "1", [m.group(2)]])
            in_illustrations = False
        elif m := EXPLANATION.match(ln):
            parts.append(["explanation", ROMAN.get(m.group(1), m.group(1)) or "1", [m.group(2)]])
            in_illustrations = False
        elif ILLUSTRATIONS.match(ln):
            in_illustrations = True
        elif in_illustrations and (m := ILLUSTRATION.match(ln)):
            parts.append(["illustration", m.group(1), [m.group(2)]])
        elif in_illustrations and parts[-1][0] == "section":
            parts.append(["illustration", "", [ln]])  # a single, unlettered illustration
        else:
            parts[-1][2].append(ln)

    nodes, edges = [], []
    seen_x = 0
    for kind, n, body in parts:
        text = _join(body)
        if kind == "section":
            nodes.append(StatuteNode(id=sid, type="section", label=f"Section {num}", text=text))
            continue
        if kind == "exception":
            nid, label, etype = f"{sid}-E{n}", f"Exception {n} to Section {num}", "exception_to"
        elif kind == "explanation":
            seen_x += 1
            n = n if n != "1" or seen_x == 1 else str(seen_x)
            nid, label, etype = f"{sid}-X{n}", f"Explanation {n} to Section {num}", "explains"
        else:
            n = n or "a"
            nid, label, etype = f"{sid}-I{n}", f"Illustration ({n}) to Section {num}", "illustrates"
        if any(x.id == nid for x in nodes):  # e.g. a second unlettered illustration
            nid += f"-{len(nodes)}"
        nodes.append(StatuteNode(id=nid, type=kind, label=label, text=text))
        edges.append(StatuteEdge(src=nid, dst=sid, type=etype, source="parsed"))
    return nodes, edges


def regex_edges(nodes: list[StatuteNode]) -> list[StatuteEdge]:
    """refers_to edges for "section N" in a node's text, skipping sections of other Acts."""
    sections = {n.id for n in nodes if n.type == "section"}
    edges = set()
    for node in nodes:
        own = "-".join(node.id.split("-")[:2])
        for m in SECTION_REF.finditer(node.text):
            if OTHER_ACT.match(node.text[m.end() :]):
                continue
            nums = [m.group(1)] + re.findall(r"\d{1,3}[A-Z]?", m.group(2) or "")
            for num in nums:
                dst = f"{PREFIX}-{num}"
                if dst in sections and dst != own:
                    edges.add((node.id, dst))
    return [StatuteEdge(src=s, dst=d, type="refers_to", source="regex") for s, d in sorted(edges)]


def build(pdf: Path) -> tuple[list[StatuteNode], list[StatuteEdge]]:
    nodes, edges = [], []
    for num, lines in split_sections(clean_pages(pdf_text(pdf))):
        if re.match(r"^[^—]*\bRep\.", " ".join(lines[:3])) and "—" not in lines[0]:
            continue  # repealed
        n, e = parse_section(num, lines)
        nodes += n
        edges += e
    edges += regex_edges(nodes)
    check_graph(nodes, edges)
    return nodes, edges


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default="data/raw/statute/A1872-09.pdf", help=f"India Code PDF ({SOURCE_URL})")
    ap.add_argument("--out", default="data/statute")
    args = ap.parse_args(argv)
    nodes, edges = build(Path(args.pdf))
    write_jsonl(Path(args.out) / "nodes.jsonl", nodes)
    write_jsonl(Path(args.out) / "edges.jsonl", edges)
    counts = {t: sum(n.type == t for n in nodes) for t in ("section", "exception", "explanation", "illustration")}
    ecounts = {t: sum(e.type == t for e in edges) for t in ("exception_to", "explains", "illustrates", "refers_to")}
    print(f"{len(nodes)} nodes {counts}; {len(edges)} edges {ecounts}")


if __name__ == "__main__":
    main()
