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
from runner.metrics import (
    diff_stats,
    unrelated_edits_present,
    tests_json_from_report,
    totals_from_tests_json,
)
from runner.failure_reasons import (
    FailureReason,
    derive_status,
    enforce_task_failure_guard,
    infer_agent_failure_reason,
    infer_eval_failure_reason,
)
from runner.events import EventLogger, RunContext
from runner.paths import (
    DEFAULT_BASELINE_CONVENTIONS,
    DEFAULT_SELECTED_TASKS_PATH,
    RESULTS_DIR,
    ensure_project_dirs,
)
from runner.swebench_data import find_task
from runner.tokens import estimate_agent_cost, extract_token_counts
from runner.judge import sanitize_judge_input


def cleanup_swebench_containers(identifier: str) -> dict[str, Any]:
    removed: list[str] = []
    error: str | None = None
    try:
        import docker

        client = docker.from_env()
        for container in client.containers.list(all=True):
            if identifier in container.name:
                removed.append(container.name)
                container.remove(force=True)
    except Exception as exc:
        error = str(exc)
    return {"removed": removed, "error": error}


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


REPO_CACHE = RESULTS_DIR / "repo_cache"
MAX_CACHED_REPOS = 10


def _repo_cache_key(task: dict[str, Any]) -> str:
    return f"{task['repo'].replace('/', '__')}_{task['base_commit']}"


def enforce_lru_cache_limit(max_repos: int = MAX_CACHED_REPOS) -> None:
    if not REPO_CACHE.exists():
        return
    entries = [(p, p.stat().st_mtime) for p in REPO_CACHE.iterdir() if p.is_dir()]
    if len(entries) <= max_repos:
        return
    entries.sort(key=lambda x: x[1])
    for path, _ in entries[: len(entries) - max_repos]:
        shutil.rmtree(path)


def get_cached_repo(task: dict[str, Any], workdir: Path) -> Path:
    cache_key = _repo_cache_key(task)
    cached = REPO_CACHE / cache_key
    target = workdir / "repo"

    if cached.exists():
        os.utime(cached, None)
        shutil.copytree(cached, target, dirs_exist_ok=False)
    else:
        tmp = tempfile.mkdtemp(prefix="clone_")
        repo_dir = Path(tmp) / "repo"
        run_cmd(["git", "clone", repo_url(task["repo"]), str(repo_dir)], cwd=Path(tmp))
        run_cmd(["git", "checkout", task["base_commit"]], cwd=repo_dir)
        shutil.copytree(repo_dir, cached, dirs_exist_ok=True)
        shutil.copytree(repo_dir, target, dirs_exist_ok=False)
    return target


def evict_stale_cache() -> None:
    enforce_lru_cache_limit(MAX_CACHED_REPOS)


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


def get_head(repo_dir: Path) -> str:
    proc = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir)
    return proc.stdout.strip()


def commit_conventions(repo_dir: Path) -> None:
    run_cmd(["git", "config", "user.name", "harness"], cwd=repo_dir)
    run_cmd(["git", "config", "user.email", "harness@local"], cwd=repo_dir)
    run_cmd(["git", "add", "CONVENTIONS.md"], cwd=repo_dir)
    run_cmd(
        ["git", "commit", "-m", "harness: add CONVENTIONS.md", "--no-gpg-sign"],
        cwd=repo_dir,
    )


