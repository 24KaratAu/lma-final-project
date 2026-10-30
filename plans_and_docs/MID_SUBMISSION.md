# Mid-submission: Team ClosedAI

**Project:** Statute-grounded enforceability checking for Indian commercial leases
**Date:** Fri 30 Oct 2026 · **Repository:** https://github.com/24KaratAu/lma-final-project (tag `mid-v1`)

All numbers below are on the **dev set** (61 items). The test set is not built yet; it is frozen on Fri 6 Nov and nothing here was tuned on it.

---

## 1. Progress

The task: given a clause of an Indian commercial lease, decide whether it is **void** under Section 27 (restraint of trade) or Section 28 (restraint of legal proceedings, including time limits) of the Indian Contract Act, 1872, **valid**, or should be **handed off** to a lawyer; cite the provision; and show the evidence path through the statute and the lease.

### Gate 0 (the TA's second feedback)

| Gate | Outcome |
|---|---|
| Legal validator | A practising lawyer agreed and labels blind. Session 1 review done (`docs/legal/session1_review.md`): confirmed the three defect types, the look-alikes and the element checklists, with corrections now in the decision rules. |
| Pilot on five leases | 20 clauses planted in 5 real deeds; the lawyer's blind labels agree with our key on 20/20 verdicts. Two frontier models read each whole deed (section 5.1). |
| Kaggle smoke test | Qwen2.5-7B-Instruct loads in 4-bit on a T4 (135 s, 5.1 GB peak); 20-step QLoRA completes with inputs up to 1,536 tokens. vLLM dropped (needs CUDA 13). |

### Components

| Component | Status | Where |
|---|---|---|
| Shared data contracts, fixtures, tests | Done | `src/common/`, `tests/` |
| Statute graph (Contract Act) | Done: 415 nodes, 234 edges | `src/graph/statute.py`, `data/statute/` |
| Lease parser (clauses, definitions, cross-references) | Done for the pilot and dev deeds; pool deeds partly | `src/graph/lease_parser.py`, `data/leases/` |
| Flat retrieval (BM25; dense BGE for comparison) | Done | `src/retrieval/` |
| `generate()` (hf 4-bit, Claude Code print mode, mock) | Done | `src/models/generate.py` |
| `verify()`: element-check prompt, parser, decision rules | Done | `src/models/verify.py` |
| Fixed pipeline (retrieve → verify per clause) | Done | `src/agent/pipeline.py` |
| Evaluation harness (defect recall/precision/F1, false-alarm rate, citation, section recall@k, by type and form) | Done | `src/eval/` |
| Training-pair generator with rule checks; QLoRA script | Done; four trials run (0 → 67 → 90 → 92 of 100 kept) | `src/train/`, `kaggle/` |
| Graph retrieval, controller agent, fine-tuned verifier | Phase 2 | — |

The fixed pipeline runs end to end on the dev set with the frontier model (B2), with and without retrieval.

---

## 2. Datasets

### Leases

28 real, executed Indian commercial lease deeds from SEC EDGAR exhibits and public templates (`data/sources.csv`): 5 pilot deeds, 3 spares (used for dev), 20 for the item pool. Cities: Bangalore (8), Chennai (4), Hyderabad (4), Gurgaon, Noida, Thane, New Delhi and others; executed 2003–2024, plus one blank 2026 PSU template. Text is converted from HTML; the wording is unchanged. All were executed after 8 Jan 1997, so the amended s.28(b) applies.

### Statute graph

Parsed from the India Code PDF of the Indian Contract Act, 1872.

| Nodes | | Edges | |
|---|---|---|---|
| Sections in force | 192 | `exception_to` (parsed) | 7 |
| Exceptions | 7 | `explains` (parsed) | 15 |
| Explanations | 15 | `illustrates` (parsed) | 201 |
| Illustrations | 201 | `refers_to` (regex, all 11 checked by eye) | 11 |

**How each kind of edge is built** (every edge records whether it was parsed, found by regex or added by hand):

