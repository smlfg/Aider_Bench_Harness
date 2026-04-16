# Plan: Karpathy Prompt Line-by-Line Iteration

## Goal

While Samuel walks, run incremental CONVENTIONS.md mutations using Aider on SWE-bench Lite tasks.
Each mutation adds **one logical block** from `KarparthysClaude.md` to the baseline `CONVENTIONS.md`.
After every run: capture judge result + Hermes' own opinion → document.
Samuel reviews the document when he returns.

---

## Context / Assumptions

### Current state
- **Project:** `~/Projekte/FirstRealHarnessEvaluation_KarpathiesMD/`
- **Baseline CONVENTIONS.md** (6 rules, 13 lines, 389 bytes):
  ```md
  # CONVENTIONS.md
  ## Goal
  Solve the requested bug with the smallest correct change.
  ## Rules
  1. State the bug hypothesis before editing.
  2. Reproduce or inspect the failing behavior first.
  3. Prefer the smallest fix that makes tests pass.
  4. Do not refactor unrelated code.
  5. Run the relevant tests before finalizing.
  6. In the final message, state what changed and which tests passed.
  ```
- **KarparthysClaude.md** (4 sections, 65 lines):
  - §1 "Think Before Coding" (header + 5 bullet points)
  - §2 "Simplicity First" (header + 4 bullet points + Ask yourself paragraph)
  - §3 "Surgical Changes" (header + 6 bullet points + The test paragraph)
  - §4 "Goal-Driven Execution" (header + 4 bullet points + code block + paragraph)

### Baseline results (sympy__sympy-20590, 4 runs)
| Run | task_success | tests_passed/total | failure_kind |
|-----|:---:|---|---|
| run01 | false | 21/22 | task_failure |
| run02 | false | 21/22 | task_failure |
| run03 | false | 21/22 | task_failure |
| run04 | false | 21/22 | task_failure |

All 4 runs: FAIL_TO_PASS (`test_immutable`) not resolved. The diff was only a `.gitignore` change — **Aider never touched the actual bug**.
This is the baseline problem: Aider is not producing a real fix.

