# Implementation plan: Team ClosedAI, LMA Group Project 2026

**Project:** Statute-grounded enforceability checking for Indian commercial leases
**Window:** Sat 24 Oct to Fri 13 Nov 2026 (21 days), Sat 14 Nov as buffer
**Fixed dates (from the TAs, no extensions):**
- **Fri 30 Oct:** mid-submission (section 5, after Phase 1)
- **Sun 15 Nov:** final submission
- **16–19 Nov:** project evaluations and viva

**Based on:** `LMA_Proposal.pdf`, the review meeting of 5 Oct, `Major Project Feedback by TA-Team:ClosedAI.docx` and the TAs' updated timeline in `guidelines.md`

> Re-baselined on 24 Oct. The first version assumed a start on 12 Oct; that time is gone, so the same work is compressed into 21 days.

---

## 1. Who owns what

Each person owns one workstream, one branch prefix and one set of folders, so nobody edits another person's files.

| Person | Workstream | Branch prefix | Folders owned |
|---|---|---|---|
| **Prabhav** | Legal and data: lawyer liaison, leases, dev and test sets, rulings | `data/` | `data/`, `docs/legal/` |
| **Saksham** | Knowledge graph and retrieval, frontier baseline, second annotator | `graph/` | `src/graph/`, `src/retrieval/`, `src/baselines/` |
| **Amitabh** | Models, fine-tuning, compute (Kaggle now, Ada if approved), slides and demo | `model/` | `src/models/`, `src/train/`, `kaggle/`, `slurm/`, `report/slides/` |
| **Avnish** | Agent, evaluation harness, integration, written report | `agent/`, `eval/` | `src/agent/`, `src/eval/`, `report/` |

Saksham's and Amitabh's roles can be swapped if their skills fit better the other way round. Prabhav's is fixed because of the lawyer contact.

**All lawyer work belongs to Prabhav.** He is the only one who contacts the lawyer: scheduling, all three sessions (section 8), the element sign-off (section 6), checking the rulings list (section 7) and settling annotator disagreements. Anyone with a legal question sends it to Prabhav, who batches it into the next session.

**Estimated load** (rough, about ±30%): roughly six hours a day each, since the work now fits in 21 days instead of 30.

| Person | Hours | Timing |
|---|---|---|
| Avnish | about 130 | Back-loaded: agent, results and report pile up in the last two weeks |
| Prabhav | about 130 | Front-loaded: the dev and test sets block everyone else |
| Amitabh | about 130 | Includes waiting on unattended training and evaluation jobs |
| Saksham | about 125 | Even |

If one person is clearly ahead at a checkpoint, they take a task from whoever is behind.

---

## 2. Gate 0: three things before anyone builds (by Mon 26 Oct)

These come straight from the TA's second feedback. Nothing in section 5 starts until they are done.

| # | Gate | Owner | Done when |
|---|---|---|---|
| 1 | **Pilot on five leases** | Prabhav + Avnish | Misses and false alarms counted for two frontier models on about 12 planted defects and 8 look-alikes |
| 2 | **Validator decision** | Prabhav | Either a named lawyer has agreed, or the team records "two-member labelling" as the official method. Hard deadline Mon 26 Oct |
| 3 | **Kaggle smoke test** | Amitabh | A 7–8B model loads in 4-bit and generates on a Kaggle T4; a 20-step QLoRA run completes (section 9) |

**If the pilot shows no misses and no false alarms:** stop and meet. The fallback in the proposal applies: weight the project on the small-model question and on cross-clause items, and make the planted defects subtler.

---

## 3. Answers owed to the TA (second feedback)

| TA point | What we do | Owner | By |
|---|---|---|---|
| 1. Legal validator | Gate 0, item 2 | Prabhav | Mon 26 Oct |
| 2. Trial generation first | Generate 100 training pairs, run the rule checks, report the rejection rate and the reasons before generating more | Amitabh | Thu 29 Oct |
| 3. Pilot first | Gate 0, item 1 | Prabhav + Avnish | Mon 26 Oct |
| 4. How graph edges are built | Section 7 below | Saksham + Prabhav | Tue 27 Oct |
| 5. Elements per defect type | Section 6 below, signed off by the lawyer | Prabhav | Wed 28 Oct |

