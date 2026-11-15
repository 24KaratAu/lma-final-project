# Statute graph: Indian Contract Act, 1872

Built by `python -m src.graph.statute` from the India Code PDF (https://www.indiacode.nic.in/bitstream/123456789/2187/2/A187209.pdf, retrieved 30 Oct 2026). The PDF is kept in `data/raw/statute/`, which git ignores.

| | Count |
|---|---|
| Sections in force | 192 |
| Exceptions | 7 |
| Explanations | 15 |
| Illustrations | 201 |
| `exception_to` / `explains` / `illustrates` edges (parsed) | 7 / 15 / 201 |
| `refers_to` edges (regex, "section N" in the text) | 11 |

All 11 `refers_to` edges were checked by eye on 30 Oct and are right (s.14 → ss.15–18 and 20–22, s.19 Exception → s.17, s.152 → s.151, s.178A → ss.19 and 19A). The other "section N" mentions in the Act name sections of other Acts (IPC, Evidence Act, Banking Regulation Act) and are skipped.

Node ids: `ICA-28` (section), `ICA-28-E1` (exception), `ICA-28-X1` (explanation), `ICA-29-Ia` (illustration (a)). Repealed sections (76–123 and others) are left out. Footnotes, page numbers and amendment brackets are stripped; the wording is otherwise as printed.

## Rulings (`rulings.csv`)

The 18 leading judgments the lawyer listed in Session 1 (`../../docs/legal/session1_review.md`, section 5), one row each. A row becomes a ruling node with `interprets` edges (source `manual`) only after a person has read the judgment (PLAN.md section 7):

1. Find the judgment (Indian Kanoon has most of them) and read the part that deals with s.27 or s.28. Check the citation against the reported text.
2. Fill in `holding` (one sentence, in your own words, saying what the court decided), `source_url`, `read_by` and `read_on` (YYYY-MM-DD). Correct `interprets` if needed: the provision ids it interprets, separated by `;`, such as `ICA-28;ICA-28-E1`.
3. Run `python -m src.graph.rulings`, which rewrites the ruling nodes and `interprets` edges here to match the sheet, then `pytest -q`.

`lawyer_note` is the lawyer's one-line summary, kept as a pointer for the reader. It never goes into the graph, and no AI writes a holding. When all rows are read, send the holdings to the lawyer to check (Session 2 asked for them).

The lawyer checked the 17 holdings on 15 Nov 2026 (`../../docs/legal/rulings_review.md`). No. 5 now uses the judgment's wording, and Nos. 15 and 18 add the points the lawyer asked for, in the lawyer's words: No. 15 overruled *Himangni*, and No. 18 applies prospectively. RUL-01 stays unread: it is known only through *Percept D'Mark* until the Bengal Law Reports text is read. The lawyer signs off the revised sheet.

Flat retrieval and the agent's `search_graph` index only sections, exceptions and explanations, and the agent never follows an `interprets` edge from a section to a ruling, so ruling nodes do not change their results. Graph retrieval (`src/retrieval`, mode `graph`) is what uses them.
