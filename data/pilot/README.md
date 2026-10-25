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

**Not yet done (by hand, no AI):**
1. Read each lease and note any clause that is already void, before planting anything.
2. Plant the defects and look-alikes in copies of these files, never in the originals here.
3. Write and commit the sealed answer key before the first model run.