Avnish sends the TA a one-page note with these answers by Wed 28 Oct, and the same answers go into the mid-submission.

---

## 4. Working independently: shared contracts

Independence depends on agreeing the file formats first. Avnish merges these schemas and a tiny fixture set to `main` by Sun 25 Oct. Everyone then builds against the fixtures and mocks, not against each other's unfinished code.

**Statute graph** (`data/statute/nodes.jsonl`, `edges.jsonl`)
```json
{"id": "ICA-27", "type": "section", "label": "Section 27", "text": "..."}
{"id": "ICA-27-E1", "type": "exception", "label": "Exception 1 to Section 27", "text": "..."}
{"src": "ICA-27-E1", "dst": "ICA-27", "type": "exception_to", "source": "parsed"}
```
Node types: `section`, `exception`, `explanation`, `illustration`, `ruling`. Edge types: `exception_to`, `explains`, `illustrates`, `refers_to`, `interprets`. Every edge carries `source`: `parsed`, `regex` or `manual`.

**Lease** (`data/leases/<lease_id>.json`)
```json
{"lease_id": "L03",
 "clauses": [{"clause_id": "L03-14", "number": "14", "heading": "...", "text": "..."}],
 "definitions": [{"term": "Restricted Period", "clause_id": "L03-1.1", "text": "..."}],
 "refs": [{"src": "L03-14", "dst": "L03-1.1", "type": "uses_term"}]}
```

**Labelled item** (`data/dev/items.jsonl`, `data/test/items.jsonl`)
```json
{"item_id": "T-0142", "lease_id": "L03", "clause_id": "L03-14",
 "defect_type": "restraint_trade", "form": "cross", "phrasing_family": "RT-3",
 "gold_verdict": "void", "gold_provision": "ICA-27",
 "gold_elements": {"restrained_activity": "trade_or_business", "window": "after_term"},
 "gold_path": ["L03-1.1", "ICA-27", "ICA-27-E1"]}
```
`defect_type`: `restraint_trade`, `bar_proceedings`, `time_limit`, `out_of_scope`. `gold_verdict`: `void`, `valid`, `handoff`.

**Prediction** (`runs/<run_id>/preds.jsonl`), the only thing the evaluation harness reads
```json
{"item_id": "T-0142", "verdict": "void", "cited_node": "ICA-27",
 "path": ["L03-1.1", "ICA-27"], "elements": {...},
 "tool_calls": [{"tool": "lookup_definition", "args": {"term": "Restricted Period"}}],
 "tokens_in": 2310, "tokens_out": 180}
```

**Function interfaces**
```python
generate(prompts: list[str], model: str, **kw) -> list[str]          # Amitabh; backends: hf, claude_cli, mock
retrieve(clause_id, lease, mode: "none"|"flat"|"graph", k=5) -> dict  # Saksham; returns {"nodes": [...], "path": [...]}
verify(clause_text, evidence, elements) -> dict                       # Amitabh; returns {"verdict", "provision", "confidence"}
run_agent(lease, config) -> list[Prediction]                          # Avnish
```

**Mocks until the real thing lands:** `retrieve` returns the gold path from the fixtures; `verify` calls the untuned base model; `generate` has a `mock` backend that needs no GPU.

---

## 5. Schedule (Sat 24 Oct – Sun 15 Nov)

Each phase ends in a checkpoint on the evening shown: merge to `main`, run the fixtures end to end, 30-minute call.

### Phase 0: setup and gates (Sat 24 – Mon 26 Oct)

