# Agreement between the answer key and the lawyer

The figure for the report's validation section. It compares the answer key with the lawyer's blind answers for all 340 test items. The key is Saksham's label, written with each item before any review. The lawyer's answers are Batches T1–T6 for the 270 new items and Batch B for the 70 pool items. The lawyer labelled every item, so the 40-item fallback in PLAN.md section 14 was not needed. The tables come from `python -m src.graph.agreement`, on the files frozen at `test-v1`.

**Verdict: 326 of 340 agree (95.9%), Cohen's kappa 0.936 (95% interval 0.904–0.967).**

| Group | Items | Verdict agrees | Kappa (95% interval) | Section agrees | With exceptions |
|---|---|---|---|---|---|
| All | 340 | 326 (95.9%) | 0.936 (0.904–0.967) | 338 (99.4%) | 334 (98.2%) |
| New items (TE, T1-T6) | 270 | 260 (96.3%) | 0.942 (0.905–0.976) | 269 (99.6%) | 266 (98.5%) |
| Pool items (PO, Batch B) | 70 | 66 (94.3%) | 0.914 (0.827–0.979) | 69 (98.6%) | 68 (97.1%) |
| restraint_trade | 100 | 100 (100.0%) | 1.000 (1.000–1.000) | 100 (100.0%) | 100 (100.0%) |
| bar_proceedings | 102 | 91 (89.2%) | 0.824 (0.724–0.916) | 100 (98.0%) | 96 (94.1%) |
| time_limit | 100 | 97 (97.0%) | 0.942 (0.869–1.000) | 100 (100.0%) | 100 (100.0%) |
| out_of_scope | 38 | 38 (100.0%) | – | 38 (100.0%) | 38 (100.0%) |
| single-clause | 241 | 234 (97.1%) | 0.956 (0.923–0.987) | 240 (99.6%) | 240 (99.6%) |
| cross-clause | 99 | 92 (92.9%) | 0.877 (0.778–0.953) | 98 (99.0%) | 94 (94.9%) |

How the table is computed:
- The lawyer's "refer" counts as the key's "handoff".
- Defect type and form are the final labels. TE-140 and PO-65, which the key had as out of scope, count as bars on proceedings.
- "Section agrees" compares s.27, s.28 or out of scope. "With exceptions" also compares the exception, for example Exception 1 to s.28. Section-level kappa over all items is 0.989.
- Kappa is Cohen's. Its interval is a percentile bootstrap over items, with 2,000 resamples and seed 0. A group whose items all agree gives a degenerate interval (restraint of trade). A group with a single verdict has no kappa (out of scope).

## Where they differ

All 14 verdicts that differ are under s.28: 11 bars on proceedings and 3 time limits.

| Key → lawyer | Items | Now (Session 2) |
|---|---|---|
| hand off → void (8) | TE-003, 079, 113, 221, 253: exclusive courts of a city nothing in the deed connects to the lease. PO-14, 24, 66: time limits | void, as the lawyer said |
| void → refer (4) | TE-133, 134, 248: "may" arbitrate plus a bar on the courts, with a binding arbitration clause elsewhere | valid, Exception 1: neither the key nor the blind answer |
| | TE-220: arbitration only if both agree later, plus a bar on the courts | hand off, as the lawyer said |
| hand off → valid (2) | TE-140, PO-65: the key had them out of scope | valid, as the lawyer said |

The lawyer's blind answer became the final label in 11 of the 14. Session 2 gave a third answer in the other 3, and the key prevailed in none. The provisions differ in 6 items: TE-140 and PO-65 above, and TE-048, 094, 158 and PO-42. In those four the key cited Exception 1 and the lawyer cited s.28 alone. Session 2 kept Exception 1, because each clause is valid only while the dispute can still go to arbitration.

## Reading the figure

- **The pool figure is the more independent one.** The 270 new items were written to follow the lawyer's earlier rulings (Session 1 and the Batch A and B reasons), so part of their agreement is by construction. The 70 pool items are clauses from real deeds, which the key and the lawyer each labelled with no shared drafting. On those, kappa is 0.914 (0.827–0.979).
- **The disagreements are where the law is hardest.** They are bars on proceedings with a forum elsewhere in the deed, and cross-clause items (kappa 0.877 against 0.956 for single clauses). Every baseline run so far is also less accurate on cross-clause items. By type the pattern differs: the key and the lawyer agree on every restraint-of-trade item, which the baselines find among the hardest.
- **The two READMEs count "section" differently.** `data/test/README.md` (266/270) counts the exception. `data/pool/README.md` (69/70) does not. Both READMEs are frozen. The report uses the two columns above, which apply one rule to all 340 items.
