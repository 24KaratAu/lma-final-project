# Project instructions

Team ClosedAI, LMA Group Project 2026: statute-grounded enforceability checking for Indian commercial leases. The plan, owners and schedule are in `plans_and_docs/PLAN.md`; read the relevant sections before changing code.

## Merging into `main`

Anyone may merge their own pull request, but only after every step below passes. If any step fails, stop, fix it, and start the list again. Never merge "to fix it later".

1. **Work on a branch**, never on `main`: `data/`, `graph/`, `model/`, `agent/` or `eval/` plus a short topic, e.g. `graph/lease-parser`.
2. **Bring in the latest `main`** before opening or merging the PR: `git fetch origin && git rebase origin/main`.
3. **Run the tests locally** and make sure they all pass: `pip install -r requirements-dev.txt && pytest -q`. Add or update tests for any new code.
4. **Check the diff** with `git diff origin/main...HEAD`:
   - Only your own folders changed (README.md, "Layout"), unless the change was agreed with their owner.
   - `src/common/schemas.py` changed only if all four team members agreed (PLAN.md section 10).
   - No model weights, API keys, tokens, raw lease PDFs or run outputs.
   - Nothing under `data/test/` changed after the test set is frozen (PLAN.md section 11).
5. **Push and open a PR** that says in plain words what changed and why.
6. **Run the tests again after the final rebase.** There is no CI on GitHub, so this local run is the only check before merging.
7. **Merge with squash**: `gh pr merge <number> --squash --delete-branch`.
8. After merging, tell the team in one line what landed.

## Commits and pull requests

- Write commit messages and PR descriptions as the team member who made the change.
- Do not add any AI attribution: no `Co-Authored-By` trailers for tools, no "Generated with" footers.

## Results rules (PLAN.md section 11)

- Tune prompts, retrieval and the agent on the dev set only.
- The mocks in `src/common/mocks.py` answer from gold labels: use them on fixtures and dev only, never for reported numbers.
- Every run is logged with its config, git commit, seed, platform, GPU type and GPU hours in `runs/<run_id>/`.