| Person | Work |
|---|---|
| Prabhav | Contact the lawyer today and ask for three short sessions (section 8); if there is no yes by Mon 26, record two-member labelling as the method. Collect the first five leases. Plant defects and run the pilot with Avnish. |
| Saksham | Parse the India Code PDF of the Contract Act into section, exception, explanation and illustration nodes. |
| Amitabh | Get all four Kaggle accounts phone-verified today, which GPU and internet access need (section 9). Kaggle smoke test. Kaggle runner notebook. `generate()` wrapper with `hf`, `claude_cli` and `mock` backends. Keep the Ada request going in parallel; write the Slurm templates only once access lands. |
| Avnish | Private repo, branch rules, schemas, fixtures (1 lease, 10 items, 8 statute nodes), a test that runs on them, all by Sun 25. Pilot with Prabhav. |

### Phase 1: components (Tue 27 – Fri 30 Oct) → Checkpoint 1 Thu 29 Oct, mid-submission Fri 30 Oct

| Person | Work | Done when |
|---|---|---|
| Prabhav | Lawyer session 1: element checklists and look-alikes. Collect 15–20 leases as clean text. Write the **dev set of 60 items**; the pilot leases and items go into it. | Dev set merged by Thu 29; element sheet signed off |
| Saksham | Statute graph with parsed and regex edges. Lease parser: clauses, definitions, cross-references. Embedding index. **Flat top-k retrieval.** Frontier baseline script (B2) through Claude Code print mode. | Section recall@5 reported on dev; B2 predictions on dev |
| Amitabh | Few-shot baseline (B1) on dev. Choose two or three base models that fit a 16 GB T4 in 4-bit, noting which also fit 11 GB in case Ada arrives. **Trial of 100 generated pairs** with rule checks. Run the item-drafting job on Kaggle for Prabhav. | B1 numbers; rejection-rate note; first item drafts handed over |
| Avnish | **Evaluation harness**: every metric in the proposal, from a `preds.jsonl`. Element-check prompts for the three types. **First ablation on dev:** the base model with no retrieval against flat retrieval. Assembles the mid-submission. | Harness scores B1 and B2 on dev; mid-submission sent Fri 30 |

All Phase 1 GPU work runs on Kaggle and does not wait for Ada.

**Mid-submission (Fri 30 Oct).** The TAs ask for each item below. All numbers are on the dev set; the test set is not built yet, and that is stated.

| Required | What we submit | Owner |
|---|---|---|
| Progress | Gate 0 outcomes, which components are merged and working end to end | Avnish |
| Datasets | Lease sources (`data/sources.csv`), the 60-item dev set, statute graph node and edge counts, element checklists (section 6) | Prabhav, Saksham |
| Baselines | B1 (few-shot open model) and B2 (frontier model) on dev | Amitabh, Saksham |
| Ablations | No retrieval against flat retrieval on dev | Avnish |
| Results | Pilot misses and false alarms, flat recall@5, B1 and B2 scores, trial-generation rejection rate | Everyone, collected by Avnish |
| Challenges and mitigations | Late start, 11 GB GPUs, validator status, Claude Pro limits, with the fallback for each | Avnish |
| Timeline | Phases 2–4 of this plan | Avnish |
| Code | Everything merged to `main` by Thu 29 evening and tagged `mid-v1` | Everyone |

### Phase 2: the real system (Sat 31 Oct – Wed 4 Nov) → Checkpoint 2 Wed 4 Nov

| Person | Work | Done when |
|---|---|---|
| Prabhav | Grow the item pool to **340 test items**: drafted with an open model on Kaggle (not Claude, see section 9), then edited by hand. Hand items to Saksham in batches for blind labelling. Lawyer session 2: review of a 40-item sample. Fill the rulings sheet (section 7). | 340 items drafted by Tue 3; rulings sheet done |
| Saksham | **Graph retrieval**: seed, expand one or two hops, rerank. Ruling edges added. Tools: `get_clause`, `lookup_definition`, `search_graph`, `expand`. Start **blind second labelling** of test items as batches arrive. | Evidence-path recall beats or matches flat on dev |
| Amitabh | Generate the training pool with an open model on Kaggle (2,000 kept pairs, one phrasing family held out). First QLoRA run at 250 pairs. `verify()` served from the adapter. | Adapter loads inside the agent |
| Avnish | **Controller agent**: step loop, state, step budget, hand-off, tool-call log. Fixed-pipeline variant. Three reasoning variants. | Full system runs end to end on dev |