### Task
- **Instance:** `sympy__sympy-20590`
- **Problem:** Symbol objects have `__dict__` since v1.7 (shouldn't, due to `__slots__`)
- **Metric:** `test_immutable` in `FAIL_TO_PASS` must pass
- **Judge rubric:** scope_adherence, minimality, diff_clarity → judge_score (1-5)

### API Budget
- ~800 prompts remaining on MiniMax account
- Each Aider run: ~1 API call (agent) + 2 judge calls (stage1 + stage2)
- Estimated: ~3 prompts per run
- Buffer: ~250 runs possible

---

## Proposed Approach

### Mutation Strategy

Create **5 candidate CONVENTIONS files**, each adding exactly ONE block from KarparthysClaude.md:

| Mutation | Added Block | New Lines | Total Lines |
|----------|-------------|:---------:|:-----------:|
| candidate_01 | §1 "Think Before Coding" header + Tradeoff line | +2 | 15 |
| candidate_02 | §1 bullets (5 items) | +9 | 24 |
| candidate_03 | §2 "Simplicity First" header | +1 | 25 |
| candidate_04 | §2 bullets (4 items) + Ask yourself | +5 | 30 |
| candidate_05 | §3 "Surgical Changes" header | +1 | 31 |
| candidate_06 | §3 bullets (6 items) | +10 | 41 |
| candidate_07 | §3 The test paragraph | +1 | 42 |
| candidate_08 | §4 "Goal-Driven Execution" header | +1 | 43 |
| candidate_09 | §4 bullets (4 items) | +4 | 47 |
| candidate_10 | §4 code block | +7 | 54 |
| candidate_11 | §4 last paragraph | +1 | 55 |

**Conservative pacing: 3 runs per candidate** (not 5, to conserve API budget).
This gives us a signal with ~33 runs total instead of 55.

### Run Command Template

```bash
cd ~/Projekte/FirstRealHarnessEvaluation_KarpathiesMD
uv run harness-run-once \
  --task-id sympy__sympy-20590 \
  --task-file data/selected_tasks_e2e.json \
  --condition candidate_vXX \
  --iteration 1 \
  --run-index N \
  --conventions-path harness/CONVENTIONS.candidate_vXX.md
```

Wait for completion, then read `results/candidate_vXX/sympy__sympy-20590/.../run_meta.json`
and `judge_result.json`.

### After Each Run

1. Read `run_meta.json` → tests_passed, task_success, failure_kind
2. Read `judge_result.json` → judge_score, scope_adherence, minimality, diff_clarity
3. Read `git_diff.patch` → what actually changed
4. **Form Hermes' own opinion:**
   - Did the added block change Aider's behavior?
   - Was the diff relevant to the bug?
   - Did the instruction help or hurt?
5. Append to `results/summary/spaziergang_2026-04-16.md`

---

## Step-by-Step Plan

### Phase 0: Setup (NOW — before Samuel leaves)
- [ ] Create `harness/CONVENTIONS.candidate_v01.md` (baseline + §1 header)
- [ ] Create all subsequent candidate files (v02–v11)
- [ ] Verify baseline still works: run candidate_v01 once as smoke test
- [ ] Create `results/summary/spaziergang_2026-04-16.md` with experiment log header

### Phase 1: Sequential Runs
For each candidate v01 → v11:
- [ ] Run 3 times (run_index 1, 2, 3)
- [ ] After each run: capture metrics + Hermes opinion → document
- [ ] Log: mutation, added_block, run_index, task_success, tests_passed/total, judge_score, Hermes_opinion
- [ ] If infrastructure error: log and retry once

### Phase 2: Summary
After all runs (or when API budget is ~50 prompts remaining):
- [ ] Aggregate: mean task_success per candidate, mean judge_score per candidate
- [ ] Identify: which block was the first to produce measurable change
- [ ] Write final verdict section in document

---

## Files That Will Change

```
harness/CONVENTIONS.candidate_v01.md  (new)
harness/CONVENTIONS.candidate_v02.md  (new)
...
harness/CONVENTIONS.candidate_v11.md  (new)
results/candidate_v01/sympy__sympy-20590/baseline_sympy__sympy-20590_run01/run_meta.json  (new dirs + files)
results/candidate_v01/sympy__sympy-20590/baseline_sympy__sympy-20590_run02/run_meta.json
results/candidate_v01/sympy__sympy-20590/baseline_sympy__sympy-20590_run03/run_meta.json
... (33 run_meta.json + judge_input.json + judge_result.json + git_diff.patch + agent_stdout.log)
results/summary/spaziergang_2026-04-16.md  (new, continuously appended)
```

---

## Risks / Tradeoffs / Open Questions

1. **Aider not fixing the bug at all (baseline problem):** All 4 baseline runs failed on the actual bug. If every candidate also fails, we can't measure improvement — only judge_score might shift. This is still useful signal.

2. **Judge cost:** 2 calls per run × 33 runs = 66 judge calls. At MiniMax pricing this should be fine but worth monitoring.

3. **Only one task:** `sympy__sympy-20590` only. Generalization to other tasks is unknown. The experiment design originally called for 3 tasks, but for Samuel's walk-duration, one task is more practical.

4. **Aider may need `--yes-always` flag:** Check config — `aider-config.example.yml` and `.env` to ensure non-interactive mode.

5. **Samuel said "OpenCode" but experiment uses "Aider":** The `run_once.py` harness calls Aider directly via `subprocess`. OpenCode is not involved in the actual experiment harness. The "Aider versuchen" likely means "let the harness runs try to execute."

6. **API budget:** 800 prompts / 3 per run ≈ 266 runs. We plan 33. Plenty of buffer.

---

## Verification Steps

After Samuel returns, we review `results/summary/spaziergang_2026-04-16.md` together.
Expected deliverable:
- Table: mutation → mean task_success → mean judge_score → Hermes' opinion
- One-sentence verdict: "Block X (§Y) was the first to produce measurable change" or "No block produced measurable change on this task"
