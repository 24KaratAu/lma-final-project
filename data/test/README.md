# Test set

**Status (15 Nov 2026):** built, **not yet frozen**. The 340 items are in `items.jsonl`. The lawyer has answered T1–T6 and settled the doubtful items in Session 2, and the corrections are applied. Only the freeze and the `test-v1` tag remain.

## What is in it

After the corrections (keys plus `corrections.jsonl`):

| Type | Void | Valid | Hand off | Cross-clause | Total |
|---|---|---|---|---|---|
| Restraint of trade (s.27) | 50 | 27 | 23 | 33 | 100 |
| Bar on proceedings (s.28(a), first limb) | 51 | 39 | 12 | 36 | 102 |
| Time limits (s.28(a), second limb, and s.28(b)) | 53 | 47 | | 30 | 100 |
| Out of scope | | | 38 | | 38 |
| **All** | 154 | 113 | 73 | 99 | **340** |

- **70 pool items** (`../pool/`, PO-01 – PO-70). These are clauses in 20 real executed deeds, of which 25 keep the deeds' own wording. The lawyer labelled them blind (Batch B), and `../pool/corrections.jsonl` applies the lawyer's answer where it differed from the key.
- **270 new items** (TE-001 – TE-270), written into the same 20 deeds (9–19 per deed) in each deed's own numbering and party names. They follow the phrasing families of `src/eval/draft_config.json` and the lawyer's rulings in the Session 1 review and the Batch A and B reasons. Two of those rulings are:
  - TL-6 ("deemed accepted unless disputed") is **void** under s.28(b), not hand off.
  - A goodwill restraint without specified local limits, or one that does not end when the buyer stops the business, is **void**.

The 20 deeds are used nowhere else, neither in dev nor in training (`../sources.csv`, `use` = `test`).

## Checking the labels

The lawyer answered T1–T6 blind (`../../docs/legal/test_T<n>_answers.csv`). Where the lawyer and the key differ, the lawyer's answer decides (PLAN.md section 13). `corrections.jsonl` records the change, and `items.jsonl` applies it.

| | T1 | T2 | T3 | T4 | T5 | T6 | All |
|---|---|---|---|---|---|---|---|
| Verdict agrees with the key | 44 | 44 | 42 | 44 | 43 | 43 | 260/270 (96.3%) |
| Section agrees with the key | 45 | 44 | 44 | 43 | 45 | 45 | 266/270 (98.5%) |

Where they differ, and what Session 2 decided (`../../docs/legal/session2_review.md`, answer sheet `../../docs/legal/session2_answers.csv`):

| Items | Key | Lawyer, blind | Session 2, now |
|---|---|---|---|
| TE-003, 079, 113, 221, 253 (BP-3): exclusive jurisdiction of the courts of a city that nothing in the deed connects to the lease | hand off | void, s.28(a), two with "unless facts outside the deed" | void, s.28(a), with no "unless" |
| TE-133, 134, 248 (BP-5): "may" go to arbitration plus a bar on the courts, with a binding arbitration clause elsewhere in the deed | void | refer, s.28(a) | valid, Exception 1: the binding clause is the arbitration agreement, and "may" does not contradict it |
| TE-220 (BP-5): arbitration only "if both parties so agree at the time the dispute arises", plus a bar on the courts | void | refer, s.28(a) | hand off, cross-clause as in PO-59: cl. 2A contradicts cl. 23A, and which prevails is for a court |
| TE-140 (OOS-2): the deposit is applied to sums due "in the opinion of" the Lessor | hand off, out of scope | valid, s.28(a) | valid, s.28 |
| TE-048, 094, 158 (BP-1), and PO-42: the Lessor's decision binds until it is arbitrated | valid, Exception 1 | valid, s.28 | valid, Exception 1: the key stands |

