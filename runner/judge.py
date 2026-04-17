from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

from runner.config import load_config, subprocess_env
from runner.db import connect, init_db
from runner.tokens import estimate_judge_cost


PROMPT_VERSION = "two_stage_v1"
JUDGE_LOG_EXCERPT_CHARS = 4000
FORBIDDEN_JUDGE_KEYS = {
    "condition",
    "condition_id",
    "condition_name",
    "conventions_path",
    "conventions_content",
    "policy",
    "policy_file",
    "policy_content",
    "baseline",
    "negative_control",
}


def _extract_log_excerpt(text: str, limit: int = JUDGE_LOG_EXCERPT_CHARS) -> str:
    if not text:
        return ""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def sanitize_judge_input(judge_input: dict[str, Any]) -> dict[str, Any]:
    leaked = sorted(k for k in judge_input.keys() if k in FORBIDDEN_JUDGE_KEYS)
    if leaked:
        raise SystemExit(f"Judge input contains forbidden keys: {', '.join(leaked)}")

    payload = {
        "prompt_version": PROMPT_VERSION,
        "task_id": judge_input.get("task_id"),
        "problem_statement": judge_input.get("problem_statement"),
        "diff": judge_input.get("diff"),
        "diff_source": judge_input.get("diff_source", "uncommitted"),
        "tests": judge_input.get("tests"),
        "agent_stdout": _extract_log_excerpt(str(judge_input.get("agent_stdout", ""))),
        "agent_stderr": _extract_log_excerpt(str(judge_input.get("agent_stderr", ""))),
    }

    if not payload["task_id"] or payload["problem_statement"] is None:
        raise SystemExit("Judge input missing required task_id/problem_statement")

    return payload


def neutral_result(model: str) -> dict[str, Any]:
    return {
        "prompt_version": PROMPT_VERSION,
        "judge_model": model,
        "scope_adherence": 3,
        "minimality": 3,
        "diff_clarity": 3,
        "judge_score": 3.0,
        "rationale": "Stub judge result. Configure a real judge command or use the built-in two-stage judge.",
        "verdict": "mixed",
        "conclusion": "Neutral placeholder result for smoke tests.",
        "tokens_in": None,
        "tokens_out": None,
        "cost_estimate": None,
    }


def _result_row(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "judge_model": result.get("judge_model"),
        "judge_prompt_version": result.get("prompt_version"),
        "judge_scope_adherence": result.get("scope_adherence"),
        "judge_minimality": result.get("minimality"),
        "judge_diff_clarity": result.get("diff_clarity"),
        "judge_verdict": result.get("verdict"),
        "judge_conclusion": result.get("conclusion"),
        "judge_rationale": result.get("rationale"),
        "judge_tokens_in": result.get("tokens_in"),
        "judge_tokens_out": result.get("tokens_out"),
        "judge_cost_estimate": result.get("cost_estimate"),
        "judge_result_json": json.dumps(result, indent=2, ensure_ascii=False),
        "judge_score": result.get("judge_score"),
    }


def _usage_tokens(response: Any) -> tuple[int | None, int | None]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None, None
    tokens_in = getattr(usage, "prompt_tokens", None)
    if tokens_in is None:
        tokens_in = getattr(usage, "input_tokens", None)
    tokens_out = getattr(usage, "completion_tokens", None)
    if tokens_out is None:
        tokens_out = getattr(usage, "output_tokens", None)
    if tokens_in is None or tokens_out is None:
        return None, None
    return int(tokens_in), int(tokens_out)


def _response_text(response: Any) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None) if message is not None else None
    if isinstance(content, list):
        return "".join(str(piece) for piece in content).strip()
    return (content or "").strip()


