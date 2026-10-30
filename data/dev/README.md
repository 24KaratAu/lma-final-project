# Dev clauses: bar on proceedings and restraint of trade

20 new dev items (PLAN.md section 13): 13 bar on legal proceedings (s.28(a), first limb) and 7 restraint of trade (s.27). With the 20 pilot items they make up part of the 60-item dev set.

The clauses are written into copies of the three spare deeds in `../pilot/leases/` (S01–S03, sources in `../sources.csv`). Everything else in the deeds is unchanged.

| ID | City | Year | Items |
|---|---|---|---|
| S01 | Bangalore | 2006 | DV-01 – DV-08, DA-01 – DA-07 |
| S02 | Hyderabad | 2003 | DV-09 – DV-15, DA-08 – DA-14 |
| S03 | — (template, premises left blank) | 2026 | DV-16 – DV-20, DA-15 – DA-21 |

**DA-01 – DA-21** (Amitabh): 14 time limits (s.28(b)) and 7 restraint of trade, planted in the same three deeds. They were written in parallel with the DV items, so where both used the same clause number the DA clause took the next free one (e.g. S01 cl. 9(II)(l), S02 GTC-12B, GTC-12C and GTC-42C, S03 cl. 2(i)–(j) and 3(f)–(i)). The lawyer labelled them blind as Batch A, part 2.

## Files

| File | What it is |
|---|---|
| `planted/` | Copies of S01–S03 with the dev clauses written in. |
| `items.csv` | Where each clause sits (lease and clause number). |
| `answer_key.jsonl` | The team's answer for each clause, in the labelled-item format. |
| `answer_sheet_blank.csv` | Blank sheet for DA-01 – DA-21, as sent to the lawyer. |
| `../../docs/legal/batch_a_answers.csv` | The lawyer's blind answers for DV-01 – DV-20 (Batch A), with reasons. |
| `../../docs/legal/batch_a2_answers.csv` | The lawyer's blind answers for DA-01 – DA-21 (Batch A, part 2), with reasons. |

The lawyer's answers agree with the answer key on all 41 verdicts and all 41 sections. On DV-03 the key cites Exception 1 to s.28 and the lawyer cites s.28 alone.

Points from the lawyer's reasons on the DA items, for Session 2:

- **DA-08** (S02 GTC-42C, 3 years from the end of the lease) and **DA-11** (S02 GTC-25(d), 3 years from the "event"): valid, but borderline. For a claim that accrues after the lease ends, or an indemnity where time runs from the loss, the period can be shorter than 3 years from accrual, and the clause would be void to that extent.
- **DA-13** and **DA-21** (in-term restraints on business elsewhere): refer, as in the Session 1 rule. DA-21 raises a question: is a PSU's choice of office location "trade or business" at all?
- **DA-18** (S03 cl. 3(h)): void because the guarantee period is under one year (Exception 3 needs at least one year). The duty to furnish the guarantee survives.

## Mix

| Type | Void | Valid | Hand off | Cross-clause |
|---|---|---|---|---|
| Bar on proceedings | 5 | 5 | 3 | 4 |
| Restraint of trade | 3 | 2 | 2 | 2 |

Labels follow the rules in the lawyer's Session 1 review (`../../docs/legal/session1_review.md`), not the draft rules in PLAN.md section 6.

## Notes

- **DV-08** (S01 cl. 13) is the deed's own arbitration clause, unchanged. It is a real look-alike.
- **New phrasing family BP-7:** a surveyor, architect or engineer whose certificate is "final and binding" on a question of fact. Following the review, it is hand off when the expert is independent and the courts are not expressly excluded (DV-01, DV-16). It is void when the expert is one party's nominee and the clause shuts out every court and tribunal (DV-09).
- **BP-7 elements:** the hand-off items leave out `alternative_forum`, because none of `arbitration`, `named_court` or `none` fits an expert determination. Settle this when `ELEMENTS` is updated with the Session 1 corrections.
- **Cross-clause items** depend on: S01 cl. 13 (arbitration), S02 Section 3(b) (Expiration Date), S02 Section 3(f) (Restricted Period and Restricted Area), S02 GTC-11(d) (Lessor's Certificate), S02 GTC-42 (arbitration) and S03 cl. 3(c) (arbitration).
- **Item ids:** DV-01 to DV-20 are used here. New dev items continue from DV-21.

**Still to do:** merge these items with the pilot items into `items.jsonl` once the lease parser gives every clause its `clause_id`.
