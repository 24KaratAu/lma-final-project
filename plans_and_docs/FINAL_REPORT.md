# Final report: Team ClosedAI

**Project:** Statute-grounded enforceability checking for Indian commercial leases
**Date:** Sun 15 Nov 2026 · **Repository:** https://github.com/24KaratAu/lma-final-project (tag `final`)
**Team:** Saksham Goyal (data, legal validation, statute graph, retrieval), Avnish Uba (agent, fine-tuning, evaluation), Amitabh Anand (training-pair generation trials, base-model choice, B1 baseline and flat-retrieval ablation for the mid-submission)

Numbers marked **dev** are on the 61-item dev set, where every choice was made. Numbers marked **test** are on the frozen test set `test-v1` (340 items), which was run once per configuration after the freeze.

> **Draft status (15 Nov, 17:30).** Sections 1 and 5 to 9 are complete, with all eight configurations run on the test set. Sections 2, 3, 4 and 8.2 are Saksham's and are marked.

---

## 1. Question and hypotheses

Given one clause of an Indian commercial lease, decide whether it is **void** under Section 27 (restraint of trade) or Section 28 (restraint of legal proceedings, including time limits) of the Indian Contract Act, 1872, **valid**, or should be **handed off** to a lawyer; cite the provision; and show the evidence path through the statute and the lease.

The research question is whether a small open model (Qwen2.5-7B-Instruct, 4-bit, on free T4 GPUs) can do this as well as a frontier model when it is given the statute as a graph, the lease's own cross-references, a verifier tuned on synthetic pairs, and an agent loop that gathers the evidence.

| | Hypothesis (proposal, section 3) | Result | Where |
|---|---|---|---|
| H1 | Grounding in the statute raises defect recall and lowers false alarms, against the ungrounded model | **Half supported:** false alarms fall, recall falls too | 7.4 |
| H2 | Graph retrieval beats flat top-k, most on items that need an exception or a second clause | **Supported for retrieval, mixed end to end:** the exact provision is found for 66% of items against 22%, but in the plain pipeline F1 is the same as flat (0.81); in the agent it is 0.03 higher, most on cross-clause items | 4, 7.6 |
| H3 | The tuned small model reaches defect F1 within a margin of the frontier single-pass baseline | **Not supported:** 0.808 against 0.884, a gap of 0.076 where the margin was 0.05 | 7.5 |
| H4 | Verifier accuracy levels off before 2,000 training pairs | **Not supported on dev:** accuracy is still rising at 2,000 | 6.3 |

The premise behind the proposal, that frontier models miss these defects, did not survive the pilot (mid-submission, section 5.1: 9 of 9 planted defects found). The project therefore asks the narrower question above: how close a small, local, inspectable system gets.

**The answer in one paragraph.** The untuned 7B model is already within 0.047 F1 of the frontier model (0.837 against 0.884). The best small-model configuration on the test set is the agent with its tools in a fixed order and **no** adapter (F1 0.842, false alarms 0.10). The two things we expected to close the gap, the tuned verifier and the model-driven controller, both looked better on dev and both were worse on test: the full system scores 0.808. The tuned verifier learned to hand clauses off. It gets 85% of the hand-off items right where the base model gets 37%, but it also hands off 42 valid and 28 void clauses. On cross-clause items every small-model configuration matches or beats the frontier model.

---

## 2. Dataset

*Saksham's section: leases and sources, the item families, how the 340 test items were written into 20 real deeds, dev and test composition.*

For reference by the later sections, the test set has 340 items: 154 void, 113 valid and 73 hand-off; 100 restraint of trade, 102 bar on proceedings, 100 time limit and 38 out of scope; 241 single-clause and 99 cross-clause. The dev set has 61 items (26 void).

## 3. Validation of the labels

*Saksham's section: blind labelling by a practising lawyer, agreement (260 of 270 verdicts and 266 of 270 sections on the new items), Session 2, corrections, the rulings sheet.*

## 4. Statute graph and retrieval

The verifier decides on the text it is given. This section describes where that text comes from: the Contract Act as a graph, and each lease's own links between its clauses. It also covers the two ways the pipeline configurations of section 7 retrieve from them. The code is in `src/graph/` and `src/retrieval/`, and the data in `data/statute/` and `data/leases/`.

### 4.1 The statute graph

The graph is built from the India Code text of the Indian Contract Act, 1872 (`src/graph/statute.py`). It has 192 sections in force, 7 exceptions, 15 explanations, 201 illustrations and 17 rulings. Ids follow the Act: `ICA-28` is a section, `ICA-28-E1` its first exception, `ICA-28-X1` its explanation and `ICA-29-Ia` an illustration. Repealed sections are left out. The wording is as printed, without footnotes or amendment brackets.