def _extract_json_text(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty judge response")
    try:
        json.loads(stripped)
        return stripped
    except json.JSONDecodeError:
        pass
    if stripped.startswith("```"):
        stripped = (
            stripped.split("```", 2)[1] if stripped.count("```") >= 2 else stripped
        )
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = stripped[start : end + 1]
        json.loads(candidate)
        return candidate
    raise ValueError(f"judge response is not valid JSON: {text[:500]}")


def _load_json_payload(text: str) -> dict[str, Any]:
    return json.loads(_extract_json_text(text))


def _mean_score(scores: list[float]) -> float:
    return sum(scores) / len(scores) if scores else 3.0


def _judge_input_text(judge_input: dict[str, Any]) -> str:
    payload = sanitize_judge_input(judge_input)
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _build_stage1_messages(judge_input: dict[str, Any]) -> list[dict[str, str]]:
    diff_source = judge_input.get("diff_source", "uncommitted")
    if diff_source == "none":
        user_content = (
            "Aider produced NO diff (no commits, no uncommitted changes).\n"
            "Evaluate the agent's attempt based on its stdout/stderr output.\n\n"
            "- scope_adherence: 1-5, how well the agent's stated intent matched the task scope\n"
            "- minimality: 1-5, how focused the agent's approach was (even without a diff)\n"
            "- diff_clarity: set to 1 (no diff exists to evaluate)\n\n"
            "Set judge_score to the arithmetic mean of the three scores.\n"
            "Write a short rationale of at most 60 words explaining WHY no diff was produced. "
            "Reference concrete output lines, error messages, or agent statements.\n"
            "Return JSON with exactly these keys:\n"
            "scope_adherence, minimality, diff_clarity, judge_score, rationale\n\n"
            f"Evidence:\n{_judge_input_text(judge_input)}"
        )
    else:
        user_content = (
            "Evaluate the patch on three axes:\n"
            "- scope_adherence: 1-5, how tightly the patch stays within the task scope\n"
            "- minimality: 1-5, how small and non-invasive the change is\n"
            "- diff_clarity: 1-5, how understandable and well-structured the diff is\n\n"
            "Set judge_score to the arithmetic mean of the three scores.\n"
            "Write a short rationale of at most 60 words that names at least one concrete file, symbol, or output clue.\n"
            "Return JSON with exactly these keys:\n"
            "scope_adherence, minimality, diff_clarity, judge_score, rationale\n\n"
            f"Evidence:\n{_judge_input_text(judge_input)}"
        )
    return [
        {
            "role": "system",
            "content": (
                "You are the first stage of a blind judge for a coding harness. "
                "Score only patch quality from the supplied evidence, including the full Aider output. "
                "Ground your rationale in concrete files, code locations, or messages when available. "
                "Do not mention the condition label or speculate about hidden context. "
                "Aider automatically adds `.aider*` entries to `.gitignore` and creates `.aider.chat.history.md` "
                "and similar tracking files. These are Aider infrastructure artifacts, NOT part of the user's patch. "
                "Ignore `.aider*` file changes in your evaluation. "
                "Return only valid JSON."
            ),
        },
        {
            "role": "user",
            "content": user_content,
        },
    ]


def _build_stage2_messages(
    judge_input: dict[str, Any], stage1: dict[str, Any]
) -> list[dict[str, str]]:
    diff_source = judge_input.get("diff_source", "uncommitted")
    if diff_source == "none":
        user_content = (
            "No diff was produced. Given the agent output and stage-1 scores, write a conclusion.\n"
            "Choose verdict from: support, mixed, reject.\n"
            "Keep the conclusion under 40 words and explain what the agent attempted and why it failed to produce a diff.\n"
            "Return JSON with exactly these keys:\n"
            "verdict, conclusion\n\n"
            f"Stage 1 JSON:\n{json.dumps(stage1, indent=2, ensure_ascii=False)}\n\n"
            f"Evidence:\n{_judge_input_text(judge_input)}"
        )
    else:
        user_content = (
            "Given the same evidence and the stage-1 scores below, write a concise conclusion.\n"
            "Choose verdict from: support, mixed, reject.\n"
            "Keep the conclusion under 40 words and mention at least one concrete file, patch effect, or unresolved failure.\n"
            "Return JSON with exactly these keys:\n"
            "verdict, conclusion\n\n"
            f"Stage 1 JSON:\n{json.dumps(stage1, indent=2, ensure_ascii=False)}\n\n"
            f"Evidence:\n{_judge_input_text(judge_input)}"
        )
    return [
        {
            "role": "system",
            "content": (
                "You are the second stage of the same blind judge. "
                "You already have the rubric scores from stage 1. "
                "Now write the final conclusion only, and keep it grounded in the full Aider output and diff. "
                "Reference the concrete change or failure mechanism when possible. "
                "Keep it concise, factual, and blind to any hidden condition labels. "
                "Aider automatically adds `.aider*` entries to `.gitignore` and creates `.aider.chat.history.md` "
                "and similar tracking files. These are Aider infrastructure artifacts, NOT part of the user's patch. "
                "Ignore `.aider*` file changes in your evaluation. "
                "Return only valid JSON."
            ),
        },
        {
            "role": "user",
            "content": user_content,
        },
    ]


def _completion(
    model: str, messages: list[dict[str, str]]
) -> tuple[dict[str, Any], int | None, int | None]:
    config = load_config()
    os.environ.update(subprocess_env(config))
    try:
        from litellm import completion
    except Exception as exc:  # pragma: no cover - dependency failure path
        raise SystemExit(f"litellm import failed: {exc}") from exc

    try:
        response = completion(
            model=model,
            messages=messages,
            temperature=0,
            max_tokens=1024,
            timeout=120,
        )
    except Exception as exc:
        raise SystemExit(
            f"Judge completion failed ({model}): {type(exc).__name__}: {exc}"
        ) from exc

    text = _response_text(response)
    if not text:
        raise SystemExit(f"Judge completion returned empty content for model {model}")

    payload = _load_json_payload(text)
    tokens_in, tokens_out = _usage_tokens(response)
    return payload, tokens_in, tokens_out


def _normalize_stage1(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        scope = int(payload["scope_adherence"])
        minimality = int(payload["minimality"])
        clarity = int(payload["diff_clarity"])
    except Exception as exc:
        raise SystemExit(
            f"Judge stage 1 payload missing rubric scores: {payload}"
        ) from exc
    judge_score = payload.get("judge_score")
    if judge_score is None:
        judge_score = _mean_score([float(scope), float(minimality), float(clarity)])
    return {
        "scope_adherence": scope,
        "minimality": minimality,
        "diff_clarity": clarity,
        "judge_score": float(judge_score),
        "rationale": str(payload.get("rationale", "")).strip(),
    }


def _normalize_stage2(payload: dict[str, Any]) -> dict[str, Any]:
    verdict = str(payload.get("verdict", "mixed")).strip().lower()
    if verdict not in {"support", "mixed", "reject"}:
        verdict = "mixed"
    conclusion = str(payload.get("conclusion", "")).strip()
    return {"verdict": verdict, "conclusion": conclusion}


def _run_native_judge(
    judge_input: dict[str, Any],
    model: str,
    config: Any,
) -> dict[str, Any]:
    stage1_payload, stage1_in, stage1_out = _completion(
        model, _build_stage1_messages(judge_input)
    )
    stage1 = _normalize_stage1(stage1_payload)

    stage2_payload, stage2_in, stage2_out = _completion(
        model, _build_stage2_messages(judge_input, stage1)
    )
    stage2 = _normalize_stage2(stage2_payload)

    tokens_in = (
        None
        if stage1_in is None and stage2_in is None
        else (stage1_in or 0) + (stage2_in or 0)
    )
    tokens_out = (
        None
        if stage1_out is None and stage2_out is None
        else (stage1_out or 0) + (stage2_out or 0)
    )
    result = {
        "prompt_version": PROMPT_VERSION,
        "judge_model": model,
        **stage1,
        **stage2,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_estimate": estimate_judge_cost(tokens_in, tokens_out, config),
    }
    return result


def _run_judge_command(command: str, judge_input: Path, model: str) -> dict[str, Any]:
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
    result.setdefault("prompt_version", PROMPT_VERSION)
    result.setdefault("judge_model", model)
    if "judge_score" not in result:
        scores = [
            float(result.get("scope_adherence", 3)),
            float(result.get("minimality", 3)),
            float(result.get("diff_clarity", 3)),
        ]
        result["judge_score"] = _mean_score(scores)
    result.setdefault("rationale", "")
    result.setdefault("verdict", "mixed")
    result.setdefault(
        "conclusion", result.get("rationale", "") or "No conclusion provided."
    )
    return result


def update_score(artifacts_dir: Path, score: float) -> None:
    run_meta_path = artifacts_dir / "run_meta.json"
    if not run_meta_path.exists():
        return
    run_id = json.loads(run_meta_path.read_text(encoding="utf-8"))["run_id"]
    with connect() as conn:
        conn.execute(
            "UPDATE runs SET judge_score = ? WHERE run_id = ?", (score, run_id)
        )


def update_judge_result(artifacts_dir: Path, result: dict[str, Any]) -> None:
    run_meta_path = artifacts_dir / "run_meta.json"
    if not run_meta_path.exists():
        return
    run_id = json.loads(run_meta_path.read_text(encoding="utf-8"))["run_id"]
    init_db()
    row = _result_row(result)
    with connect() as conn:
        conn.execute(
            """
            UPDATE runs SET
              judge_score = ?,
              judge_model = ?,
              judge_prompt_version = ?,
              judge_scope_adherence = ?,
              judge_minimality = ?,
              judge_diff_clarity = ?,
              judge_verdict = ?,
              judge_conclusion = ?,
              judge_rationale = ?,
              judge_tokens_in = ?,
              judge_tokens_out = ?,
              judge_cost_estimate = ?,
              judge_result_json = ?
            WHERE run_id = ?
            """,
            (
                row["judge_score"],
                row["judge_model"],
                row["judge_prompt_version"],
                row["judge_scope_adherence"],
                row["judge_minimality"],
                row["judge_diff_clarity"],
                row["judge_verdict"],
                row["judge_conclusion"],
                row["judge_rationale"],
                row["judge_tokens_in"],
                row["judge_tokens_out"],
                row["judge_cost_estimate"],
                row["judge_result_json"],
                run_id,
            ),
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run blind LLM judge for one artifact dir."
    )
    parser.add_argument("--artifacts-dir", type=Path, required=True)
    parser.add_argument("--allow-stub", action="store_true")
    args = parser.parse_args()
    config = load_config()
    judge_input_path = args.artifacts_dir / "judge_input.json"
    if not judge_input_path.exists():
        raise SystemExit(f"Missing judge input: {judge_input_path}")
    judge_input = json.loads(judge_input_path.read_text(encoding="utf-8"))
    judge_input = sanitize_judge_input(judge_input)

    if config.judge_command:
        result = _run_judge_command(
            config.judge_command, judge_input_path, config.judge_model
        )
    elif args.allow_stub:
        result = neutral_result(config.judge_model)
    else:
        result = _run_native_judge(judge_input, config.judge_model, config)

    (args.artifacts_dir / "judge_result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    update_judge_result(args.artifacts_dir, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