### Phase 3: freeze and measure (Thu 5 – Mon 9 Nov) → Checkpoint 3 Mon 9 Nov

| Person | Work | Done when |
|---|---|---|
| Prabhav | Fix items from the second-annotator pass. Lawyer session 3. **Freeze the test set on Fri 6 Nov.** Gold tool traces for 30 clauses. | Test set tagged `test-v1` |
| Saksham | Finish blind second labelling by Thu 5. Tune retrieval on dev only, then freeze by Fri 6. Graph statistics for the report. | Retrieval tagged `retrieval-v1`; agreement reported |
| Amitabh | **Learning curve** at 250, 500, 1,000, 2,000. Choose the size. Two more seeds. Model-comparison runs. | Adapter tagged `verifier-v1` by Sat 7 |
| Avnish | Run-all script that splits the configurations into 12-hour chunks across the four Kaggle accounts (or a Slurm job array if Ada is active), launched as background runs before the Diwali weekend (Sat 7 – Sun 8) so it runs unattended. **Results table v1** on the frozen test set. | Baselines and full system scored by Mon 9 |

### Phase 4: ablations and write-up (Tue 10 – Fri 13 Nov) → Checkpoint 4 Fri 13 Nov

| Person | Work |
|---|---|
| Prabhav | Legal commentary on the failure cases. Stretch: 20–30 real clauses from reported judgments. Writes the dataset and validation sections. |
| Saksham | Flat against graph against none, by defect type and form. Retrieval error analysis. Writes the architecture and graph sections, with the figures. |
| Amitabh | No-adapter ablation, model-comparison table, learning-curve plot, compute accounting. Writes the fine-tuning section. **Slides and demo.** |
| Avnish | Remaining ablations and seeds. Ten worked hard cases with Prabhav. Assembles the written report. |

**Sat 14 Nov:** buffer for reruns and polish, no new experiments. Mock viva: each person explains every component, not only their own, because the TAs will ask why behind every decision.

**Sun 15 Nov:** final submission. Repository tagged `final`.

**16–19 Nov:** evaluations and viva.

---

## 6. Element checklists (draft, for the lawyer to confirm)

These are what "element accuracy" is scored against. They are a first draft from the text of the Act and must be signed off in lawyer session 1.

**Post-term restraint of trade (Section 27)**

| Element | Values |
|---|---|
| `restrained_party` | tenant / landlord / both |
| `restrained_activity` | trade or business generally / use of the premises only |
| `window` | during term only / after term / both |
| `window_start_and_length` | trigger (expiry, termination) and duration, resolved from definitions if needed |
| `goodwill_sale` | yes / no (Exception 1) |

Draft rule: **void** if the activity is a trade or business and the window runs after the term and there is no sale of goodwill. **Valid** if it only limits use of the premises during the term. **Hand off** if goodwill is sold, since reasonableness is for a court.
*Question for the lawyer:* how to treat a restraint on business elsewhere that applies only during the term.

**Absolute bar on legal proceedings (Section 28(a), first limb)**