def export_diff_v2(repo_dir: Path, pre_head: str | None) -> tuple[str, str]:
    if pre_head:
        log_proc = run_cmd(
            ["git", "log", f"{pre_head}..HEAD", "--oneline"], cwd=repo_dir
        )
        has_commits = bool(log_proc.stdout.strip())
        diff_proc = run_cmd(["git", "diff", "--no-ext-diff", pre_head], cwd=repo_dir)
        if diff_proc.stdout.strip():
            return diff_proc.stdout, "auto_commits" if has_commits else "uncommitted"
    diff_proc = run_cmd(["git", "diff", "--no-ext-diff"], cwd=repo_dir)
    if diff_proc.stdout.strip():
        return diff_proc.stdout, "uncommitted"
    return "", "none"


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
    from runner.paths import (
        PROJECT_ROOT,
    )  # local import to avoid module-level scope issues

    ensure_project_dirs()
    init_db()
    config = load_config()
    task = find_task(args.task_id, args.task_file)
    condition = args.condition
    run_id = args.run_id or build_run_id(condition, task["instance_id"], args.run_index)
    artifacts_dir = RESULTS_DIR / condition / task["instance_id"] / run_id
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    context = RunContext(
        run_id=run_id,
        condition_id=condition,
        task_id=task["instance_id"],
        iteration=args.iteration,
        run_index=args.run_index,
    )
    events = EventLogger(artifacts_dir / "events.jsonl", context)
    events.emit(phase="setup_repo", event="run_start")

    start = utc_now()
    started = time.monotonic()
    exit_code = 0
    patch = ""
    pre_head: str | None = None
    diff_source: str = "none"
    agent_stdout = ""
    agent_stderr = ""
    eval_stdout = ""
    eval_stderr = ""
    tests_json: dict[str, Any] = tests_json_from_report(None)
    infrastructure_error = False
    error_detail: str | None = None
    repo_dir: Path | None = None
    failure_reason = FailureReason.SUCCESS
    eval_attempted = False
    eval_completed = False
    report_found = False

    agent_stdout_path = artifacts_dir / "agent_stdout.log"
    agent_stderr_path = artifacts_dir / "agent_stderr.log"
    eval_stdout_path = artifacts_dir / "eval_stdout.log"
    eval_stderr_path = artifacts_dir / "eval_stderr.log"

    for p in (agent_stdout_path, agent_stderr_path, eval_stdout_path, eval_stderr_path):
        p.write_text("", encoding="utf-8")

    write_phase(artifacts_dir, "setup_repo")
    events.emit(phase="setup_repo", event="phase_enter")

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
                repo_dir = get_cached_repo(task, workdir)
                shutil.copyfile(conventions_path, repo_dir / "CONVENTIONS.md")
                commit_conventions(repo_dir)
                pre_head = get_head(repo_dir)

                write_phase(artifacts_dir, "aider_running")
                events.emit(phase="aider_running", event="phase_enter")
                # Use project venv python for aider to ensure it's available
                aider_python = str(PROJECT_ROOT / ".venv" / "bin" / "python")
                aider_cmd = [
                    aider_python,
                    "-m",
                    "aider",
                    "--model",
                    args.model_name or config.aider_model,
                    "--read",
                    "CONVENTIONS.md",
                    *config.aider_extra_args,
                    "--message",
                    task["problem_statement"],
                ]
                events.emit(phase="aider_running", event="agent_start")
                agent_proc = run_cmd_streaming(
                    aider_cmd,
                    agent_stdout_path,
                    agent_stderr_path,
                    cwd=repo_dir,
                    env=subprocess_env(config),
                    timeout=args.agent_timeout,
                )
                events.emit(
                    phase="aider_running",
                    event="agent_end",
                    status="ok" if agent_proc.returncode == 0 else "error",
                    details={"returncode": agent_proc.returncode},
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
                    failure_reason = infer_agent_failure_reason(
                        agent_stdout, agent_stderr, agent_proc.returncode
                    )
                if infrastructure_error and exit_code == 0:
                    exit_code = 1
                    failure_reason = infer_agent_failure_reason(
                        agent_stdout, agent_stderr, exit_code
                    )
                patch, diff_source = export_diff_v2(repo_dir, pre_head)

                if not patch:
                    write_phase(artifacts_dir, "aider_retry")
                    events.emit(phase="aider_retry", event="phase_enter")
                    repo_dir = get_cached_repo(task, workdir)
                    shutil.copyfile(conventions_path, repo_dir / "CONVENTIONS.md")
                    commit_conventions(repo_dir)
                    pre_head = get_head(repo_dir)
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
                        failure_reason = infer_agent_failure_reason(
                            agent_stdout, agent_stderr, agent_proc.returncode
                        )
                    if infrastructure_error and exit_code == 0:
                        exit_code = 1
                        failure_reason = infer_agent_failure_reason(
                            agent_stdout, agent_stderr, exit_code
                        )
                    patch, diff_source = export_diff_v2(repo_dir, pre_head)

            if args.skip_eval:
                tests_json = args.synthetic_tests or tests_json
            elif patch:
                eval_attempted = True
                write_phase(artifacts_dir, "docker_eval")
                events.emit(phase="docker_eval", event="phase_enter")
                predictions_path = artifacts_dir / "predictions.jsonl"
                prediction = {
                    "instance_id": task["instance_id"],
                    "model_name_or_path": args.model_name or config.aider_model,
                    "model_patch": patch,
                }
                predictions_path.write_text(
                    json.dumps(prediction) + "\n", encoding="utf-8"
                )
                eval_run_id = f"{run_id}_{int(time.time() * 1000)}_{os.getpid()}"
                pre_cleanup = cleanup_swebench_containers(run_id)
                events.emit(
                    phase="docker_eval",
                    event="docker_cleanup_pre",
                    status="ok" if not pre_cleanup["error"] else "error",
                    details=pre_cleanup,
                )
                if pre_cleanup["error"] and failure_reason == FailureReason.SUCCESS:
                    failure_reason = FailureReason.EVAL_CONTAINER_CLEANUP_ERROR
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
                    eval_run_id,
                    "--report_dir",
                    str(artifacts_dir),
                    "--instance_ids",
                    task["instance_id"],
                ]
                events.emit(
                    phase="docker_eval",
                    event="eval_start",
                    details={"eval_run_id": eval_run_id},
                )
                eval_proc = run_cmd_streaming(
                    eval_cmd,
                    eval_stdout_path,
                    eval_stderr_path,
                    cwd=artifacts_dir,
                    timeout=args.eval_timeout,
                )
                events.emit(
                    phase="docker_eval",
                    event="eval_end",
                    status="ok" if eval_proc.returncode == 0 else "error",
                    details={"returncode": eval_proc.returncode},
                )
                eval_stdout = eval_proc.stdout
                eval_stderr = eval_proc.stderr
                if eval_proc.returncode != 0 and exit_code == 0:
                    exit_code = eval_proc.returncode
                    failure_reason = infer_eval_failure_reason(
                        eval_stdout, eval_stderr, eval_proc.returncode
                    )
                report_payload = find_report(artifacts_dir, task["instance_id"])
                report_found = report_payload is not None
                events.emit(
                    phase="docker_eval",
                    event="report_parse",
                    status="ok" if report_found else "error",
                    details={"report_found": report_found},
                )
                tests_json = tests_json_from_report(report_payload)
                eval_completed = report_found
                if eval_attempted and not report_found and exit_code == 0:
                    failure_reason = FailureReason.EVAL_REPORT_MISSING
                    exit_code = 1
                post_cleanup = cleanup_swebench_containers(run_id)
                events.emit(
                    phase="docker_eval",
                    event="docker_cleanup_post",
                    status="ok" if not post_cleanup["error"] else "error",
                    details=post_cleanup,
                )
                if post_cleanup["error"] and failure_reason == FailureReason.SUCCESS:
                    failure_reason = FailureReason.EVAL_CONTAINER_CLEANUP_ERROR
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
        if failure_reason == FailureReason.SUCCESS:
            failure_reason = FailureReason.EVAL_PARSE_ERROR
        events.emit(
            phase="error",
            event="exception",
            status="error",
            failure_reason=failure_reason.value,
            details={"error": str(exc)},
        )
        write_phase(artifacts_dir, "error")

    end = utc_now()
    duration = time.monotonic() - started
    files_changed, lines_added, lines_removed = diff_stats(patch)
    tests_total, tests_passed, task_success = totals_from_tests_json(tests_json)
    if failure_reason == FailureReason.SUCCESS:
        failure_reason = (
            FailureReason.SUCCESS if task_success else FailureReason.TASK_FAILURE
        )
    # Only use EVAL_REPORT_MISSING as fallback when eval was actually attempted.
    # When skip-eval is used, TASK_FAILURE is the correct outcome (agent completed
    # but we have no test evidence of success).
    if eval_attempted:
        failure_reason = enforce_task_failure_guard(
            failure_reason,
            tests_total=tests_total,
            fallback=FailureReason.EVAL_REPORT_MISSING,
        )
    else:
        failure_reason = enforce_task_failure_guard(
            failure_reason,
            tests_total=tests_total,
            fallback=FailureReason.TASK_FAILURE,
        )
    tokens_in, tokens_out = extract_token_counts(agent_stdout + "\n" + agent_stderr)
    cost_estimate = estimate_agent_cost(tokens_in, tokens_out, config)

    (artifacts_dir / "git_diff.patch").write_text(patch, encoding="utf-8")
    write_json(artifacts_dir / "tests.json", tests_json)
    judge_input = sanitize_judge_input(
        {
            "task_id": task["instance_id"],
            "problem_statement": task["problem_statement"],
            "diff": patch,
            "diff_source": diff_source,
            "tests": tests_json,
            "agent_stdout": agent_stdout,
            "agent_stderr": agent_stderr,
        }
    )
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
        "duration_s": duration,
        "exit_code": exit_code,
        "infrastructure_error": infrastructure_error,
        "error_detail": error_detail,
        "failure_kind": failure_reason.value,
        "failure_reason": failure_reason.value,
        "status": derive_status(failure_reason),
        "eval_attempted": eval_attempted,
        "eval_completed": eval_completed,
        "report_found": report_found,
        "diff_source": diff_source,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_estimate": cost_estimate,
        "files_changed": files_changed,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "unrelated_edits_present": unrelated_edits_present(patch),
        "tests_total": tests_total,
        "tests_passed": tests_passed,
        "task_success": bool(task_success and not infrastructure_error),
        "success": bool(task_success and not infrastructure_error),
        "fail_to_pass_total": tests_json.get("FAIL_TO_PASS", {}).get("total", 0),
        "fail_to_pass_passed": tests_json.get("FAIL_TO_PASS", {}).get("passed", 0),
        "pass_to_pass_total": tests_json.get("PASS_TO_PASS", {}).get("total", 0),
        "pass_to_pass_passed": tests_json.get("PASS_TO_PASS", {}).get("passed", 0),
        "target_file": task.get("target_file")
        or (
            task.get("instance_id", "").split("__")[1]
            if "__" in task.get("instance_id", "")
            else None
        ),
        "target_files": task.get("target_files", []),
    }

    # Every run gets its own judge report file in its own artifacts dir.
    # This remains available even when eval fails or no per-instance report exists.
    judge_report = {
        "judge_schema_version": 1,
        "run_id": run_id,
        "task_id": task["instance_id"],
        "condition_id": condition,
        "status": run_meta["status"],
        "failure_reason": run_meta["failure_reason"],
        "eval_attempted": run_meta["eval_attempted"],
        "eval_completed": run_meta["eval_completed"],
        "report_found": run_meta["report_found"],
        "tests": tests_json,
        "summary": {
            "tests_total": tests_total,
            "tests_passed": tests_passed,
            "task_success": bool(task_success and not infrastructure_error),
            "files_changed": files_changed,
            "lines_added": lines_added,
            "lines_removed": lines_removed,
        },
        "artifacts": {
            "judge_input": "judge_input.json",
            "tests": "tests.json",
            "run_meta": "run_meta.json",
            "events": "events.jsonl",
            "git_diff": "git_diff.patch",
            "predictions": "predictions.jsonl",
        },
    }

    write_json(artifacts_dir / "judge_report.json", judge_report)
    write_json(artifacts_dir / "run_meta.json", run_meta)
    events.emit(
        phase="done",
        event="run_end",
        status="ok" if run_meta["status"] == "success" else "error",
        failure_reason=failure_reason.value,
        details={
            "status": run_meta["status"],
            "tests_total": tests_total,
            "tests_passed": tests_passed,
        },
    )
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
            "failure_kind": failure_reason.value,
            "diff_source": diff_source,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_estimate": cost_estimate,
            "tests_total": tests_total,
            "tests_passed": tests_passed,
            "task_success": int(task_success and not infrastructure_error),
            "files_changed": files_changed,
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "fail_to_pass_total": tests_json.get("FAIL_TO_PASS", {}).get("total", 0),
            "fail_to_pass_passed": tests_json.get("FAIL_TO_PASS", {}).get("passed", 0),
            "pass_to_pass_total": tests_json.get("PASS_TO_PASS", {}).get("total", 0),
            "pass_to_pass_passed": tests_json.get("PASS_TO_PASS", {}).get("passed", 0),
            "target_file": run_meta["target_file"],
            "target_files": json.dumps(run_meta["target_files"], ensure_ascii=False),
            "unrelated_edits_present": int(unrelated_edits_present(patch)),
            "judge_score": None,
            "judge_report_path": str(artifacts_dir / "judge_report.json"),
            "judge_report_json": json.dumps(judge_report, ensure_ascii=False),
            "judge_report_schema_version": judge_report.get("judge_schema_version"),
            "judge_report_status": judge_report.get("status"),
            "judge_report_failure_reason": judge_report.get("failure_reason"),
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
                    "failure_kind": failure_reason.value,
                    "tests_total": tests_total,
                    "tests_passed": tests_passed,
                    "task_success": int(task_success and not infrastructure_error),
                    "artifacts_dir": str(artifacts_dir),
                },
            )
    evict_stale_cache()
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
