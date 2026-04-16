from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runner.config import load_config, subprocess_env
from runner.db import (
    connect,
    init_db,
    insert_calibration_run,
    insert_run,
    upsert_conventions,
)
from runner.metrics import diff_stats, tests_json_from_report, totals_from_tests_json
from runner.paths import (
    DEFAULT_BASELINE_CONVENTIONS,
    DEFAULT_SELECTED_TASKS_PATH,
    RESULTS_DIR,
    ensure_project_dirs,
)
from runner.swebench_data import find_task
from runner.tokens import estimate_agent_cost, extract_token_counts


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_cmd(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        timeout=timeout,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_cmd_streaming(
    cmd: list[str],
    stdout_path: Path,
    stderr_path: Path,
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")

    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env or None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    def _tee(pipe, file_path: Path, buf: list[str]) -> None:
        try:
            with open(file_path, "a", encoding="utf-8", errors="replace") as fh:
                for line in pipe:
                    fh.write(line)
                    fh.flush()
                    os.fsync(fh.fileno())
                    buf.append(line)
        except (ValueError, OSError):
            pass

    t_out = threading.Thread(
        target=_tee, args=(proc.stdout, stdout_path, stdout_lines), daemon=True
    )
    t_err = threading.Thread(
        target=_tee, args=(proc.stderr, stderr_path, stderr_lines), daemon=True
    )
    t_out.start()
    t_err.start()

    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    t_out.join(timeout=5)
    t_err.join(timeout=5)

    return subprocess.CompletedProcess(
        args=cmd,
        returncode=proc.returncode,
        stdout="".join(stdout_lines),
        stderr="".join(stderr_lines),
    )


def write_phase(artifacts_dir: Path, phase: str) -> None:
    (artifacts_dir / ".phase").write_text(phase, encoding="utf-8")


def repo_url(repo: str) -> str:
    if (
        repo.startswith("http://")
        or repo.startswith("https://")
        or repo.endswith(".git")
    ):
        return repo
    return f"https://github.com/{repo}.git"


def clone_repo(task: dict[str, Any], workdir: Path) -> Path:
    repo_dir = workdir / "repo"
    proc = run_cmd(["git", "clone", repo_url(task["repo"]), str(repo_dir)], cwd=workdir)
    if proc.returncode != 0:
        raise RuntimeError(f"git clone failed:\n{proc.stderr}")
    proc = run_cmd(["git", "checkout", task["base_commit"]], cwd=repo_dir)
    if proc.returncode != 0:
        raise RuntimeError(f"git checkout failed:\n{proc.stderr}")
    return repo_dir


def export_diff(repo_dir: Path) -> str:
    proc = run_cmd(["git", "diff", "--no-ext-diff"], cwd=repo_dir)
    return proc.stdout


def find_report(artifacts_dir: Path, instance_id: str) -> dict[str, Any] | None:
    for report_path in artifacts_dir.rglob("report.json"):
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if instance_id in report:
            return report[instance_id]
    return None


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


INFRA_ERROR_PATTERNS = [
    "litellm.badrequesterror",
    "litellm.apiconnectionerror",
    "provider not provided",
    "authenticationerror",
    "authorized_error",
    "login fail",
    "connectionerror",
    "timeout connecting to",
    "docker daemon not running",
    "could not pull image",
]


def is_infrastructure_error(stdout: str, stderr: str) -> bool:
    haystack = f"{stdout}\n{stderr}".lower()
    return any(pat in haystack for pat in INFRA_ERROR_PATTERNS)


def extract_error_detail(stdout: str, stderr: str) -> str | None:
    haystack = f"{stdout}\n{stderr}".lower()
    for pat in INFRA_ERROR_PATTERNS:
        idx = haystack.find(pat)
        if idx < 0:
            continue
        lines = haystack[:idx].split("\n")
        start = max(0, len(lines) - 1)
        source = f"{stdout}\n{stderr}"
        all_lines = source.split("\n")
        char_offset = len(haystack[:idx])
        line_idx = source[:char_offset].count("\n")
        lo = max(0, line_idx - 2)
        hi = min(len(all_lines), line_idx + 3)
        snippet = "\n".join(all_lines[lo:hi]).strip()
        return snippet[:500] if snippet else pat
    return None


def failure_kind(infrastructure_error: bool, task_success: bool) -> str:
    if infrastructure_error:
        return "infrastructure_error"
    if task_success:
        return "success"
    return "task_failure"


def run_swebench_eval(
    *,
    artifacts_dir: Path,
    task: dict[str, Any],
    model_name: str,
    patch: str,
    run_id: str,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    predictions_path = artifacts_dir / "predictions.jsonl"
    prediction = {
        "instance_id": task["instance_id"],
        "model_name_or_path": model_name,
        "model_patch": patch,
    }
    predictions_path.write_text(json.dumps(prediction) + "\n", encoding="utf-8")
    return run_cmd(
        [
            sys.executable,
            "-m",
            "swebench.harness.run_evaluation",
            "--dataset_name",
            "princeton-nlp/SWE-bench_Lite",
            "--split",
            "test",
            "--predictions_path",
            str(predictions_path),
            "--max_workers",
            "1",
            "--timeout",
            str(timeout),
            "--run_id",
            run_id,
            "--report_dir",
            str(artifacts_dir),
            "--instance_ids",
            task["instance_id"],
        ],
        cwd=artifacts_dir,
        timeout=timeout,
    )


def build_run_id(condition: str, task_id: str, run_index: int) -> str:
    clean_task = task_id.replace("/", "__")
    return f"{condition}_{clean_task}_run{run_index:02d}"


def execute(args: argparse.Namespace) -> dict[str, Any]:
    ensure_project_dirs()
    init_db()
    config = load_config()
    task = find_task(args.task_id, args.task_file)
    condition = args.condition
    run_id = args.run_id or build_run_id(condition, task["instance_id"], args.run_index)
    artifacts_dir = RESULTS_DIR / condition / task["instance_id"] / run_id
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    start = utc_now()
    started = time.monotonic()
    exit_code = 0
    patch = ""
    agent_stdout = ""
    agent_stderr = ""
    eval_stdout = ""
    eval_stderr = ""
    tests_json: dict[str, Any] = tests_json_from_report(None)
    infrastructure_error = False
    error_detail: str | None = None
    repo_dir: Path | None = None

    agent_stdout_path = artifacts_dir / "agent_stdout.log"
    agent_stderr_path = artifacts_dir / "agent_stderr.log"
    eval_stdout_path = artifacts_dir / "eval_stdout.log"
    eval_stderr_path = artifacts_dir / "eval_stderr.log"

    for p in (agent_stdout_path, agent_stderr_path, eval_stdout_path, eval_stderr_path):
        p.write_text("", encoding="utf-8")

    write_phase(artifacts_dir, "setup_repo")

    conventions_path = args.conventions_path
    try:
        with tempfile.TemporaryDirectory(prefix="swebench-aider-") as tmp:
            workdir = Path(tmp)
            if args.skip_agent:
                (workdir / "repo").mkdir()
                repo_dir = workdir / "repo"
                (repo_dir / "CONVENTIONS.md").write_text(
                    conventions_path.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
            else:
                repo_dir = clone_repo(task, workdir)
                shutil.copyfile(conventions_path, repo_dir / "CONVENTIONS.md")
                write_phase(artifacts_dir, "aider_running")
                aider_cmd = [
                    "aider",
                    "--model",
                    args.model_name or config.aider_model,
                    "--read",
                    "CONVENTIONS.md",
                    *config.aider_extra_args,
                    "--message",
                    task["problem_statement"],
                ]
                agent_proc = run_cmd_streaming(
                    aider_cmd,
                    agent_stdout_path,
                    agent_stderr_path,
                    cwd=repo_dir,
                    env=subprocess_env(config),
                    timeout=args.agent_timeout,
                )
                agent_stdout = agent_proc.stdout
                agent_stderr = agent_proc.stderr
                infrastructure_error = is_infrastructure_error(
                    agent_stdout, agent_stderr
                )
                if infrastructure_error:
                    error_detail = extract_error_detail(agent_stdout, agent_stderr)
                if agent_proc.returncode != 0:
                    exit_code = agent_proc.returncode
                if infrastructure_error and exit_code == 0:
                    exit_code = 1
                patch = export_diff(repo_dir)

            if args.skip_eval:
                tests_json = args.synthetic_tests or tests_json
            elif patch:
                write_phase(artifacts_dir, "docker_eval")
                predictions_path = artifacts_dir / "predictions.jsonl"
                prediction = {
                    "instance_id": task["instance_id"],
                    "model_name_or_path": args.model_name or config.aider_model,
                    "model_patch": patch,
                }
                predictions_path.write_text(
                    json.dumps(prediction) + "\n", encoding="utf-8"
                )
                eval_cmd = [
                    sys.executable,
                    "-m",
                    "swebench.harness.run_evaluation",
                    "--dataset_name",
                    "princeton-nlp/SWE-bench_Lite",
                    "--split",
                    "test",
                    "--predictions_path",
                    str(predictions_path),
                    "--max_workers",
                    "1",
                    "--timeout",
                    str(args.eval_timeout),
                    "--run_id",
                    run_id,
                    "--report_dir",
                    str(artifacts_dir),
                    "--instance_ids",
                    task["instance_id"],
                ]
                eval_proc = run_cmd_streaming(
                    eval_cmd,
                    eval_stdout_path,
                    eval_stderr_path,
                    cwd=artifacts_dir,
                    timeout=args.eval_timeout,
                )
                eval_stdout = eval_proc.stdout
                eval_stderr = eval_proc.stderr
                if eval_proc.returncode != 0 and exit_code == 0:
                    exit_code = eval_proc.returncode
                tests_json = tests_json_from_report(
                    find_report(artifacts_dir, task["instance_id"])
                )
            else:
                repo_dir = clone_repo(task, workdir)
                shutil.copyfile(conventions_path, repo_dir / "CONVENTIONS.md")
                aider_cmd = [
                    "aider",
                    "--model",
                    args.model_name or config.aider_model,
                    "--read",
                    "CONVENTIONS.md",
                    *config.aider_extra_args,
                    "--message",
                    task["problem_statement"],
                ]
                agent_proc = run_cmd(
                    aider_cmd,
                    cwd=repo_dir,
                    env=subprocess_env(config),
                    timeout=args.agent_timeout,
                )
                agent_stdout = agent_proc.stdout
                agent_stderr = agent_proc.stderr
                infrastructure_error = is_infrastructure_error(
                    agent_stdout, agent_stderr
                )
                if infrastructure_error:
                    error_detail = extract_error_detail(agent_stdout, agent_stderr)
                if agent_proc.returncode != 0:
                    exit_code = agent_proc.returncode
                if infrastructure_error and exit_code == 0:
                    exit_code = 1
                patch = export_diff(repo_dir)

            if args.skip_eval:
                tests_json = args.synthetic_tests or tests_json
            elif patch:
                eval_proc = run_swebench_eval(
                    artifacts_dir=artifacts_dir,
                    task=task,
                    model_name=args.model_name or config.aider_model,
                    patch=patch,
                    run_id=run_id,
                    timeout=args.eval_timeout,
                )
                eval_stdout = eval_proc.stdout
                eval_stderr = eval_proc.stderr
                if eval_proc.returncode != 0 and exit_code == 0:
                    exit_code = eval_proc.returncode
                tests_json = tests_json_from_report(
                    find_report(artifacts_dir, task["instance_id"])
                )
    except Exception as exc:
        exit_code = exit_code or 1
        agent_stderr += f"\nHARNESS_ERROR: {exc}\n"
        if not infrastructure_error and is_infrastructure_error(
            agent_stdout, agent_stderr
        ):
            infrastructure_error = True
            error_detail = (
                error_detail
                or extract_error_detail(agent_stdout, agent_stderr)
                or str(exc)
            )
        write_phase(artifacts_dir, "error")

    end = utc_now()
    duration = time.monotonic() - started
    files_changed, lines_added, lines_removed = diff_stats(patch)
    tests_total, tests_passed, task_success = totals_from_tests_json(tests_json)
    tokens_in, tokens_out = extract_token_counts(agent_stdout + "\n" + agent_stderr)
    cost_estimate = estimate_agent_cost(tokens_in, tokens_out, config)

    (artifacts_dir / "git_diff.patch").write_text(patch, encoding="utf-8")
    write_json(artifacts_dir / "tests.json", tests_json)
    judge_input = {
        "task_id": task["instance_id"],
        "problem_statement": task["problem_statement"],
        "diff": patch,
        "tests": tests_json,
    }
    write_json(artifacts_dir / "judge_input.json", judge_input)

    run_meta = {
        "run_id": run_id,
        "task_id": task["instance_id"],
        "condition_id": condition,
        "model_name": args.model_name or config.aider_model,
        "harness_name": "aider",
        "instruction_file": str(conventions_path),
        "start_ts": start,
        "end_ts": end,
        "duration_seconds": duration,
        "exit_code": exit_code,
        "infrastructure_error": infrastructure_error,
        "error_detail": error_detail,
        "failure_kind": failure_kind(infrastructure_error, bool(task_success)),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_estimate": cost_estimate,
        "files_changed": files_changed,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "tests_total": tests_total,
        "tests_passed": tests_passed,
        "task_success": bool(task_success and not infrastructure_error),
    }
    write_json(artifacts_dir / "run_meta.json", run_meta)
    write_phase(artifacts_dir, "done")

    with connect() as conn:
        conventions_hash = upsert_conventions(
            conn,
            conventions_path,
            parent_hash=args.parent_conventions_hash,
            mutation_note=args.mutation_note,
        )
        db_row = {
            "run_id": run_id,
            "task_id": task["instance_id"],
            "condition_id": condition,
            "iteration": args.iteration,
            "model_name": args.model_name or config.aider_model,
            "conventions_hash": conventions_hash,
            "conventions_path": str(conventions_path),
            "start_ts": start,
            "end_ts": end,
            "duration_seconds": duration,
            "exit_code": exit_code,
            "infrastructure_error": int(infrastructure_error),
            "error_detail": error_detail,
            "failure_kind": failure_kind(infrastructure_error, bool(task_success)),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_estimate": cost_estimate,
            "tests_total": tests_total,
            "tests_passed": tests_passed,
            "task_success": int(task_success and not infrastructure_error),
            "files_changed": files_changed,
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "judge_score": None,
            "artifacts_dir": str(artifacts_dir),
        }
        if args.calibration_round is None:
            insert_run(conn, db_row)
        else:
            insert_calibration_run(
                conn,
                {
                    "calibration_run_id": run_id,
                    "task_id": task["instance_id"],
                    "round": args.calibration_round,
                    "run_index": args.run_index,
                    "model_name": args.model_name or config.aider_model,
                    "conventions_hash": conventions_hash,
                    "start_ts": start,
                    "end_ts": end,
                    "duration_seconds": duration,
                    "exit_code": exit_code,
                    "infrastructure_error": int(infrastructure_error),
                    "error_detail": error_detail,
                    "failure_kind": failure_kind(
                        infrastructure_error, bool(task_success)
                    ),
                    "tests_total": tests_total,
                    "tests_passed": tests_passed,
                    "task_success": int(task_success and not infrastructure_error),
                    "artifacts_dir": str(artifacts_dir),
                },
            )
    return run_meta


def parse_synthetic_tests(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    return json.loads(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one Aider + SWE-bench task.")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--task-file", type=Path, default=DEFAULT_SELECTED_TASKS_PATH)
    parser.add_argument("--condition", default="baseline")
    parser.add_argument("--iteration", type=int, default=1)
    parser.add_argument("--run-index", type=int, default=1)
    parser.add_argument("--run-id")
    parser.add_argument("--model-name")
    parser.add_argument(
        "--conventions-path", type=Path, default=DEFAULT_BASELINE_CONVENTIONS
    )
    parser.add_argument("--parent-conventions-hash")
    parser.add_argument("--mutation-note")
    parser.add_argument("--calibration-round", type=int)
    parser.add_argument("--skip-agent", action="store_true")
    parser.add_argument("--skip-eval", action="store_true")
    parser.add_argument("--synthetic-tests-json", dest="synthetic_tests")
    parser.add_argument("--agent-timeout", type=int, default=1800)
    parser.add_argument("--eval-timeout", type=int, default=7200)
    args = parser.parse_args()
    args.synthetic_tests = parse_synthetic_tests(args.synthetic_tests)
    meta = execute(args)
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