| Element | Values |
|---|---|
| `restricted_party` | tenant / landlord / both |
| `rights_covered` | rights under or in respect of the lease / other |
| `degree` | absolute (no forum, or one party's decision is final) / partial (forum chosen) |
| `alternative_forum` | arbitration / one named court / none |
| `named_court_competent` | yes / no / cannot tell |

Draft rule: **void** if absolute with no arbitration. **Valid** if it refers disputes to arbitration (Exception 1) or picks one court that already has jurisdiction. **Hand off** if the named court's jurisdiction cannot be told from the lease.

**Time limit that cuts off claims (Section 28(a), second limb, and Section 28(b))**

| Element | Values |
|---|---|
| `affected_party` | tenant / landlord / both |
| `what_is_limited` | time to sue or claim / time for a contractual step (notice, cure, payment) |
| `period_and_trigger` | length and starting event |
| `effect_on_expiry` | claim barred / right extinguished or liability discharged / none on the right to sue |
| `bank_guarantee` | yes / no (Exception 3) |

Draft rule: **void** if the clause limits the time to sue or extinguishes the right after a period. **Valid** if the period governs only a contractual step. **Hand off** if it is a bank guarantee.
*Question for the lawyer:* whether any contractual period shorter than the statutory limitation period counts, and what that period is for lease claims.

---

## 7. How graph edges are built

| Edge | Method | Who |
|---|---|---|
| `exception_to`, `explains`, `illustrates` | Parsed from the Act's own headings ("Exception 1.—", "Explanation.—", "Illustrations") | Saksham |
| `refers_to` between sections | Regular expression on "section N" in the text, then every hit checked by eye (the Act has only about 25) | Saksham |
| `interprets` (ruling → section) | **Manual.** With only 15–20 rulings, Prabhav reads each one and fills a sheet: citation, section and limb interpreted, one-sentence holding, source link. An LLM may suggest candidates, but no edge is added without a human reading the ruling. | Prabhav, lawyer checks the list |
| Lease `uses_term`, `refers_to` | Parser: defined terms in capitals or quotes, and "Clause N" references | Saksham |

Every edge stores how it was made, so the report can state how many edges are parsed and how many are manual.

---

## 8. Prabhav's lawyer sessions

Three short sessions keep the ask small. Offer acknowledgement in the report, with permission.

| Session | When | Ask | Time needed |
|---|---|---|---|
| 1 | by Wed 28 Oct | Confirm the three defect types, the look-alikes and the element checklists in section 6. Suggest 15–20 leading rulings on Sections 27 and 28. | about 45 minutes |
| 2 | by Tue 3 Nov | Yes or no on a 40-item sample: is the verdict right, is the provision right. | about 1 hour |
| 3 | by Thu 5 Nov, before the freeze | As many of the remaining test items as they can do, hardest first (cross-clause and look-alikes). | 2–3 hours |

If the lawyer can only do sessions 1 and 2, the remaining items rely on two-member labelling, and the report says exactly how many items the lawyer checked.

**Second annotator:** Saksham labels all test items blind as they are drafted, finishing by Thu 5 Nov. Agreement is reported, and Prabhav takes the disagreements to the lawyer. The second annotator has to be someone other than Prabhav, or the agreement figure means nothing.

---

## 9. Compute: Kaggle now, Ada if approved

**Status on 24 Oct:** the team has no Ada access. All GPU work runs on Kaggle until Ada is approved. The code stays portable: `generate()` and the training scripts take paths and settings from the config, so the same commit runs on Kaggle, Ada or a laptop with the `mock` backend.

### Kaggle (primary)

**What we get** (Kaggle does not publish the quota and it changes; each person checks their own account)

- Two T4s (**16 GB** each) or one P100 (16 GB) per session. T4 has no bf16, so use fp16.
- About **30 GPU-hours a week per account**, so about 120 a week across the four of us.
- Sessions stop after **12 hours**. "Save & Run All" runs a notebook in the background with the browser closed.
- GPU and internet access need a phone-verified account. **One account per person**: Kaggle's rules forbid extra accounts.

**What that means for us**

- **GPU hours are the constraint**, not memory. Every run logs its GPU hours, and Amitabh reports the team's remaining quota at each checkpoint.
- **Memory is easier than on Ada.** 16 GB leaves room for QLoRA on a 7–8B model; the smoke test finds the longest input that fits (aim for 1,024 tokens).
- **Use vLLM for inference** where the model supports it. Batched generation is several times faster than plain `transformers`, and the Phase 3 test runs need it to fit the quota.
- **Every job must survive a 12-hour cutoff.** Training saves a checkpoint at least every 30 minutes and can resume; evaluation writes predictions as it goes and skips items already done.
- **Spread jobs across accounts.** Each person runs their own share of configurations from their own account, never someone else's.
- **Keep everything private.** Notebooks and datasets stay private, since they hold the leases and the test set. A public notebook would leak the test set.

**Smoke test checklist (Amitabh, by Mon 26 Oct)**

- [ ] All four accounts phone-verified; GPU and internet switch on in a notebook
- [ ] The private repo clones using a GitHub token stored in Kaggle Secrets
- [ ] `bitsandbytes` 4-bit loading works on T4 and on P100
- [ ] One generation timed, to replace the 3-seconds-per-call guess in the proposal; the same with vLLM
- [ ] 20-step QLoRA run completes; note peak memory and the longest input that fits
- [ ] A checkpoint saved, the session restarted, and training resumed from it
- [ ] A background run ("Save & Run All") finishes and its output can be downloaded

**Runner notebook** (`kaggle/run.ipynb`): one notebook, the config is the only thing that changes
```python
from kaggle_secrets import UserSecretsClient
token = UserSecretsClient().get_secret("GH_TOKEN")           # never paste the token into a cell
!git clone -q https://{token}@github.com/<org>/<repo>.git repo
%cd repo
!git checkout <commit>                                         # pin the commit for every logged run
!pip install -q -r requirements.txt
!python -m src.eval.run --config configs/<config>.yaml --out /kaggle/working/runs
```

Storage rule: code comes from git, model weights download from Hugging Face at the start of each session, and run outputs go to `/kaggle/working/runs/<run_id>/`. After each run, the owner copies the outputs out (download, or save them as a private Kaggle Dataset). Anything not copied out is lost when the session's output is replaced.

**Colab** is for debugging and the demo only: free sessions disconnect when idle and sometimes get no GPU, so no logged run depends on it.

**If the quota runs short:** cut extra seeds early (section 12, item 4). Paid fallback: Colab Pro or a few hours of rented GPU for the Phase 3 runs only.

### Ada cluster (if access is approved)

Amitabh keeps the request going. If Ada arrives, long training and the Phase 3 test runs move there and Kaggle stays for short jobs.

**What the guide says**

- Each node has four GPUs with **11 GB** each: GTX 1080 Ti on nodes 01–40, RTX 2080 Ti on nodes 43–92.
- `research` account, `medium` QoS: up to 4 GPUs, 40 CPUs and 4 running jobs per user; 4-day limit per job.
- Interactive sessions are for debugging and limited to 6 hours. Long runs go through `sbatch`.
- Keep 10 CPUs per GPU. Memory is capped at 3 GB per CPU, so about 30 GB of RAM per GPU.
- `/home` is small (25–50 GB). `/scratch` and `/ssd_scratch` are local to each node and purged after about a week.
- Accounts must not be shared. Access is for research students; others need a faculty advisor's endorsement.

**What that means for us**

- **GPU hours stop being the constraint.** Four people with four GPUs each can run every configuration in parallel as separate one-GPU jobs.
- **Memory is the constraint.** The proposal assumed 16–24 GB; Ada has 11 GB per GPU. A 7–8B model in 4-bit should run for inference (about 6 GB). QLoRA should fit only with short inputs (512 tokens or fewer), batch size 1 with gradient accumulation, and gradient checkpointing. The Ada smoke test confirms this. Settings tuned on Kaggle's 16 GB may need shorter inputs here.
- **Fallback if it does not fit:** a 3–4B model as the verifier, or split one model across two GPUs.
- **Prefer the 2080 Ti nodes** (43–92) for training.

**Ada smoke test checklist (Amitabh, once access lands)**

- [ ] All four accounts requested from `hpc.admin@iiit.ac.in`, with faculty endorsement if needed (send now if not already sent)
- [ ] `nvidia-smi`: note the driver version
- [ ] A current PyTorch build installs and sees the GPU. The nodes run Ubuntu 18.04, which may be too old for recent wheels; if so, use the Singularity module with a container, or pin an older PyTorch
- [ ] `bitsandbytes` 4-bit loading works on both GPU types
- [ ] Whether compute nodes can reach Hugging Face; if not, download on the login node
- [ ] One generation timed, to replace the 3-seconds-per-call guess in the proposal
- [ ] 20-step QLoRA run completes at 11 GB

**Job template** (`slurm/job.sh`)
```bash
#!/bin/bash
#SBATCH -A research
#SBATCH --qos=medium
#SBATCH -p long
#SBATCH -c 10
#SBATCH --gres=gpu:1
#SBATCH --mem-per-cpu=2900M
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x-%j.out

export HF_HOME=/ssd_scratch/$USER/hf          # weights on local scratch, not /home
mkdir -p "$HF_HOME" logs
python -m src.eval.run --config "$1"          # print with flush=True
```

Storage rule: code in `/home`, model weights and run outputs on `/share1/$USER`, copied to `/ssd_scratch` at job start. Anything left only on scratch will be deleted.

**Frontier model without an API key**

The team has Claude Code Pro, so no API key is bought. A one-call trial on 10 Oct worked: tools off, own system prompt, JSON out, one turn.

```bash
cat lease_L03.txt | claude -p "<instruction>" \
  --tools "" --system-prompt "<reviewer prompt>" \
  --model <model> --output-format json > runs/b2/L03_run1.json
```

| Use | How |
|---|---|
| Frontier baseline (B2) | Saksham scripts the command above over the lease variants, three repeats each, from a laptop |
| Training pairs | Amitabh generates them with an open model on Kaggle |
| Test-item drafts | An open model on Kaggle, so the baseline is never scored on clauses Claude wrote |
| Pilot | Chat window |

Rules for the baseline:

- Pin the model with `--model` and record its name, the Claude Code version and the date of each run.
- Keep `--tools ""` and a fixed `--system-prompt`, so it is a single pass with no agent behaviour.
- There is no temperature or seed control: "three seeds" means three repeated runs.
- In the report, describe it as "Claude via Claude Code print mode, tools disabled", not as a plain API call.
- Pro has usage limits. Run in batches over several days and save every raw JSON output.
- Check that the current subscription terms allow scripted research runs like this.

**Fallback:** if the limits or the terms get in the way, buy a small amount of API credit for B2 only. The script changes by one backend.

---

## 10. Git rules

- Private repository. `main` is protected: changes arrive by pull request with one reviewer and a passing fixture test.
- Branch names: `<prefix>/<short-topic>`, for example `graph/lease-parser`.
- Stay inside your own folders. A change to a schema in section 4 needs all four to agree.
- Merge small and often; rebase on `main` before each checkpoint.
- Never commit model weights, API keys, GitHub tokens or raw lease PDFs. Tokens used on Kaggle live only in Kaggle Secrets. Commit cleaned text and a `data/sources.csv` listing where each lease came from.
- Tag the frozen pieces: `mid-v1`, `test-v1`, `retrieval-v1`, `verifier-v1`. Final numbers come only from tagged versions.

---

## 11. Rules that protect the results

- **Dev and test are separate.** Prompts, retrieval and the agent are tuned on the 60-item dev set only.
- **The test set is frozen on Fri 6 Nov.** Before that, only Prabhav (and Saksham for blind labelling) open it. After that, nobody edits it. Mid-submission numbers come from the dev set only.
- **No training data from test leases.** Training pairs come from a separate generation process, and one phrasing family per defect type is held out.
- **Every run is logged** with its config, git commit, seed, platform, GPU type and GPU hours in `runs/<run_id>/`.

---

## 12. If the schedule slips

Cut in this order; the main research question survives all of them.

1. Real-clause slice from judgments
2. Model comparison across base models
3. Reasoning variants
4. Extra seeds (keep three seeds only for the full system and naive RAG)
5. Test set down from 340 to about 240, keeping all three types and both forms

Do not cut: the pilot, the frozen test set, naive RAG against graph RAG, the frontier baseline, the no-retrieval and no-adapter ablations.