| Edge | From → to | Count | How it is made |
|---|---|---|---|
| `exception_to` | exception → its section | 7 | parsed from the Act's layout |
| `explains` | explanation → its section | 15 | parsed |
| `illustrates` | illustration → its section | 201 | parsed |
| `refers_to` | section → a section it names | 11 | found by pattern, each checked by hand |
| `interprets` | ruling → the provision it interprets | 17 | by hand, from the rulings sheet |

**Rulings.** In Session 1 the lawyer listed 18 leading judgments on ss.27 and 28. A judgment became a ruling node only once one of us had read it and written its holding in one sentence of our own (`data/statute/rulings.csv`, built by `src/graph/rulings.py`). The sheet records the source, the reader and the date. The lawyer's own one-line notes never enter the graph.

Seventeen were read: five on s.27, three on the choice of court and three on time limits under s.28, and six on Exception 1 (arbitration). The eighteenth, *Madhub Chunder* (1874), has no reliable text online, so it stays out until it has been read.

The lawyer checked the 17 holdings, corrected three (Nos. 5, 15 and 18) and signed off the revised sheet. The summaries state each court's holding correctly for the purposes of the project. The sign-off covers the summaries, not the system's outputs (`docs/legal/rulings_review.md`).

### 4.2 The lease's own links

The lease parser (`src/graph/lease_parser.py`) splits each deed into clauses in the deed's own numbering (`12A`, `5.5(d)`, `XXVIII(d)`). A clause's text includes its sub-clauses. The parser lists the defined terms and adds two kinds of link:
- `uses_term`, from a clause to the definition of a term it uses;
- `refers_to`, from a clause to another clause it cites by number.

The 20 test deeds have 2,108 clauses, 109 definitions, 621 `uses_term` links and 213 `refers_to` links. These links are what make a cross-clause item answerable: of the 102 lease clauses that the test set's cross-clause items depend on, 84 are one link from the target clause.

### 4.3 Flat retrieval

BM25 over the 214 provisions (sections, exceptions and explanations; illustrations are left out), queried with the clause text. The top 5 are the evidence. BM25 was chosen over dense embeddings on dev for the mid-submission. BGE-small found the right section in the top 5 for 55% of items, against 78% for BM25, because it matched on topic and pulled in illustrations about leases and bailment.

### 4.4 Graph retrieval

Graph retrieval (`src/retrieval/graph.py`) builds the evidence in five steps:

1. **Seed.** The 3 provisions that BM25 ranks highest for the clause text.
2. **Expand.** One hop from each seed along `exception_to` and `explains`, in both directions, and along `refers_to`. A neighbour takes its seed's score, or its own if that is higher.
3. **Rerank.** The 5 highest-scoring provisions are kept.
4. **Rulings.** Of the rulings that interpret those 5 provisions, up to 3 whose holding best matches the clause, by BM25 on the holding with the case names removed. A ruling that shares no word with the clause is left out.
5. **Lease clauses.** The clauses and definitions the target clause links to, one hop out. Two more come by rule, because the lawyer's element checklists ask for them and no link points to them:
   - for a clause about disputes, courts or final decisions, the deed's arbitration clause;
   - for a clause tied to the end of the lease, the deed's term clause.

   Each lease clause is cut to its first 1,500 characters (section 4.8).

The evidence path lists the provisions first, then the rulings, then the lease clauses, so exact provision recall@5 reads only statute nodes.

**Settings, chosen on dev only** (60 items with a gold provision):
- **3 seeds, no decay on expansion, and the clause text alone as the query.** Adding the linked lease clauses to the query made the seeds noisier: exact provision recall@5 fell from 0.75 to 0.68.
- **One hop on the lease side.** A second hop found nothing more.
- **Rulings picked by how well their holding matches the clause.** Taking rulings in provision order gave every s.28 clause the same three jurisdiction cases. Time-limit items then got a time-limit ruling in 0 of 20 cases, against 18 of 20 with matching.

The settings were frozen and tagged `retrieval-v1` (commit `d86d757`) before retrieval was measured on the test set.

**How this differs from the agent's evidence** (section 5.1):
- **Seeds:** the fixed-policy agent searches with 5 seeds and passes the first 8 statute nodes it finds.
- **Rulings:** the agent adds none.
- **Lease clauses:** it reads only the clauses the target links to, with no arbitration or term clause by rule.

### 4.5 Retrieval results

