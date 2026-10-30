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

Node ids: `ICA-28` (section), `ICA-28-E1` (exception), `ICA-28-X1` (explanation), `ICA-29-Ia` (illustration (a)). Repealed sections (76–123 and others) are left out. Footnotes, page numbers and amendment brackets are stripped; the wording is otherwise as printed. `interprets` edges from rulings come in Phase 2.
