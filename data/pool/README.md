# Item pool: 20 more leases

20 real, executed Indian commercial lease deeds, with 70 clauses to label (PLAN.md section 13, "collect 15–20 more leases"). Sources, parties and dates are in `../sources.csv` (`use` = `pool`).

| ID | City | Year | Items |
|---|---|---|---|
| L01 | Coimbatore | 2005 | PO-01 – PO-04 |
| L02 | Noida | 2004 | PO-05 – PO-08 |
| L03 | Gurgaon | 2007 | PO-09 – PO-12 |
| L04 | Gurgaon | 2008 | PO-13 – PO-16 |
| L05 | Hyderabad | 2007 | PO-17 – PO-19 |
| L06 | Chennai | 2004 | PO-20 – PO-23 |
| L07 | Gurgaon | 2005 | PO-24 – PO-27 |
| L08 | Bangalore | 2009 | PO-28 – PO-31 |
| L09 | Bangalore | 2014 | PO-32 – PO-34 |
| L10 | Thane | 2013 | PO-35 – PO-37 |
| L11 | Noida | 2012 | PO-38 – PO-40 |
| L12 | Hyderabad | 2009 | PO-41 – PO-44 |
| L13 | Chennai | 2010 | PO-45 – PO-48 |
| L14 | Mundra (Kachchh) | 2024 | PO-49 – PO-51 |
| L15 | Noida | 2016 | PO-52 – PO-54 |
| L16 | Bangalore | 2017 | PO-55 – PO-57 |
| L17 | Siruseri (Kancheepuram) | 2004 | PO-58 – PO-61 |
| L18 | Chennai | 2018 | PO-62 – PO-64 |
| L19 | New Delhi | 2011 | PO-65 – PO-67 |
| L20 | Bangalore | 2008 | PO-68 – PO-70 |

All deeds were executed after 8 January 1997, so s.28(b) applies to every one of them (Session 1 review, section 1).

**What was done to them:** HTML or SEC text converted to plain text, and the EDGAR filing headers removed. The wording of the deeds is unchanged. L06 keeps only the first of the four near-identical deeds in its exhibit. L10 and L11 contain terms that the filer redacted (`*****`). Original downloads are not committed.

## Files

| File | What it is |
|---|---|
| `leases/` | The 20 deeds, as collected. Never edited. |
| `planted/` | Copies of the deeds with clauses written in. L17 has none: all of its items are the deed's own wording. |
| `items.csv` | Where each of the 70 clauses sits (lease and clause number). This is what goes to the lawyer. |
| `answer_sheet_blank.csv` | Blank sheet for the lawyer, in the same columns as `../../docs/legal/pilot_answers.csv`. |
| `answer_key.jsonl` | The team's answer for each clause, in the labelled-item format. Do not send it to the lawyer. |
| `../../docs/legal/batch_b_answers.csv` | The lawyer's blind answers (Batch B), with reasons. |

The lawyer's answers agree with the answer key on 66 of 70 verdicts and 69 of 70 sections. Where they differ:

| Item | Answer key | Lawyer |
|---|---|---|
| PO-14 | hand off, s.28 | void, s.28(b) |
| PO-24 | hand off, s.28 | void, s.28(b) |
| PO-66 | hand off, s.28 | void, s.28(b) |
| PO-65 | hand off, out of scope | valid, s.28 Exception 1 |

On PO-42 the key cites Exception 1 to s.28 and the lawyer cites s.28 alone.

## Mix

| Type | Void | Valid | Hand off | Total |
|---|---|---|---|---|
| Restraint of trade | 7 | 6 | 4 | 17 |
| Bar on proceedings | 8 | 9 | 4 | 21 |
| Time limit | 9 | 8 | 3 | 20 |
| Out of scope | | | 12 | 12 |

18 items are cross-clause. Labels follow the lawyer's Session 1 review (`../../docs/legal/session1_review.md`).

**25 items are the deeds' own wording, unchanged:** PO-01, 02, 04, 05, 10, 12, 16, 19, 22, 23, 25, 26, 30, 35, 44, 45, 51, 55, 58, 59, 60, 61, 63, 65, 69. The other 45 are written into the copies in `planted/`. Real clauses worth the lawyer's attention:

- **PO-16** (L04 cl. 15) and **PO-61** (L17 cl. 36): exclusive jurisdiction given to courts of a city other than the one where the premises are.
- **PO-59** (L17 cl. 26): a cost fixed by the lessor "cannot be questioned in any Court of law", while cl. 35 still sends disputes to arbitration.
- **PO-60** (L17 cl. 35): the arbitrator is appointed by the Government of Tamil Nadu, and the lessee may not raise disputes during the lease.
- **PO-65** (L19 cl. D(vi)): an arbitration clause in a lease that says it is governed by the Delhi Rent Control Act.

## Phrasing families

Families used in the pilot, plus these new ones:

| Family | Pattern |
|---|---|
| TL-3 | Period equal to the statutory limitation period (3 years for money claims): valid |
| TL-5 | Short limit on starting arbitration, or on serving the notice that starts it |
| TL-6 | A bill or statement is "deemed accepted" unless disputed within a period |
| BP-7 | A surveyor's or expert's determination is "final and binding" (as in `../dev/`) |
| OOS-1 | Lock-in rent, or pre-determined damages for holding over (s.74) |
| OOS-2 | Forfeiture of a deposit or development charges |
| OOS-3 | Cap on, or exclusion of, liability |
| OOS-4 | Remedy limited to damages, with no injunction |
| OOS-5 | Interest on late payment, plus cutting off services |
| OOS-6 | Arbitration in a tenancy said to be under a rent control statute |

The BP-7 hand-off items and the TL-6 items leave out the elements that none of the allowed values fit (`alternative_forum`, `effect_on_expiry`). Settle this when `ELEMENTS` is updated with the Session 1 corrections.

## Still to do

1. Commit the answer key as it stands, and never edit it afterwards (PLAN.md section 13). Changes after the lawyer's review, including the four disagreements above, go in a separate corrections file.
2. Decide whether these items go to test or dev. PLAN.md section 9 says test items are drafted with an open model, so B2 is never scored on clauses a frontier model wrote. The 25 unchanged clauses are not affected.
