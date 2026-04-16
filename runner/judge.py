from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path

from runner.config import load_config, subprocess_env
from runner.db import connect
from runner.tokens import estimate_judge_cost, extract_token_counts


def neutral_result(model: str) -> dict:
    return {
        "judge_model": model,
        "scope_adherence": 3,
        "minimality": 3,
        "diff_clarity": 3,
        "judge_score": 3.0,
        "tokens_in": None,
        "tokens_out": None,
        "cost_estimate": None,
        "rationale": "Stub judge result. Configure JUDGE_COMMAND for real judging.",
    }


def run_judge_command(command: str, judge_input: Path, model: str) -> dict:
    config = load_config()
    cmd = [*shlex.split(command), str(judge_input)]
    proc = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=subprocess_env(config),
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"Judge command failed:\n{proc.stderr}")
    result = json.loads(proc.stdout)
    result.setdefault("judge_model", model)
    tokens_in, tokens_out = extract_token_counts(proc.stdout + "\n" + proc.stderr)
    result.setdefault("tokens_in", tokens_in)
    result.setdefault("tokens_out", tokens_out)
    result.setdefault("cost_estimate", estimate_judge_cost(tokens_in, tokens_out, config))
    return result


def update_score(artifacts_dir: Path, score: float) -> None:
    run_meta_path = artifacts_dir / "run_meta.json"
    if not run_meta_path.exists():
        return
    run_id = json.loads(run_meta_path.read_text(encoding="utf-8"))["run_id"]
    with connect() as conn:
        conn.execute("UPDATE runs SET judge_score = ? WHERE run_id = ?", (score, run_id))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run blind LLM judge for one artifact dir.")
    parser.add_argument("--artifacts-dir", type=Path, required=True)
    parser.add_argument("--allow-stub", action="store_true")
    args = parser.parse_args()
    config = load_config()
    judge_input = args.artifacts_dir / "judge_input.json"
    if not judge_input.exists():
        raise SystemExit(f"Missing judge input: {judge_input}")
    if config.judge_command:
        result = run_judge_command(config.judge_command, judge_input, config.judge_model)
    elif args.allow_stub:
        result = neutral_result(config.judge_model)
    else:
        raise SystemExit("JUDGE_COMMAND is not configured. Use --allow-stub only for smoke tests.")
    (args.artifacts_dir / "judge_result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    update_score(args.artifacts_dir, float(result["judge_score"]))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