Retrieval alone, scored against the gold provision and the gold evidence path (`src/retrieval/evaluate.py`). Out-of-scope items have no gold provision and are skipped. "Section" counts any node of the gold provision's section. "Lease" is the share of the gold path's lease clauses that are found, on items whose gold path has any.

| | Dev, flat | Dev, graph | **Test, flat** | **Test, graph** |
|---|---|---|---|---|
| Items | 60 | 60 | 302 | 302 |
| Exact provision recall@1 | 0.15 | 0.50 | 0.11 | 0.36 |
| Exact provision recall@5 | 0.27 | 0.75 | **0.22** | **0.66** |
| Section recall@5 | 0.78 | 0.75 | **0.73** | **0.66** |
| Section recall@10 | 0.80 | 0.77 | 0.82 | 0.66 |
| Lease clauses of the gold path found | 0 | 0.75 | 0 | **0.91** |

On the test set, by type and form (exact provision recall@5 / section recall@5):

| | Restraint of trade (100) | Bar on proceedings (102) | Time limit (100) | Single clause (203) | Cross-clause (99) |
|---|---|---|---|---|---|
| Flat | 0.09 / 0.66 | 0.31 / 0.82 | 0.26 / 0.70 | 0.19 / 0.71 | 0.29 / 0.76 |
| Graph | 0.60 / 0.60 | 0.76 / 0.77 | 0.60 / 0.60 | 0.64 / 0.64 | 0.69 / 0.70 |

- **Graph retrieval finds the exact provision three times as often** (0.66 against 0.22), on every type and form. A section's exceptions and explanations come with it. The right exception arrives with its section instead of having to win on shared words. Flat retrieval often ranks Exception 3 to s.28 (bank guarantees), a long node with broad vocabulary, first when it is not the answer: on 44 of the 302 test items.
- **It finds the right section less often** (0.66 against 0.73), and more candidates do not help (0.66 at 10, against 0.82 for flat). With 3 seeds and one hop the candidate set is fixed. When the seeds miss the section, nothing brings it back. This is the cost of the setting chosen on dev, where section recall was level with flat (0.75 against 0.78).
- **It finds 91% of the lease clauses** the gold path needs. Flat retrieval finds none, by design.
- **Dev overstated it on time limits.** Exact provision recall@5 on time-limit items was 0.90 on dev and is 0.60 on test.

### 4.6 Where graph retrieval goes wrong (test)

- **It misses the gold section for 103 of the 302 items:** 40 restraint-of-trade items, 40 time limits and 23 bars on proceedings. Flat retrieval's top 5 has the section for 21 of them; 82 are missed by both.
- **Restraint of trade:** 21 of its 40 misses retrieved s.28 instead of s.27.
- **The other misses scatter** across sections that share the clause's words but not its subject. The most frequent are s.74 (penalty for breach, in 22 of the 103) and s.30 (wagers, 18).
- **Rulings come only with their provisions.** A ruling can be chosen only if a provision it interprets is in the top 5. A ruling of the item's own kind is in the evidence for:

  | | Restraint of trade | Bar on proceedings | Time limits |
  |---|---|---|---|
  | Test | 47/100 | 70/102 | 55/100 |
  | Dev | 6/20 | 17/20 | 18/20 |

  For a bar on proceedings, "own kind" means a jurisdiction ruling, or an arbitration ruling when the gold provision is Exception 1. Overall, 237 of the 340 test items get at least one ruling.
- **Graph evidence is the longest.** The median prompt is 4,600 characters with the clause alone, 7,300 with flat retrieval and 8,200 with graph retrieval.

### 4.7 From retrieval to verdicts

Better retrieval did not by itself give better verdicts (section 7.6).
- **In the plain pipeline,** B1-graph's defect F1 is level with B1-flat's: 0.807 against 0.812, interval −0.039 to +0.027. Its false alarms are higher, 0.17 against 0.12.
- **In the agent,** the evidence did better: the fixed-policy agent without the adapter is 0.030 above flat, and 0.035 above B1-graph, an interval that excludes zero.

The two give the model different text: the rulings, the arbitration and term clauses, and 3 seeds against 5 (section 4.4). We have not isolated which of these accounts for the difference. H2's retrieval claim holds for the exact provision and for the lease clauses, but not for the section.

### 4.8 Changes made after the first test runs

Two changes reached graph retrieval's input after other configurations had been scored on the test set. Neither was made in response to a score. B1-graph was scored once, after both.

