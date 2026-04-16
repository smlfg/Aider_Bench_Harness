# First Real Harness Evaluation

Disposable Aider + SWE-bench Lite harness for measuring whether small
`CONVENTIONS.md` changes produce measurable coding-agent effects.

## Setup

```bash
uv sync
cp .env.example .env
```

Fill `.env` with the MiniMax endpoint settings, `JUDGE_MODEL` (default `openai/MiniMax-M2.7`), and token prices.
`JUDGE_COMMAND` is optional; when unset, `harness-judge` uses the built-in two-stage judge.
Keep real secrets out of versioned files.

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
