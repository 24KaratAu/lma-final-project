# Pilot leases

Five real, executed Indian commercial lease deeds for the pilot (PLAN.md section 2, Gate 0 item 1), plus three spares. Sources, parties and dates are in `data/sources.csv`.

| ID | City | Year | Words |
|---|---|---|---|
| P01 | Chennai | 2008 | 14,658 |
| P02 | Hyderabad | 2003 | 13,697 |
| P03 | Bangalore | 2006 | 6,931 |
| P04 | Bangalore | 2010 | 9,487 |
| P05 | Bangalore | 2021 | 7,026 |
| S01 | Bangalore | 2006 | spare |
| S02 | Hyderabad | 2003 | spare, same lessor as P02 |
| S03 | — | 2026 | spare, PSU template with blanks |

**What was done to them:** HTML converted to plain text and the filing headers removed. The wording of the deeds is unchanged. Original downloads are kept locally in `data/raw/`, which git ignores.

## Pilot files

| File | What it is |
|---|---|
| `leases/` | The five pilot deeds and three spares, as collected. Never edited. |
| `planted/` | Copies of P01–P05 with 20 clauses written in by hand. |
| `items.csv` | Where each of the 20 clauses sits (lease and clause number). |
| `answer_key.jsonl` | The team's answer for each clause, in the labelled-item format. |
| `../../docs/legal/pilot_answers.csv` | The lawyer's blind answers, with reasons. |
| `../../docs/legal/session1_review.md` | The lawyer's Session 1 review of the types, rules and judgments. |

The answer key and the lawyer's answers were committed together on 26 Oct 2026. They agree on all 20 verdicts and all 20 sections.

**Still to do:** run the two frontier models on `planted/` (fresh chat per lease, same neutral prompt), save every raw answer, and count misses and false alarms against `answer_key.jsonl`.