1. **Lease clauses cut to 1,500 characters** (`b7ee5e7`). The first B1-graph run ran out of GPU memory in L07. That deed states its term in a 19,082-character preamble, which the term-clause rule passed whole, giving prompts of 27,000–29,000 characters. The cut is the one the agent already made before verify (section 5.1). The evidence path is unchanged, so the retrieval figures above stand. The 86 predictions made before the crash were never scored.
2. **The lawyer's corrections to three holdings** (`6a229d1`). They arrived while the second B1-graph run was going; that run was cancelled and never scored. Only the choice of rulings changed. The provisions and lease clauses are the same on every dev and test item, and the dev count of items given a ruling of their own kind went from 42 to 41.

No other configuration is affected: flat retrieval and the agent never read rulings, and the agent already cut lease clauses.

---

## 5. The agent

The agent decides one clause at a time. It gathers evidence with four tools and then hands that evidence to the verifier (section 6), which gives the verdict, the provision and a confidence. The code is `src/agent/tools.py` and `src/agent/controller.py`.

### 5.1 Tools

| Tool | What it returns |
|---|---|
| `get_clause(clause_id)` | Another clause of the same lease, by id or by the deed's own number, with the clauses it links to |
| `lookup_definition(term)` | The lease's definition of a defined term. If the parser listed no definition, it looks for the clause that defines the term in running text ("hereinafter referred to as the 'Exit Date'") |
| `search_graph(query)` | Contract Act provisions by BM25, each section followed by its exceptions and explanations |
| `expand(node_id)` | One hop from a statute node (its exceptions, explanations, the section it belongs to) or from a lease clause (the clauses it links to) |

Every call is logged. Everything a call returns is kept as evidence. The controller sees each result cut to 600 characters; the verifier gets the full statute text and each lease clause cut to 1,500 characters. The evidence path lists statute nodes first, in the order found, then lease clauses.

### 5.2 Two policies

- **Fixed.** No model chooses anything. The agent reads every clause and definition the target clause links to, runs one statute search on the clause text, and calls the verifier. This is the tool set in a fixed order.
- **Controller.** The model picks one tool call per step, as a JSON action, until it calls `verify` or has used 6 steps. Three prompt variants were compared: **direct** (the action only), **think** (one or two sentences, then the action) and **plan** (a short plan on the first step, kept in view afterwards).

Running out of steps is not a hand-off by itself: the verifier still decides on what was gathered, and the log records that the budget was spent. A clause is handed off when the verifier says so.

The controller chooses tools with the **base** model and the verifier answers with the **adapter**. The adapter was trained to give verdicts, not to choose tools, so it is switched off for the controller's calls. Both use the same loaded weights, so the GPU holds one copy.

### 5.3 What the dev runs showed (dev, base model, no adapter)

| Variant | Accuracy | Defect recall | Defect F1 | False alarms | Cross-clause accuracy | Exact provision recall@5 | Clauses that used all 6 steps | Mean steps |
|---|---|---|---|---|---|---|---|---|
| Fixed | 0.72 | 0.77 | 0.82 | 0.09 | 0.58 | 0.75 | – | 1.5 |
| Controller, direct | **0.75** | **0.92** | **0.91** | 0.09 | **0.63** | 0.10 | 4 of 61 | 3.8 |
| Controller, think | 0.69 | 0.81 | 0.84 | 0.09 | 0.47 | 0.08 | 54 of 61 | 5.8 |
| Controller, plan | 0.69 | 0.81 | 0.82 | 0.11 | 0.47 | 0.00 | 53 of 61 | 5.7 |

Three things came out of these runs.

1. **Asking the 7B model to reason before acting made it loop.** With think and plan it repeated `lookup_definition` (229 and 289 calls over 61 clauses) and used the whole budget on 54 and 53 clauses. With direct it stopped by itself on 57 of 61.
2. **Left to itself, the model reads the lease and rarely searches the statute.** The direct variant made 46 statute searches over 61 clauses, and the gold provision was in its first five nodes for only 10% of items. Its verdicts were still the best. For this model the lease's own context (the definition of "Restricted Period", the clause a restraint refers to) is what changes the answer.
3. **Forcing the statute search made it worse.** We then started every controller run with a statute search on the clause text and stopped runs that repeated a call twice. The loops went (0 or 1 clause out of budget), and exact provision recall@5 rose to 0.75, but the direct variant's F1 fell from 0.91 to 0.82. Item by item, 8 verdicts changed and 6 of those were right before; 4 void clauses became "valid", among them DA-06 and DV-12, the two restraints whose reach depends on a term defined in another clause. With the search done for it, the model called `verify` at once (0.1 steps on average) and never read the lease.

| Controller with the opening statute search | Accuracy | Defect F1 | False alarms | Cross-clause accuracy |
|---|---|---|---|---|
| direct | 0.69 | 0.82 | 0.09 | 0.47 |
| think | 0.74 | 0.83 | 0.06 | 0.63 |
| plan | 0.70 | 0.82 | 0.09 | 0.53 |

