# Plan: Switch to Small Astropy Tasks + Fix Aider First

## Goal

Fix the Aider environment crash, then revalidate the harness with 3 small Astropy tasks.
Goal is **method validation** — stable runs, low baseline variance, hard primary metric `tests_pass`.

---

## Current Context

### Aider Crash (Blocker)
- `/home/smlflg/.local/bin/aider` → system Python → litellm without `BadGatewayError` → crash
- `uv run python -m aider` → tries to import from `.venv` but `aider/__init__.py` is missing
- `aider-chat` package installed but `aider` top-level package not created correctly
- **Root cause:** The `aider-chat` package doesn't expose an `aider` import path — it uses `aider_chat`

### SymPy as Too Hard
- `sympy__sympy-20590`: all 4 baseline runs failed — Aider only modified `.gitignore`
- This task requires understanding a complex class hierarchy (`__slots__` inheritance chain)
- Not suitable for V0 method validation — mark as archived, move on

### Available Astropy Candidates
Already in `swebench_lite_candidates.json`:
- `astropy__astropy-12907` — separability_matrix bug, 2 FAIL_TO_PASS, ~12 PASS_TO_PASS
- `astropy__astropy-14182` — RST header_rows support, 1 FAIL_TO_PASS, ~8 PASS_TO_PASS

Need 1 more Astropy task. Must fetch candidates with low complexity.

---

## Proposed Approach

### Phase 1: Fix Aider (Prerequisite)

**Option A — Fix via proper uv execution:**
```bash
# Create a wrapper that uses the correct python
cat > ~/.local/bin/aider-uv << 'EOF'
#!/bin/bash
exec /home/smlflg/.local/share/uv/python/cpython-3.13.11-linux-x86_64-gnu/bin/python -m aider "$@"
EOF
chmod +x ~/.local/bin/aider-uv
```

**Option B — Downgrade to working version:**
Find a version of `aider-chat` or `aider` that works with the current litellm version.

**Option C — Use uv run with the right entry point:**
```bash
uv run aider --version
```
Check if the `harness-run-once` script uses `subprocess` with the right Python.

**Recommended: Option C** — first verify `uv run aider` works, then ensure `run_once.py` calls the correct binary.

### Phase 2: Task Selection

Fetch SWE-bench Lite candidates filtered by:
- repo: `astropy/astropy`
- FAIL_TO_PASS count: 1
- PASS_TO_PASS count: ≤10
- Expected diff: ≤5 lines, 1 file

Run:
```bash
uv run harness-fetch-candidates --limit 50
# Then filter for astropy tasks with small FAIL_TO_PASS
```

Select top 3 by:
1. Smallest number of FAIL_TO_PASS tests (prefer 1)
2. Fewest PASS_TO_PASS tests (lower risk of regression)
3. Shortest expected test runtime

### Phase 3: Baseline Variance Measurement

For each of 3 tasks:
- 5 runs with `CONVENTIONS.baseline.md`
- Record: `task_success`, `tests_passed/total`, `duration_seconds`, `judge_score`
- Stop if any task shows 0% or 100% success rate across all runs (no variance = useless)

### Phase 4: Archive SymPy

Add note to `results/baseline/sympy__sympy-20590/README_ARCHIVED.md`:
```markdown
# Archived: sympy__sympy-20590

## Reason
Too hard for V0 method validation. Aider requires understanding complex
`__slots__` inheritance chain across 3+ files. All 4 baseline runs produced
only `.gitignore` changes. Not suitable for measuring prompt sensitivity.

## Status
Archived 2026-04-16. Do not use for harness prompt iteration.
```

---

## Step-by-Step Plan

### Step 1: Fix Aider
- [ ] Test `uv run aider --version` inside project dir
- [ ] If it works: update `run_once.py` to use `uv run` prefix for aider command
- [ ] If not: apply Option A (wrapper script)
- [ ] Verify with: `uv run aider --model minimax/MiniMax-M2.7 --read CONVENTIONS.md --yes-always --no-auto-commits --no-show-model-warnings --message "reply with OK" /tmp`

### Step 2: Fetch Astropy Candidates
- [ ] Run `uv run harness-fetch-candidates --limit 100`
- [ ] Filter output for astropy tasks with FAIL_TO_PASS count ≤ 2
- [ ] Select 3 tasks with smallest FAIL_TO_PASS
- [ ] Update `data/selected_tasks_e2e.json` with chosen tasks

### Step 3: Archive SymPy
- [ ] Create `results/baseline/sympy__sympy-20590/README_ARCHIVED.md`
- [ ] Update `data/selected_tasks_e2e.json` — remove sympy entry

### Step 4: Smoke Test
- [ ] Run 1 baseline on first Astropy task
- [ ] Verify: actual code file changed (not just gitignore)
- [ ] Verify: test_immutable equivalent FAIL_TO_PASS test is addressed

### Step 5: Full Baseline Variance Run
- [ ] 5 runs × 3 tasks = 15 baseline runs
- [ ] Capture all metrics per run
- [ ] Write variance report

---

## Files Likely to Change

```
harness/CONVENTIONS.baseline.md        (unchanged — baseline)
results/baseline/sympy__sympy-20590/README_ARCHIVED.md  (new)
data/selected_tasks_e2e.json           (replace sympy with 3 astropy)
runner/run_once.py                     (possibly fix aider invocation)
```

## Risks / Tradeoffs

1. **Aider fix may take time** — if `uv run aider` also fails, need to dig deeper
2. **Astropy tasks may also be too hard** — if 3 runs all fail on actual bug fix, need to find even simpler tasks
3. **Only 3 tasks** — statistical power is low, but sufficient for method validation
4. **API budget** — 15 baseline runs + subsequent mutation runs. Need to be careful.

## Open Questions

1. Should we use the full `uv run` prefix in `run_once.py` for the aider command, or a custom wrapper script?
2. What complexity threshold for task selection? (lines of test_patch as proxy?)
3. Do we keep the existing `CONVENTIONS.baseline.md` as-is, or is the Karpathy iteration approach now the priority?