| Edge | Method |
|---|---|
| `exception_to`, `explains`, `illustrates` | Parsed from the Act's own markers ("Exception 1.—", "Explanation.—", "Illustrations"). |
| `refers_to` between sections | Regular expression on "section N" in the text; all 11 hits checked by eye. Mentions of other Acts are skipped. |
| `interprets` (ruling → section) | **By hand** (Phase 2). With only 15–20 leading rulings, a team member reads each judgment and fills a sheet: citation, the section and limb it interprets, a one-sentence holding, and a source link; the lawyer checks the sheet. An LLM may suggest candidate rulings, but no edge is added without a person reading the judgment. |
| Lease `uses_term`, `refers_to` | Lease parser: defined terms in quotes or capitals, and "Clause N" / "sub-clause (x)" references (table below). |

### Parsed leases

The parser follows each deed's own numbering, as the lawyer and the answer keys cite it (`3(c)`, `9(II)(i)`, `5.5(d)`, `GTC-42A`, `E.1`, `AI.43A`), and extracts defined terms and clause references.

| | P01 | P02 | P03 | P04 | P05 | S01 | S02 | S03 |
|---|---|---|---|---|---|---|---|---|
| Clauses | 183 | 166 | 79 | 148 | 104 | 90 | 177 | 36 |
| Cross-references | 7 | 47 | 8 | 46 | 15 | 21 | 43 | 7 |

All 61 dev items, and every lease clause on their gold evidence paths, resolve to parsed clauses. On the 20 pool deeds, 38 of 70 items resolve so far; the rest use numbering the parser does not yet read (`3.3.Heading` with no space, lettered parts with roman sub-clauses, roman top-level clauses, `12.J`). Fixing these is the first Phase 2 parser task.

### Labelled items

| Set | Items | Status |
|---|---|---|
| **Dev** (`data/dev/items.jsonl`) | **61**: 20 pilot + 41 written into the spare deeds | Lawyer's blind labels agree with the key on 61/61 verdicts and 61/61 sections (on DV-03 the lawyer cites s.28 where the key cites its Exception 1) |
| Item pool (`data/pool/`) | 70 in 20 deeds; 25 are the deeds' own wording | Lawyer agrees on 66/70 verdicts; the 4 disagreements are logged for Session 2 |
| Test | target 340 | Drafted with an open model on Kaggle (Phase 2), frozen 6 Nov |

Dev mix:

| Type | Void | Valid | Hand off | Total |
|---|---|---|---|---|
| Restraint of trade (s.27) | 7 | 7 | 6 | 20 |
| Bar on proceedings (s.28(a)) | 8 | 8 | 4 | 20 |
| Time limit (s.28(a)/(b)) | 11 | 9 | 0 | 20 |
| Out of scope | | | 1 | 1 |

19 of the 61 items are **cross-clause**: the clause is void or valid only once a defined term or another clause is read with it.

### Element checklists

Before giving a verdict, the model fills in the elements of the clause's defect type; element accuracy is measured against the gold elements in the answer key. The elements, from PLAN.md section 6 as corrected by the lawyer in Session 1 (`ELEMENTS` in `src/common/schemas.py`):

| Defect type | Element | The question it answers | Allowed values |
|---|---|---|---|
| Restraint of trade (s.27) | `restrained_party` | Who is restrained? | tenant, landlord, both |
| | `restrained_activity` | From what? | trade_or_business (any business anywhere), premises_use (what these premises may be used for) |
| | `window` | When does the restraint run? | during_term, after_term, both |
| | `window_start_and_length` | Starting when, for how long, and where? | free text, e.g. "end of lease; 2 years; 3 km" |
| | `goodwill_sale` | Is it given on a sale of the business with its goodwill (Exception 1)? | yes, no |
| Bar on proceedings (s.28(a), first limb) | `restricted_party` | Whose right to sue is restricted? | tenant, landlord, both |
| | `rights_covered` | Which rights? | under_lease, other |
| | `degree` | Shut out entirely, or only partly? | absolute, partial |
| | `alternative_forum` | Where must disputes go instead? | arbitration (Exception 1), named_court, none |
| | `named_court_competent` | If a named court, would it otherwise have jurisdiction? | yes, no, cannot_tell |
| Time limit (s.28(a) second limb, s.28(b)) | `affected_party` | Whose time is limited? | tenant, landlord, both |
| | `what_is_limited` | The time to sue, or a step under the contract (e.g. a notice)? | time_to_sue, contractual_step |
| | `period_and_trigger` | How long, starting from what event? | free text, e.g. "6 months from the cause of action" |
| | `effect_on_expiry` | What happens when the time runs out? | claim_barred, right_extinguished, none |
| | `bank_guarantee` | Is it a bank guarantee's own claim period (Exception 3)? | yes, no (recorded; the lawyer advised that a lease clause is never the bank's own guarantee, so the rules ignore it) |

