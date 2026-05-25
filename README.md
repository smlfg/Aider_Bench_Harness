# First Real Harness Evaluation

First Real Harness Evaluation is a small measurement rig for testing whether a
Markdown harness policy changes coding-agent behavior in a reproducible way.

The core question is deliberately narrow:

> Under the same model, task set, and measurement pipeline, does one
> `CONVENTIONS.md` policy produce better agent behavior than another?

The project currently focuses on Aider + SWE-bench Lite experiments, with hard
test metrics as the primary evidence and LLM judging only as a secondary
diagnostic layer.

## Current Status

This repository contains working runner, preflight, summary, scientific A/B, and
model-comparison tooling. It does **not** yet claim a decisive result for a
specific policy.

Existing local reports have marked some comparisons as `not_decisive` or
`not_testable` when the validity gate found too few valid paired runs, zero-test
runs, infrastructure failures, or no shared task cells. That is intentional: the
harness separates raw runs from evidence strong enough to support a claim.

## What This Is Not

- Not a general-purpose agent evaluation platform.
- Not a dashboard product.
- Not a proof that any broad "Karpathy-style" rule set is generally good.
- Not a benchmark result unless the validity gate says the comparison is usable.

## Setup

```bash
uv sync
cp .env.example .env
```

Fill `.env` with the MiniMax endpoint settings, `JUDGE_MODEL` (default `openai/MiniMax-M2.7`), and token prices.
`JUDGE_COMMAND` is optional; when unset, `harness-judge` uses the built-in two-stage judge.
Keep real secrets out of versioned files.

Real runs require Docker, Aider, model/API access, and enough time and budget for
SWE-bench Lite task execution.

## Required Preflight

Run this on the host, not inside a restricted sandbox:

```bash
uv run harness-preflight
```

The preflight checks:
- `docker run hello-world`
- Aider x MiniMax in a throwaway repo with `--read CONVENTIONS.md`
- `datasets` and `swebench` imports

If native MiniMax fails in Aider, configure `MINIMAX_BASE_URL` and try an
OpenAI-compatible LiteLLM model name such as `openai/<model>`.

## Smoke Test Without Agent/Docker

```bash
uv run harness-run-once \
  --task-id example__example-1 \
  --task-file data/selected_tasks.example.json \
  --condition baseline \
  --iteration 1 \
  --run-index 1 \
  --skip-agent \
  --skip-eval \
  --synthetic-tests-json '{"FAIL_TO_PASS":{"total":1,"passed":1,"failed":[]},"PASS_TO_PASS":{"total":1,"passed":1,"failed":[]}}'

uv run harness-summarize --iteration 1
```

## Real Flow

Create a candidate policy first, usually by copying a baseline policy and adding
one explicit policy change:

```bash
cp harness/CONVENTIONS.baseline.md harness/CONVENTIONS.candidate.md
```

```bash
uv run harness-fetch-candidates --limit 30
uv run harness-calibrate
uv run harness-run-matrix \
  --candidate-conventions harness/CONVENTIONS.candidate.md \
  --candidate-condition candidate_v1 \
  --mutation-note "one explicit CONVENTIONS.md change"
uv run harness-summarize --iteration 1
```

Each iteration is symmetric: 3 tasks x 5 runs x 2 conditions = 30 runs.

## Scientific A/B Reading

Raw runs are not automatically scientific evidence. Use the A/B layer to filter
invalid runs, pair tasks, detect counterexamples, and separate strong universal
claims from average treatment-effect claims.

```bash
uv run harness-science-ab --list

uv run harness-science-ab \
  --iteration 1 \
  --baseline baseline_6line \
  --candidate negative_control_karpathy40

uv run harness-model-ab --list

uv run harness-model-ab \
  --iteration 7 \
  --condition baseline_6line \
  --baseline-model openai/MiniMax-M2.7 \
  --candidate-model openai/gpt-5.5
```

Outputs:

- `results/summary/scientific_ab_iteration_<N>_<baseline>_vs_<candidate>.md`
- `results/summary/scientific_ab_iteration_<N>_<baseline>_vs_<candidate>.json`
- `results/summary/model_ab_iteration_<N>_<condition>_<baseline_model>_vs_<candidate_model>.md`
- `results/summary/model_ab_iteration_<N>_<condition>_<baseline_model>_vs_<candidate_model>.json`

Protocol: [docs/scientific_evaluation_protocol.md](docs/scientific_evaluation_protocol.md)
Diagram: [web/static/scientific-versuchsaufbau.html](web/static/scientific-versuchsaufbau.html)
