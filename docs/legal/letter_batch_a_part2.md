**Subject:** Batch A, part 2: 21 more practice clauses, and which files to open

Dear [lawyer's name],

Thank you again for Session 1 and for the pilot, Batch A and Batch B answers. Your answers matched ours on almost every item. Where they did not, your answer is the one we use.

I am now the team's contact for the legal review, taking over from Avnish. I have copied our project folder, `lma-final-project`, onto your laptop so that everything you need is in one place and you can work offline. This letter says what we are asking for and exactly which files to open.

## 1. What we are asking for now: 21 clauses, back by Monday 2 November

Batch A was meant to be 60 practice clauses. You have answered the first 20 (DV-01 to DV-20). A teammate wrote 21 more, **DA-01 to DA-21**, and they were not ready in time to go with the first part. They are written into the same three lease deeds you have already seen (S01, S02 and S03).

The task is the same as before. For each clause, please give:

| Column | What to write |
|---|---|
| `answer` | **void**, **valid** or **refer** ("refer" if it cannot be decided from the text alone, or it is outside ss.27–28) |
| `section_or_exception` | The provision that decides it, e.g. s.27, s.27 Exception 1, s.28(a), s.28(b), s.28 Exception 1 |
| `reason` | Optional, one or two lines. If only part of a clause is void, please say which words, as you suggested in Session 1 |

Some of the clauses are void and some only look similar but are valid. We do not say which. Some depend on a definition or another clause elsewhere in the same deed, so please read the clause in the context of the whole deed.

It should take about 45 minutes.

## 2. Which files to open

Everything is inside the `lma-final-project` folder on your laptop. You do not need to install anything or connect to the internet. All the paths below start from that folder.

**Please open only these:**

| File | What it is |
|---|---|
| `data/dev/answer_sheet_blank.csv` | **Your answer sheet.** One row per clause (DA-01 to DA-21), giving the deed and the clause number. The last three columns are blank for you to fill in. It opens in Excel. |
| `data/dev/planted/S01.txt` | Lease deed S01 (Bangalore, 2006), with the clauses written in: DA-01 to DA-07 |
| `data/dev/planted/S02.txt` | Lease deed S02 (Hyderabad, 2003), DA-08 to DA-14. Clause numbers such as "GTC-12B" are in Exhibit A (General Terms and Conditions). |
| `data/dev/planted/S03.txt` | Lease template S03 (2026), DA-15 to DA-21 |
| `docs/legal/session1_review.md` | Your own Session 1 notes, in case they are useful for reference |

The deeds are plain text files. Open them in Notepad (or any text editor) and use Ctrl+F to find a clause by its number, e.g. "13A" or "GTC-42C".

**Please do not open these, so that your answers stay blind:**

- any file named `answer_key.jsonl` (in `data/dev/`, `data/pilot/` and `data/pool/`): our own answers
- the `README.md` files inside `data/`, which summarise our answers
- the folders `plans_and_docs/`, `src/`, `tests/` and `kaggle/`, and the hidden `.git` folder, which describe our rules and sometimes mention answers

If you open one of these by mistake, it is not a problem. Just tell us which items you saw our answer for, and we will note it.

## 3. How to send your answers back

Open `data/dev/answer_sheet_blank.csv` in Excel, fill in the three columns, and save it under a new name, `batch_a2_answers.csv`, keeping the CSV format (if Excel asks, choose "Keep current format"). Then email that file to me at sakshamgoyal.sgm27@gmail.com. Please do not change any other file in the folder. We will add your sheet as `docs/legal/batch_a2_answers.csv`, like your earlier sheets.

If a clause is badly drafted or ambiguous in a way we did not intend, please say so in the reason column. That is as useful to us as the answer.

## 4. What comes after this

**Session 2, Thursday 5 November, about 1 hour.** As planned in the original brief, we will go through:

1. **The clauses where your answer and ours differ.** From Batch B so far: PO-14, PO-24, PO-65 and PO-66 on the verdict, and PO-42 and DV-03 on which provision to cite. We will send the list, including any differences from these 21 clauses, by Tuesday 3 November.
2. **Our one-line summaries of the judgments you suggested.** Please mark any that are wrong.

**Test clauses.** The clauses our final results are scored on will reach you in batches of about 50 from this weekend, in the same format (a blank answer sheet plus the deeds). Our test set is frozen on Friday 6 November, so anything after that date cannot be used. If time is short, the hardest items come first: clauses that depend on another clause, and the look-alikes.

If the full amount is too much, please tell us. Even a sample of the test clauses lets us report how far our own labels can be trusted.

## 5. Credit

As before, with your permission we will thank you by name in our report. If you prefer, we will only say "a legally trained reviewer".

If anything in the folder is unclear, please email or call me.

Kind regards,

Saksham
Team ClosedAI, LMA course project, IIIT Hyderabad
sakshamgoyal.sgm27@gmail.com