The decision rules in `src/models/verify.py` reproduce the gold verdict of every pilot item, and of every fixture item but FX-09 (labelled before the lawyer's correction), from its gold elements (tested).

---

## 3. Baselines

| | Model | Setting | Status |
|---|---|---|---|
| **B1** | Qwen2.5-7B-Instruct, 4-bit | Few-shot element-check prompt, no retrieval | **Run on dev** on a Kaggle T4 (section 5.2) |
| **B2** | Claude Opus 5.5 via Claude Code print mode, tools disabled | Same element-check prompt, one clause per call | **Run on dev** (section 5.2) |

B2 is described as "Claude via Claude Code print mode, tools disabled", not as an API call. Claude Code version and date are logged with each run.

---

## 4. Ablations

1. **No retrieval vs flat retrieval** (B2 model, dev): section 5.2.
2. **Flat retriever: BM25 vs dense embeddings**, and **with vs without illustrations** in the index: section 5.3.

The same no-retrieval vs flat ablation with the open model (B1): section 5.2.

---

## 5. Results

### 5.1 Pilot: frontier models on whole leases (Gate 0)

Each model read each of the 5 planted pilot deeds whole (6,900–14,700 words), in a fresh call with tools off and a neutral prompt that does not say clauses were planted, and listed every clause it judged void under s.27 or s.28. The deeds hold 20 labelled clauses: 9 void, 11 look-alikes (valid or hand off). Raw answers are saved; a flag is matched to an item by the quoted opening words of the clause, or by its clause number when the planted text sits inside an existing clause.

| Model (Claude Code 2.1.312, print mode, tools off) | Void caught | Missed | False alarms on look-alikes | Other clauses flagged |
|---|---|---|---|---|
| Claude Opus 5.5 | 9/9 | 0 | 1 (PL-15) | 0 |
| Claude Sonnet 5.5 | 9/9 | 0 | 0 | 0 |

Opus flagged PL-15 (P04 cl. 27.1, an exclusive-jurisdiction clause the key hands off) as partly void. Both caught PL-13, a claim bar planted in the last paragraph of a long hand-over clause. Neither model flagged any clause outside the 20 items.

**What this means.** On planted, single-deed defects, frontier models are already near ceiling, which matches the fallback the plan set for this outcome (PLAN.md section 2): the project's weight moves to (1) whether a **small open model** with retrieval and a fine-tuned verifier can approach this, (2) **cross-clause** items, where the clause is void only once a definition or another clause is read with it, and (3) **subtler look-alikes** (in-term restraints, expert determinations, periods at the statutory limit), which make up most of the 41 dev items written after the pilot. PLAN.md section 2 asks the team to stop and decide when the pilot shows (almost) no misses; this fallback is our proposal for that decision.

### 5.2 Baselines on dev: B2 with and without retrieval, and B1

Claude Opus 5.5 (Claude Code 2.1.314, print mode, tools off), one call per clause with the element-check prompt and five few-shot examples (the lawyer's own illustrations, not dev clauses). The model sees the clause alone; with flat retrieval it also sees the top 5 statute provisions (BM25). One run each (git commit `3386db5`); Claude Code offers no seed, so the three repeats come in Phase 3.

| Setting | Verdict accuracy | Defect recall | Defect precision | Defect F1 | False-alarm rate | Citation correct |
|---|---|---|---|---|---|---|
| B2, no retrieval | 0.82 | 0.88 (23/26) | 0.92 | 0.90 | 0.06 (2/35) | 0.92 |
| B2, flat retrieval | 0.80 | 0.88 (23/26) | 0.96 | 0.92 | 0.03 (1/35) | 0.92 |

By type and form (no retrieval):

| Slice | n | Verdict accuracy | Defect recall | False-alarm rate |
|---|---|---|---|---|
| Bar on proceedings | 20 | 0.85 | 1.00 | 0.00 |
| Time limit | 20 | 0.90 | 1.00 | 0.11 |
| Restraint of trade | 20 | 0.70 | 0.57 | 0.08 |
| **Single clause** | 42 | **0.88** | 0.94 | 0.00 |
| **Cross-clause** | 19 | **0.68** | 0.78 | 0.20 |

**What the errors are.** 12 of 61 items are wrong in at least one setting, and 11 of those are wrong in both. Most are over-cautious hand-offs: valid look-alikes (PL-08, PL-10, DV-03, DA-02, DA-07) and void restraints (DV-10, DV-12, DA-06) sent to a lawyer instead of decided. Two of the three misses (DV-12, DA-06) are restraints whose reach depends on a term defined in another clause (S02 Section 3(f), S01 cl. 15A.2), which the model never sees when it reads the clause alone; in the third (DV-10) it took the restraint for a goodwill sale under Exception 1. Both false alarms are cross-clause: DV-13 (a restraint whose window is fixed by the defined "Expiration Date") and DA-11 (a 3-year limit that runs from a defined "Limitation Date").

**Retrieval did not help B2.** Flat retrieval changed two items: DA-11 moved from a false "void" to a hand-off (still not the gold "valid"), and DV-17 moved from a correct "valid" to a hand-off. The frontier model already knows ss.27–28, so retrieved statute text adds little; what it lacks is the **lease's** context. This is the case for graph retrieval that follows the lease's own `uses_term` and `refers_to` edges to the definitions and linked clauses, and the main hypothesis for Phase 2. For the small open model (B1), which knows the statute less well, statute retrieval may matter more; that ablation runs on Kaggle.

**B1 and a second frontier model.** B1 is Qwen2.5-7B-Instruct in 4-bit on a Kaggle T4 (0.36 GPU-hours, git commit `b8476cd`), with the same element-check prompt and the clause alone. As a second frontier reference, Claude Sonnet 5.5 was run the same way.

| Setting | Verdict accuracy | Defect recall | Defect precision | Defect F1 | False-alarm rate | Citation correct | Cross-clause accuracy |
|---|---|---|---|---|---|---|---|
| **B1** Qwen2.5-7B (4-bit), no retrieval | 0.69 | 0.81 (21/26) | 0.84 | 0.82 | 0.11 (4/35) | 0.73 | 0.47 |
| B2 Claude Opus 5.5, no retrieval | 0.82 | 0.88 (23/26) | 0.92 | 0.90 | 0.06 (2/35) | 0.92 | 0.68 |
| B2 Claude Sonnet 5.5, no retrieval | 0.80 | 0.88 (23/26) | 1.00 | 0.94 | 0.00 (0/35) | 0.87 | 0.68 |

The open model is 0.08 F1 behind Opus and 0.12 behind Sonnet. The gap is in false alarms (PL-14, DV-13, DA-08, DA-11; two of them the clauses the lawyer called borderline), in cross-clause items, where it is right on fewer than half, and in citations on bar-on-proceedings clauses (0.35), mostly because it gives no provision for clauses it judges valid or hands off. Closing this gap with retrieval and a fine-tuned verifier is the project's main question.

**Choice of base model.** B1 was run the same way with two smaller open models, all in 4-bit on a Kaggle T4:

| Model | Parameters | Peak GPU memory | Verdict accuracy | Defect F1 | False-alarm rate | Cross-clause accuracy | GPU-hours |
|---|---|---|---|---|---|---|---|
| **Qwen2.5-7B-Instruct** | 7.6B | 5.1 GB | **0.69** | **0.82** | **0.11** | 0.47 | 0.36 |
| Phi-3.5-mini-instruct | 3.8B | 4.7 GB | 0.66 | 0.69 | 0.34 | 0.79 | 0.73 |
| Qwen2.5-3B-Instruct | 3.1B | 2.7 GB | 0.49 | 0.63 | 0.63 | 0.53 | 0.39 |

Qwen2.5-7B is the base model for fine-tuning: best F1 and by far the fewest false alarms. Phi-3.5-mini's high cross-clause accuracy comes with calling a third of the valid and hand-off clauses void, and Qwen2.5-3B calls nearly two-thirds of them void. All three fit in 11 GB, so they would also run on the Ada cluster. Phi-3.5-mini stays as the smaller model in the Phase 4 model comparison. (Qwen2.5-7B's peak memory is from the smoke test; the other two are from these runs.)

**Ablation with the open model: B1 with and without flat retrieval.** Qwen2.5-7B (4-bit), the same prompt, with the top 5 statute provisions from BM25 added (git commit `439b8a7`, 0.40 GPU-hours, peak 9.4 GB with the longer prompt).

| B1 Qwen2.5-7B | Items | Verdict accuracy | Defect recall | Defect precision | Defect F1 | False-alarm rate | Citation correct |
|---|---|---|---|---|---|---|---|
| No retrieval | 58 | 0.69 | 0.83 (20/24) | 0.83 | 0.83 | 0.12 (4/34) | 0.72 |
| Flat retrieval | 58 | 0.69 | 0.75 (18/24) | 0.90 | 0.82 | 0.06 (2/34) | 0.68 |
| No retrieval | 61 | 0.69 | 0.81 | 0.84 | 0.82 | 0.11 | 0.73 |
| Flat retrieval | 61 | 0.67 | 0.69 | 0.90 | 0.78 | 0.06 | 0.68 |

The no-retrieval run read each clause from the planted deed as cut by a stopgap script; the flat run read it from the lease parser. For 3 items (PL-09, PL-11, PL-13) the parser gives the whole clause where the stopgap gave only the planted paragraph, so the 58 items with the same text are the clean comparison. On them, statute retrieval leaves F1 unchanged and makes the small model more cautious: false alarms halve, and recall drops by two defects. Section recall@5 is 0.27, the BM25 figure in section 5.3: most retrieved provisions are not the gold one, so the model sees more statute text but mostly the wrong exception. As with B2, flat statute retrieval does not supply what the model lacks, the lease's own definitions; that is the case for graph retrieval in Phase 2. Re-running the no-retrieval arm on the parser's text is the first Phase 2 run.

Section recall@5 is 0 without retrieval by construction (no evidence path); with flat retrieval it is 0.27 (exact provision), as in section 5.3.

### 5.3 Retrieval: section recall@k on dev (60 items with a gold provision)

"Exact": the gold provision (e.g. `ICA-28-E1`) is in the top k. "Section": any node of the gold provision's section is.

| Retriever | exact@1 | exact@5 | exact@10 | section@1 | section@3 | section@5 |
|---|---|---|---|---|---|---|
| **BM25 over provisions (flat)** | 0.15 | 0.27 | 0.33 | **0.62** | 0.77 | **0.78** |
| Dense (BGE-small) over provisions | 0.17 | 0.32 | 0.42 | 0.33 | 0.45 | 0.55 |
| Dense, illustrations included | — | 0.23 | — | 0.20 | — | 0.40 |
| Dense, with BGE query prefix, illustrations included | — | 0.20 | — | 0.12 | — | 0.35 |
| Dense + BM25 (reciprocal rank fusion) | — | 0.25 | — | 0.32 | — | 0.60 |

By type (BM25, section@5): bar on proceedings 0.90, time limit 0.90, restraint of trade 0.55. Cross-clause items 0.84, single 0.76.

**Why.** Lease clauses and the statute share legal vocabulary ("suit", "proceeding", "arbitration", "restrain"), which BM25 matches exactly; a general-purpose embedding model instead matches on topic and pulls in illustrations about leases and bailment ("A lets B a house…"). Restraint-of-trade clauses rarely use the word "trade", so even BM25 misses s.27 for half of them. Exact recall is low because BM25 ranks Exception 3 to s.28 (bank guarantees, a long and lexically broad node) above the right exception. This is the gap graph retrieval targets: seed on the section, then expand along `exception_to` edges and rerank.

### 5.4 Training-pair generation trial (Qwen2.5-7B-Instruct, 100 pairs, rule checks)

| Run | Kept | Main rejection reasons | Fix |
|---|---|---|---|
| Trial 1 | 0/100 | wrong JSON shape (98), elements undecided (87), provision not allowed (25) | Show only the type's own elements, flat; list allowed provisions |
| Trial 2 | 67/100 | rules disagree with the verdict (27), wrong JSON shape (9) | Per-family hints for RT-2/3/4; drop unknown element names |
| Trial 3 | 90/100 | rules disagree (8), wrong JSON shape (4), wrong verdict (3) | Sharper RT-3/RT-4 hints; reject placeholder values |
| Trial 4 | 92/100 | rules disagree (5), unparseable (3) | RT-3 no longer generated (below); config frozen |

In trials 2 and 3 the rejections were real labelling mistakes caught by the rule checks, mostly in three restraint-of-trade families. The checks cannot catch a pair whose elements the model set to fit the rule: some RT-3 "goodwill sale" pairs only forbid selling the business. A hand check of trial 4 settled it: none of the 9 kept RT-3 pairs was a real sale of goodwill with the seller agreeing not to compete; each was a ban on selling the business plus a post-term non-compete, which is a void restraint, not the Exception 1 case. RT-3 is therefore not generated (`"generate": false` in the config) and gets a small set of hand-written pairs instead. RT-4 kept 8 of 11 in trial 4, up from 4; one of the 8 lets the restraint run past the term and is removed by the hand check every restraint-of-trade pair gets before training. The generation config is frozen from here, before any test item is written.

---

## 6. Challenges and mitigations

| Challenge | Mitigation |
|---|---|
| Late start; team down to three people from 26 Oct | Plan re-baselined to 21 days; work re-split (PLAN.md section 13); cut order fixed in advance (section 12) |
| No Ada (HPC) access | All GPU work on Kaggle (2× T4, ~30 GPU-h/week/account); jobs resume after the 12-hour cutoff |
| vLLM does not run on Kaggle (CUDA 13) | `hf` backend, 4-bit, batches of 8: 3.8 s per call |
| QLoRA memory on a T4 | Inputs capped at 1,536 tokens (measured), gradient accumulation |
| Small model gets the JSON wrong | Flat element sheet, allowed provisions listed, rule checks reject bad pairs (0 → 67 → 90 → 92 kept) |
| Lease numbering differs in every deed | Parser follows each deed's numbering; tested so that every dev item and gold-path clause resolves |
| Dense retrieval misses the statute | BM25 as flat retriever; graph expansion over exceptions in Phase 2 |
| Claude Pro usage limits for B2 | One clause per call, runs resume; fallback is a small amount of API credit for B2 only |
| Frontier model must not grade clauses it wrote | Test items are drafted with an open model on Kaggle, not Claude |
| Lawyer time is scarce | Three short sessions; blind second labelling within the team; agreement reported |

---

## 7. Timeline to the final submission (Sun 15 Nov)

| Phase | Dates | Work | Done when |
|---|---|---|---|
| 2. The real system | Sat 31 Oct – Wed 4 Nov | Graph retrieval (seed, expand, rerank) and ruling edges; tools `get_clause`, `lookup_definition`, `search_graph`, `expand`; controller agent; training pool (2,000 pairs) and first QLoRA run; 340 test items drafted; lawyer Session 2 | Full system end to end on dev; graph recall ≥ flat |
| 3. Freeze and measure | Thu 5 – Mon 9 Nov | Test set frozen Fri 6 Nov; retrieval frozen; learning curve (250–2,000 pairs); three seeds; results table v1 on test | Baselines and full system scored on test |
| 4. Ablations and write-up | Tue 10 – Fri 13 Nov | Flat vs graph vs none by type and form; no-adapter; model comparison; error analysis; report, slides, demo | Report draft complete |
| Buffer | Sat 14 Nov | Reruns, mock viva | |
| Final | Sun 15 Nov | Repository tagged `final` | |

---

## 8. Reproducing the numbers

```bash
pip install -r requirements-dev.txt && pytest -q                    # 68 tests
python -m src.graph.statute --pdf data/raw/statute/A1872-09.pdf     # statute graph (PDF from India Code)
python -m src.graph.lease_parser data/pilot/planted/*.txt data/dev/planted/*.txt --out data/leases
python -m src.retrieval.evaluate --modes flat dense                 # section 5.3
python -m src.eval.run --items data/dev/items.jsonl --leases data/leases \
    --model claude-opus-5-5 --backend claude_cli --mode none        # B2, section 5.2 (then --mode flat)
python -m src.eval.pilot --models claude-sonnet-5-5 claude-opus-5-5 # section 5.1
```

Run outputs (`runs/`) are not committed; every run writes its config, git commit, seed, platform and GPU hours there.