Session 2 also gave three rules for the whole set. The set already follows them:
- **Courts of another city.** Valid if the premises are there. Refer if something in the deed (a party's office, the place of signing or of payment) puts the city in jurisdiction, as in PO-16 and PO-61. Void if nothing does. Facts that might turn up outside the deed are not enough for refer.
- **Exception 1 or s.28.** Exception 1 when the clause is valid because the dispute can go to arbitration (arbitration clauses, "shall arbitrate; no courts" included, and clauses that bind until arbitrated). s.28 when it is valid because the courts stay open or no forum is affected (a choice of competent court, TE-140, the notice-period look-alikes). Every valid bar-on-proceedings item citing Exception 1 or 2 has `alternative_forum` = `arbitration`, and every one citing s.28 has a named court or none.
- **s.28 or out of scope.** A clause is under s.28 if it deals with who decides a claim, where or by when, even when it is valid. It is out of scope only if it deals with what can be recovered, or has nothing to do with claims.

A bar on the courts next to a binding arbitration clause cannot remove the courts' role under the 1996 Act (ss. 9, 11, 34 and 36), so nothing is actually restricted: TE-133, 134 and 248 take `degree` = `partial`, like the BP-2 "shall arbitrate; no courts" items.

Thirteen of the 270 labels (after the corrections) are deliberately not what the decision rules in `src/models/verify.py` would give from the elements, because the law goes further than the rules:
- 7 RT-3 voids: goodwill is sold, but the restraint has no local limit or does not end when the buyer stops.
- 3 TL-4 guarantees saved by Exception 3.
- 2 bar-on-proceedings hand offs (TE-032, BP-1, and TE-220, BP-5): a bar on the courts with the deed's arbitration clause still open, as in PO-59.
- TE-140: no rule verdict, because no allowed value of `degree` or `alternative_forum` fits a clause that restricts nothing.

The dev and pool keys label DV-10, PO-68 and PO-59 the same way.

## Rules

- **Before the freeze, only Saksham opens this folder.** These files live on the `data/test-set` branch and reach `main` only at the freeze, because Avnish builds and tunes the system from `main` (PLAN.md section 14).
- **The answer key is never edited.** `build` refuses to change a keyed item; later changes go in `corrections.jsonl` (PLAN.md section 13).

## Next steps

1. ✅ **Lawyer.** T1–T6 answered (`../../docs/legal/test_T<n>_answers.csv`).
2. ✅ **Corrections.** The 10 verdicts that differed are in `corrections.jsonl`.
3. ✅ **Session 2.** The 13 items above and PO-42 are settled, and `corrections.jsonl` records the outcome (source: the Batch and Session 2). The judgment summaries are still to go to the lawyer (`../../docs/legal/session2_review.md`, point 5).
4. **Freeze.** Run `python -m src.graph.items items --include data/pool`, which rewrites `items.jsonl` from the keys plus corrections. Then tag `test-v1` and merge into `main`.

## Changing or adding items

Edit `worksheet.csv` (one row per item) and rebuild with `python -m src.graph.items build --batch <new batch> [--check]`. `build` writes the kept clauses of every keyed batch, plus the new one, into copies of the host deeds. It checks that each clause landed under its number in the parse, that the labels are valid, and that dev and pool items still resolve. Then it appends the batch to the key.

| Column | What it holds |
|---|---|
| `keep`, `item_id`, `batch` | `y`, `TE-001`…, `T1`… |
| `clause` | The clause, starting with its number as the deed writes it (`16A.`, `(g)`, `9.2A`) |
| `lease_id`, `after`, `clause_id` | Host deed, the clause it goes straight after (sub-clauses included), and its own number |
| `support`, `support_after`, `support_id` | Cross-clause only: the definition it depends on, where it goes, and its number. For a clause already in the deed (its arbitration clause), `support_id` alone |
| `verdict`, `provision`, `elements`, `path` | The labels. Elements as JSON or `name=value; name=value` |
| `notes` | Anything worth knowing about the row |

## Files

| File | What it is |
|---|---|
| `worksheet.csv` | The 270 new items, as written and labelled |
| `planted/` | The 20 pool deeds with the pool and test clauses written in; parsed into `../leases/L01.json`–`L20.json` |
| `answer_key.jsonl` | The 270 new items, appended batch by batch |
| `items.csv` | Where each new clause sits (lease and clause number) |
| `batches/T<n>_answer_sheet_blank.csv` | Blank sheet for the lawyer, one per batch of 45 |
| `batches/S2_answer_sheet_blank.csv` | Blank sheet for Session 2: the 13 test items and PO-42 |
| `corrections.jsonl` | Changes to keyed items after the lawyer's review (10, from T1–T6 and Session 2) |
| `items.jsonl` | The test set: pool and new items, keys plus corrections (340) |
