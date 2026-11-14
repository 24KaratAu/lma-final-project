# Test set

**Status (14 Nov 2026):** built, **not yet frozen**. The 340 items are in `items.jsonl`. The six new batches (T1–T6) still need the lawyer's blind answers and Session 2 before the freeze and the `test-v1` tag.

## What is in it

| Type | Void | Valid | Hand off | Cross-clause | Total |
|---|---|---|---|---|---|
| Restraint of trade (s.27) | 50 | 27 | 23 | 33 | 100 |
| Bar on proceedings (s.28(a), first limb) | 50 | 35 | 16 | 32 | 101 |
| Time limits (s.28(a), second limb, and s.28(b)) | 53 | 47 | | 30 | 100 |
| Out of scope | | | 39 | | 39 |
| **All** | 153 | 109 | 78 | 95 | **340** |

- **70 pool items** (`../pool/`, PO-01 – PO-70). These are clauses in 20 real executed deeds, of which 25 keep the deeds' own wording. The lawyer labelled them blind (Batch B), and `../pool/corrections.jsonl` applies the lawyer's answer where it differed from the key.
- **270 new items** (TE-001 – TE-270), written into the same 20 deeds (9–19 per deed) in each deed's own numbering and party names. They follow the phrasing families of `src/eval/draft_config.json` and the lawyer's rulings in the Session 1 review and the Batch A and B reasons. Two of those rulings are:
  - TL-6 ("deemed accepted unless disputed") is **void** under s.28(b), not hand off.
  - A goodwill restraint without specified local limits, or one that does not end when the buyer stops the business, is **void**.

The 20 deeds are used nowhere else, neither in dev nor in training (`../sources.csv`, `use` = `test`).

## Who wrote the new items

**The 270 new clauses and their labels were written by Claude (`claude-opus-5-5`) at Saksham's request, not hand-edited from the open-model drafts** that PLAN.md section 9 planned for. The `author` column of `worksheet.csv` records this on every row. Two consequences go in the report:

1. **The frontier baseline (B2) runs on Claude Opus, the model that wrote and labelled these items.** Report B2 on the pool items (70, all written or chosen by the team) as well as on the whole set, and say why.
2. **The lawyer's blind answers on T1–T6 are the check on the labels.** Where the lawyer and the key differ, the lawyer's answer decides (`corrections.jsonl`). Report the agreement per batch.

Eleven of the 270 labels are deliberately not what the decision rules in `src/models/verify.py` would give from the elements, because the law goes further than the rules:
- 7 RT-3 voids: goodwill is sold, but the restraint has no local limit or does not end when the buyer stops.
- 3 TL-4 guarantees saved by Exception 3.
- 1 BP-1 hand off: a finality clause with the deed's arbitration clause still open, as in PO-59.

The dev and pool keys label DV-10, PO-68 and PO-59 the same way.

## Rules

- **Before the freeze, only Saksham opens this folder.** These files live on the `data/test-set` branch and reach `main` only at the freeze, because Avnish builds and tunes the system from `main` (PLAN.md section 14).
- **The answer key is never edited.** `build` refuses to change a keyed item; later changes go in `corrections.jsonl` (PLAN.md section 13).

## Next steps

1. **Lawyer.** Send each `batches/T<n>_answer_sheet_blank.csv` with the planted deeds it points to (`planted/`), never the answer key. Save the returned sheets as `../../docs/legal/test_T<n>_answers.csv`.
2. **Corrections.** Where the lawyer differs, add a line to `corrections.jsonl`, then take the doubtful ones to Session 2.
3. **Freeze.** Run `python -m src.graph.items items --include data/pool`, which rewrites `items.jsonl` from the keys plus corrections. Then tag `test-v1` and merge into `main`.

## Changing or adding items

Edit `worksheet.csv` (one row per item) and rebuild with `python -m src.graph.items build --batch <new batch> [--check]`. `build` writes the kept clauses of every keyed batch, plus the new one, into copies of the host deeds. It checks that each clause landed under its number in the parse, that the labels are valid, and that dev and pool items still resolve. Then it appends the batch to the key.

| Column | What it holds |
|---|---|
| `keep`, `item_id`, `batch` | `y`, `TE-001`…, `T1`… |
| `clause` | The clause, starting with its number as the deed writes it (`16A.`, `(g)`, `9.2A`) |
| `lease_id`, `after`, `clause_id` | Host deed, the clause it goes straight after (sub-clauses included), and its own number |
| `support`, `support_after`, `support_id` | Cross-clause only: the definition it depends on, where it goes, and its number. For a clause already in the deed (its arbitration clause), `support_id` alone |
| `verdict`, `provision`, `elements`, `path` | The labels. Elements as JSON or `name=value; name=value` |
| `author`, `notes` | Who wrote the row as kept |

## Files

| File | What it is |
|---|---|
| `worksheet.csv` | The 270 new items, as written and labelled |
| `planted/` | The 20 pool deeds with the pool and test clauses written in; parsed into `../leases/L01.json`–`L20.json` |
| `answer_key.jsonl` | The 270 new items, appended batch by batch |
| `items.csv` | Where each new clause sits (lease and clause number) |
| `batches/T<n>_answer_sheet_blank.csv` | Blank sheet for the lawyer, one per batch of 45 |
| `corrections.jsonl` | Changes to keyed items after the lawyer's review (none yet) |
| `items.jsonl` | The test set: pool and new items, keys plus corrections (340) |