**Configuration taken to the test set (chosen on dev only):** the controller with the direct prompt and no opening search, with the 2,000-pair adapter as the verifier. This choice has a cost: the evidence path of this configuration seldom contains the statute text, so it is less "statute-grounded" than the fixed policy. The fixed policy with the adapter is reported next to it for that reason.

---

## 6. Fine-tuning the verifier

### 6.1 Training pairs

The pairs are synthetic. Qwen2.5-7B-Instruct was asked for 2,400 clauses, each with a requested defect type, phrasing family, verdict and form (a third cross-clause, with the definition it depends on). Each reply was checked by rules: it must parse, follow the schema, name an allowed provision, and its stated elements must give the requested verdict under the lawyer's element checklist. **2,121 of 2,400 were kept (88%).** The main reasons for rejection were elements that disagreed with the rules (199), schema errors (65), a wrong verdict (53) and unparseable replies (53).

Three phrasing families (RT-5, BP-3, TL-4) were never generated, so the test set contains wording the verifier was not trained on. The generation config was committed before any test item was written. No test or dev clause is in the training pairs.

### 6.2 Training

| Setting | Value |
|---|---|
| Base model | Qwen2.5-7B-Instruct, 4-bit NF4 with double quantisation, fp16 |
| Adapter | LoRA rank 16, alpha 32, dropout 0.05, all linear layers |
| Optimisation | 2 epochs, learning rate 2e-4, cosine schedule, 3% warm-up, batch 1 with 8 accumulation steps |
| Input | chat-formatted element-check prompt, loss on the answer only, at most 1,024 tokens |
| Hardware | Kaggle, 2 × T4; peak memory 11.9 GB across both |

### 6.3 Learning curve (dev, fixed-policy agent, one seed)

Each adapter is trained on the first N kept pairs, so the sets are nested.

| Training pairs | Accuracy | Defect recall | Defect F1 | False alarms | Citation correct | Cross-clause accuracy | Training time |
|---|---|---|---|---|---|---|---|
| 0 (base model) | 0.72 | 0.77 | 0.82 | 0.09 | 0.70 | 0.58 | – |
| 250 | 0.72 | 0.69 | 0.78 | 0.06 | 0.90 | 0.58 | 32 min |
| 500 | 0.70 | 0.81 | 0.84 | 0.09 | 0.87 | 0.58 | 65 min |
| 1,000 | 0.75 | 0.77 | 0.82 | 0.09 | 0.85 | 0.74 | 2.2 h |
| **2,000** | **0.79** | **0.85** | **0.86** | 0.09 | 0.78 | **0.74** | 4.3 h |

- **H4 is not supported on dev.** Accuracy goes 0.72, 0.70, 0.75, 0.79: it is still rising at 2,000 pairs, and the two largest steps are the last two. We had 2,121 pairs, so we cannot say where it levels off.
- **Where the gain is.** Against the base model, the 2,000-pair adapter raises accuracy on restraint of trade from 0.55 to 0.75 and on cross-clause items from 0.58 to 0.74, and removes the false alarms on restraint of trade (0.08 to 0.00). Bar on proceedings and time limits stay at 0.80.
- **Citations improve early, then slip.** Citation accuracy jumps from 0.70 to 0.90 with 250 pairs and is 0.78 at 2,000.
- **Caveats.** One seed per size, and 61 dev items: one item is 0.016 of accuracy, so the differences between neighbouring sizes are two or three items. The trend over four sizes is the evidence, not any single step.

The 2,000-pair adapter is the verifier in every "adapter" configuration on the test set. **The dev gain did not carry over to the test set** (section 7.6): there the adapter leaves accuracy unchanged and lowers F1, because it hands off far more clauses.

---

## 7. Results

### 7.1 Configurations

Every configuration is one call of `src/eval/run.py` through `src/eval/run_all.py`, with greedy decoding, the same element-check prompt and five few-shot examples (the lawyer's illustrations).

| Name | Model | What it sees |
|---|---|---|
| B1-none | Qwen2.5-7B-Instruct, 4-bit | the clause alone |
| B1-flat | same | the clause and the top 5 provisions by BM25 |
| B1-graph | same | the clause, graph retrieval over the statute and the lease's links |
| agent-fixed-noadapter | same | fixed-policy agent (section 5.2) |
| agent-fixed | same, with the 2,000-pair adapter | fixed-policy agent |
| **agent-controller** (full system) | same, with the adapter as verifier | controller, direct, no opening search |
| B2-none | Claude Opus 5.5 through Claude Code print mode, tools off | the clause alone |
| B2-flat | same | the clause and the top 5 provisions by BM25 |

### 7.2 Metrics

A **defect** is a clause whose gold verdict is void. Defect recall, precision and F1 are over void against not-void. The **false-alarm rate** is the share of valid and hand-off clauses called void. **Citation correct** is the share of items with a gold provision where the cited provision matches it exactly. **Exact provision recall@5** is the share where the gold provision is among the first five nodes of the evidence path; it is blank where nothing is retrieved. A missing prediction counts as wrong.

### 7.3 Test set (`test-v1`, 340 items)

| Run | Accuracy | Defect recall | Defect precision | **Defect F1** | False alarms | Citation correct | Exact provision recall@5 | Cross-clause accuracy |
|---|---|---|---|---|---|---|---|---|
| B1-none | 0.74 | 0.85 | 0.82 | **0.84** | 0.15 | 0.72 | – | 0.72 |
| B1-flat | 0.71 | 0.79 | 0.84 | **0.81** | 0.12 | 0.68 | 0.22 | 0.66 |
| B1-graph | 0.70 | 0.81 | 0.80 | **0.81** | 0.17 | 0.70 | 0.66 | 0.69 |
| agent-fixed-noadapter | 0.71 | 0.81 | 0.87 | **0.84** | 0.10 | 0.66 | 0.65 | 0.72 |
| agent-fixed | 0.70 | 0.77 | 0.85 | **0.81** | 0.11 | 0.75 | 0.65 | 0.73 |
| **agent-controller** (full system) | 0.70 | 0.81 | 0.81 | **0.81** | 0.16 | 0.76 | 0.13 | 0.69 |
| B2-none | 0.81 | 0.84 | 0.93 | **0.88** | 0.05 | 0.95 | – | 0.69 |
| B2-flat | 0.80 | 0.83 | 0.93 | **0.88** | 0.05 | 0.95 | 0.22 | 0.70 |

By defect type and form, defect F1 (accuracy in brackets):

| Run | Restraint of trade (100) | Bar on proceedings (102) | Time limit (100) | Single clause (241) | Cross-clause (99) |
|---|---|---|---|---|---|
| B1-none | 0.83 (0.68) | 0.87 (0.78) | 0.87 (0.78) | 0.84 (0.75) | 0.83 (0.72) |
| B1-flat | 0.84 (0.65) | 0.83 (0.76) | 0.81 (0.72) | 0.83 (0.73) | 0.79 (0.66) |
| B1-graph | 0.84 (0.67) | 0.85 (0.77) | 0.78 (0.69) | 0.81 (0.71) | 0.79 (0.69) |
| agent-fixed-noadapter | 0.85 (0.66) | 0.88 (0.78) | 0.83 (0.72) | 0.83 (0.71) | 0.86 (0.72) |
| agent-fixed | 0.80 (0.67) | 0.82 (0.69) | 0.82 (0.67) | 0.80 (0.69) | 0.83 (0.73) |
| agent-controller | 0.83 (0.70) | 0.82 (0.70) | 0.80 (0.64) | 0.81 (0.71) | 0.80 (0.69) |
| B2-none | 0.79 (0.73) | 0.89 (0.75) | 0.95 (0.90) | 0.94 (0.85) | 0.79 (0.69) |
| B2-flat | 0.79 (0.72) | 0.89 (0.75) | 0.94 (0.89) | 0.93 (0.85) | 0.79 (0.70) |

Share of items answered correctly, by gold verdict:

| Run | Void (154) | Valid (113) | Hand-off (73) | Out-of-scope items (38) |
|---|---|---|---|---|
| B1-none | 0.85 | 0.83 | 0.36 | 0.66 |
| B1-graph | 0.81 | 0.78 | 0.34 | 0.61 |
| agent-fixed-noadapter | 0.81 | 0.81 | 0.37 | 0.66 |
| agent-fixed | 0.77 | 0.50 | 0.85 | 0.89 |
| agent-controller | 0.81 | 0.48 | 0.82 | 0.87 |
| B2-none | 0.84 | 0.74 | 0.84 | 0.92 |

### 7.4 What the baselines show

- **The gap between the small model and the frontier model is 0.047 F1 with nothing added** (0.837 against 0.884; paired bootstrap 95% interval of the difference −0.095 to −0.000). On dev it was 0.08.
- **The frontier model's advantage is precision, not recall.** Recall is the same (0.84 and 0.85). B2 raises 9 false alarms where B1 raises 28, and cites the right provision on 95% of items against 72%.
- **The frontier model is cautious.** It hands off 111 clauses where the key has 73, including 25 void clauses. That is where its misses are: on restraint of trade its recall is 0.68 against B1's 0.86.
- **Cross-clause items are where the frontier model loses its lead.** Its F1 drops from 0.94 on single clauses to 0.79 on cross-clause items, below B1's 0.83.
- **H1, flat retrieval.** Adding the top 5 provisions lowers the small model's false alarms (0.15 to 0.12) and lowers its recall more (0.85 to 0.79), so F1 falls from 0.84 to 0.81. It changes nothing for the frontier model. This repeats the dev result and the agent result in section 5.3: with statute text in the prompt, the small model calls more clauses valid. Flat retrieval puts the exact gold provision in the top 5 for only 22% of test items, so much of what it adds is the wrong text.

### 7.5 H3

Agreed and recorded before any test run (PLAN.md section 14): H3 holds if the full system's defect F1 is at least B2-none's minus 0.05, on the point estimates over all 340 items. B2-none's F1 is 0.8836, so the bar is **0.8336**.

| | Defect F1 |
|---|---|
| B2-none | 0.8836 |
| agent-controller (full system) | 0.8078 |
| Difference | **−0.076** (95% paired-bootstrap interval −0.127 to −0.025, 10,000 resamples) |

**H3 is not supported.** The full system is 0.076 below the frontier baseline, outside the 0.05 margin, and the whole interval is below zero. The fixed-policy agent with the adapter gives the same picture (0.8095, difference −0.074, interval −0.124 to −0.026).

The rule was fixed for the configuration chosen on dev, so that is the verdict. For the record, two configurations that were *not* the chosen one are inside the margin: the untuned model alone (B1-none, 0.837, difference −0.047) and the fixed-policy agent without the adapter (0.842, difference −0.042). We report them as observations, not as a pass: choosing either of them now would be choosing on the test set.

### 7.6 Ablations

Differences in defect F1 on the test set, with 95% paired-bootstrap intervals (`src/eval/compare.py`):

| Ablation | Compared | Difference in F1 | 95% interval |
|---|---|---|---|
| The adapter | agent-fixed against agent-fixed-noadapter | −0.032 | −0.076 to +0.012 |
| The controller | agent-controller against agent-fixed | −0.002 | −0.040 to +0.037 |
| Graph search and lease links against flat retrieval | agent-fixed-noadapter against B1-flat | +0.030 | −0.001 to +0.062 |
| The whole system against the bare model | agent-controller against B1-none | −0.029 | −0.083 to +0.025 |
| Graph against flat retrieval in the plain pipeline | B1-graph against B1-flat | −0.006 | −0.039 to +0.027 |
| The agent's evidence against graph retrieval in the plain pipeline | agent-fixed-noadapter against B1-graph | +0.035 | +0.007 to +0.065 |

**The adapter did not help on the test set, and the reason is visible in the verdicts.** With the adapter the agent hands off 132 clauses; without it, 42. The adapter is right about hand-offs (85% of the gold hand-off items, against 37%) and about out-of-scope clauses (0.89 against 0.66), which the base model mostly decides when it should not. The price is that it also hands off 42 of the 113 valid clauses and 28 of the 154 void ones, so accuracy on valid clauses falls from 0.81 to 0.50 and defect recall from 0.81 to 0.77. On time limits it also raises more false alarms (0.13 to 0.28). On restraint of trade it does what it did on dev: precision 1.00 and no false alarms, with lower recall (0.66). Overall accuracy is unchanged (0.71 and 0.70) because the gains on hand-off items and the losses on valid items cancel.

The same shift was there on dev, and we read it as a gain. On dev the adapter raised hand-offs from 4 to 20 of 61 clauses, got all 11 hand-off items right (from 3), and dropped accuracy on valid clauses from 0.88 to 0.62; accuracy rose from 0.72 to 0.79 because defect recall also rose (0.77 to 0.85). On the test set recall fell instead (0.81 to 0.77), so nothing paid for the lost valid clauses. Dev has 1 out-of-scope item and the test set 38, so dev could not show how much of the adapter's value is in refusing clauses outside ss.27–28. The adapter is better at knowing what it should not decide and worse at deciding. Citations are the one clear gain that carried over: 0.66 to 0.75.

**The controller did not help either.** With the adapter as verifier, letting the model choose its tools gives the same F1 as the fixed order (0.808 and 0.810), with more false alarms (0.16 against 0.11) and a much lower exact provision recall@5 (0.13 against 0.65), because it reads the lease and seldom searches the statute. It used 3.5 steps per clause and ran out of budget once in 340. Its dev lead (F1 0.91) was measured with the base model as verifier and did not carry over.

**H2: graph retrieval finds the right provision far more often, and that alone does not improve the verdicts.** Both graph-based configurations put the exact gold provision in the first five nodes for about 65% of items, where flat retrieval does for 22%. End to end the two differ:

- **In the plain pipeline (B1-graph) the F1 is the same as flat** (0.807 against 0.812), on cross-clause items too (0.79 and 0.79), and false alarms are higher (0.17 against 0.12; 0.33 on cross-clause items). Better retrieval did not turn into better verdicts.
- **In the fixed-policy agent without the adapter it is 0.030 higher than flat** (0.842 against 0.812; the interval just includes zero), and the gain is largest on cross-clause items (0.86 against 0.79), as H2 predicted. It also undoes the harm flat retrieval did to the bare model (0.837 to 0.812) while keeping a lower false-alarm rate (0.10 against B1-none's 0.15). It is 0.035 above B1-graph, and that interval excludes zero.

The two give the model different evidence. The agent passes the sections with their exceptions and the clauses and definitions the target clause links to. Graph retrieval in the pipeline adds up to three court rulings and, by rule, the deed's arbitration and term clauses. We have not isolated which of these accounts for the difference; it fits the pattern in every other result here, that more legal text in the prompt makes the 7B model less accurate, but that is an explanation after the fact and not a tested one.

**Cross-clause items.** Every small-model configuration is level with or above the frontier model here (0.80 to 0.86 against 0.79), and the fixed-policy agent without the adapter is 0.07 above it. On single clauses the frontier model is far ahead (0.94 against 0.80 to 0.84). The frontier model's lead is in reading one clause precisely; where the answer depends on another clause, reading that clause is what counts, and a small model given the clause does as well.

---

## 8. Error analysis and limitations

### 8.1 Limitations

- **One run per configuration.** Decoding is greedy, so a repeat gives the same answers for the open model; the frontier baseline has no seed and was run once. Training used one seed per size.
- **The dev set is small** (61 items). The controller variant and the adapter size were chosen on it, and several of those choices rest on differences of two to four items. Both choices turned out wrong on the test set (section 7.6). We did not change the system after seeing test results.
- **The controller variant was chosen with the base model as verifier** and then run with the adapter. The combination was not measured on dev.
- **The learning curve is on dev only.** Only the 2,000-pair adapter was run on the test set.
- **Synthetic training pairs** come from the same 7B model that is then tuned, checked by rules and not by a lawyer.
- **B2 ran in parts.** Both B2 runs stopped at a usage limit and were resumed; B2-none's two parts ran at two commits that differ only in files it does not use (the note is kept with the run).
- **The test deeds are public SEC exhibits**, so a frontier model may have seen them in training. The planted clauses are new.

### 8.2 Hard cases and legal commentary

*Saksham's section: ten worked hard cases and the retrieval error analysis.*

---

## 9. Compute

Everything ran on free Kaggle sessions (2 × T4) and one laptop; no paid compute.

| Stage | GPU-hours (wall time × 2 GPUs) |
|---|---|
| Training-pair generation, 2,400 requests | *to add from the session-1 log* |
| QLoRA at 250, 500, 1,000 and 2,000 pairs | 16.1 (8.1 h wall) |
| Dev runs of the agent (11 runs) | 11.5 |
| Test runs, B1-none and B1-flat | 3.2 |
| Test runs, agent (3 runs, 4.5 h wall) | 9.1 |
| Test run, B1-graph | 1.8 |
| B2 (frontier, laptop, no GPU) | 0 |

Peak GPU memory was 11.9 GB in training and 9.5 to 13 GB for the agent runs on dev, spread over the two T4s. Each run folder has its `config.json` with the git commit, seed, platform, GPU type and GPU hours.

## 10. Reproducing the numbers

```
pip install -r requirements.txt
python -m src.train.gen_pairs --n 2400 --out runs/gen-full                           # training pairs
python -m src.train.qlora --model Qwen/Qwen2.5-7B-Instruct --data runs/gen-full/kept.jsonl \
    --out runs/qlora-2000 --limit 2000                                                # the verifier
python -m src.eval.run_all --items data/test/items.jsonl --adapter runs/qlora-2000/adapter --out runs/test
python -m src.eval.run_all --items data/test/items.jsonl --where laptop \
    --frontier-model <model id> --frontier-backend <backend> --out runs/test           # B2
python -m src.eval.run_all --table runs/test                                          # section 7.3
python -m src.eval.compare --system runs/test/agent-controller-test --baseline runs/test/B2-none-test   # section 7.5
```

`kaggle/run.ipynb` is the notebook every Kaggle run used; only its command cell changes.
