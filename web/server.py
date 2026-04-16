from __future__ import annotations

import argparse
import json
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from runner.db import connect, init_db
from runner.run_once import is_infrastructure_error
from runner.paths import DATA_DIR, HARNESS_DIR, RESULTS_DIR, ensure_project_dirs

app = FastAPI(title="Harness Dashboard")

STATIC_DIR = Path(__file__).resolve().parent / "static"
DB_PATH = RESULTS_DIR / "experiment.db"

_active_run: dict[str, Any] | None = None
_active_lock = threading.Lock()


class LaunchRequest(BaseModel):
    task_id: str
    condition: str = "baseline"
    iteration: int = 1
    run_index: int = 1
    conventions_path: str | None = None


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


# ── Existing endpoints ────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/runs")
async def api_runs(iteration: int | None = None, condition: str | None = None):
    conn = _db()
    try:
        query = (
            "SELECT r.run_id, r.task_id, r.condition_id, r.iteration, "
            "r.model_name, r.conventions_hash, r.conventions_path, "
            "r.start_ts, r.end_ts, r.duration_seconds, r.exit_code, "
            "r.infrastructure_error, r.failure_kind, "
            "r.tokens_in, r.tokens_out, r.cost_estimate, "
            "r.tests_total, r.tests_passed, r.task_success, "
            "r.files_changed, r.lines_added, r.lines_removed, "
            "r.judge_score, r.artifacts_dir, "
            "r.infrastructure_error, r.failure_kind, r.error_detail, "
            "c.content AS conventions_content, "
            "c.parent_hash AS conventions_parent_hash, "
            "c.mutation_note AS conventions_mutation_note "
            "FROM runs r LEFT JOIN conventions c ON r.conventions_hash = c.conventions_hash"
        )
        clauses: list[str] = []
        params: list[Any] = []
        if iteration is not None:
            clauses.append("r.iteration = ?")
            params.append(iteration)
        if condition is not None:
            clauses.append("r.condition_id = ?")
            params.append(condition)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY r.start_ts"
        rows = conn.execute(query, params).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


@app.get("/api/runs/{run_id}")
async def api_run_detail(run_id: str):
    conn = _db()
    try:
        row = conn.execute(
            "SELECT r.*, c.content AS conventions_content, "
            "c.parent_hash AS conventions_parent_hash, "
            "c.mutation_note AS conventions_mutation_note "
            "FROM runs r LEFT JOIN conventions c ON r.conventions_hash = c.conventions_hash "
            "WHERE r.run_id = ?",
            (run_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, f"Run {run_id} not found")
        result = dict(row)
        art_dir = Path(result["artifacts_dir"]) if result.get("artifacts_dir") else None
        if art_dir and art_dir.exists():
            for fname in (
                "agent_stdout.log",
                "agent_stderr.log",
                "git_diff.patch",
                "tests.json",
                "run_meta.json",
                "judge_result.json",
            ):
                fpath = art_dir / fname
                key = "has_" + fname.replace(".", "_")
                result[key] = fpath.exists() and fpath.stat().st_size > 0
            phase_path = art_dir / ".phase"
            if phase_path.exists():
                result["phase"] = phase_path.read_text(encoding="utf-8").strip()
        return result
    finally:
        conn.close()


@app.get("/api/analysis")
async def api_analysis(iteration: int | None = None):
    conn = _db()
    try:
        query = "SELECT * FROM analysis"
        params: list[Any] = []
        if iteration is not None:
            query += " WHERE iteration = ?"
            params.append(iteration)
        query += " ORDER BY iteration, condition, metric"
        rows = conn.execute(query, params).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


@app.get("/api/comparisons")
async def api_comparisons(iteration: int | None = None):
    conn = _db()
    try:
        query = "SELECT * FROM comparisons"
        params: list[Any] = []
        if iteration is not None:
            query += " WHERE iteration = ?"
            params.append(iteration)
        query += " ORDER BY iteration, metric"
        rows = conn.execute(query, params).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


@app.get("/api/trajectory")
async def api_trajectory():
    conn = _db()
    try:
        rows = conn.execute("SELECT * FROM trajectory ORDER BY iteration").fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


@app.get("/api/status")
async def api_status():
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT run_id, task_id, condition_id, iteration, task_success, "
            "tests_passed, tests_total, duration_seconds, start_ts, end_ts, "
            "files_changed, lines_added, lines_removed, judge_score, artifacts_dir, "
            "infrastructure_error, failure_kind, error_detail "
            "FROM runs ORDER BY start_ts DESC LIMIT 20"
        ).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


@app.get("/api/completed-iterations")
async def api_completed_iterations():
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT DISTINCT iteration FROM runs ORDER BY iteration"
        ).fetchall()
        return [r["iteration"] for r in rows]
    finally:
        conn.close()


@app.get("/api/artifacts/{run_id}/{filename}")
async def api_artifact(run_id: str, filename: str):
    allowed = {
        "agent_stdout.log",
        "agent_stderr.log",
        "git_diff.patch",
        "tests.json",
        "run_meta.json",
        "judge_result.json",
        "judge_input.json",
        "eval_stdout.log",
        "eval_stderr.log",
        ".phase",
    }
    if filename not in allowed:
        raise HTTPException(403, "Filename not allowed")
    conn = _db()
    try:
        row = conn.execute(
            "SELECT artifacts_dir FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, f"Run {run_id} not found")
    art_dir = Path(row["artifacts_dir"])
    fpath = art_dir / filename
    if not fpath.exists():
        raise HTTPException(404, f"File {filename} not found")
    if filename.endswith(".log") or filename.endswith(".patch") or filename == ".phase":
        return PlainTextResponse(fpath.read_text(encoding="utf-8", errors="replace"))
    return PlainTextResponse(fpath.read_text(encoding="utf-8"))


@app.get("/api/log-stream/{run_id}/{stream}")
async def api_log_stream(run_id: str, stream: str):
    if stream not in ("stdout", "stderr", "eval_stdout", "eval_stderr"):
        raise HTTPException(
            400, "stream must be stdout, stderr, eval_stdout, or eval_stderr"
        )
    fname = f"{stream}.log" if stream in ("stdout", "stderr") else f"{stream}.log"
    if stream in ("stdout", "stderr"):
        fname = f"agent_{stream}.log"
    conn = _db()
    try:
        row = conn.execute(
            "SELECT artifacts_dir FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, f"Run {run_id} not found")
    art_dir = Path(row["artifacts_dir"])
    fpath = art_dir / fname

    async def event_generator():
        if fpath.exists():
            content = fpath.read_text(encoding="utf-8", errors="replace")
            if content:
                yield {"event": "full", "data": content}
        else:
            yield {"event": "full", "data": f"(file not found: {fname})"}

    return EventSourceResponse(event_generator())


# ── New cockpit endpoints ──────────────────────────────────────────────


@app.get("/api/tasks")
async def api_tasks():
    candidates_path = DATA_DIR / "swebench_lite_candidates.json"
    selected_path = DATA_DIR / "selected_tasks.json"
    tasks: list[dict] = []
    for p in (candidates_path, selected_path):
        if p.exists():
            try:
                tasks.extend(json.loads(p.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                pass
    seen = set()
    unique = []
    for t in tasks:
        tid = t.get("instance_id") or t.get("task_id")
        if tid and tid not in seen:
            seen.add(tid)
            unique.append(t)
    return unique


@app.get("/api/tasks/{task_id}")
async def api_task_detail(task_id: str):
    from runner.swebench_data import find_task

    try:
        task = find_task(task_id, None)
        return task
    except SystemExit:
        raise HTTPException(404, f"Task {task_id} not found")


@app.get("/api/conventions")
async def api_conventions():
    result = []
    for p in sorted(HARNESS_DIR.glob("CONVENTIONS*.md")):
        content = p.read_text(encoding="utf-8")
        from runner.db import content_hash

        h = content_hash(content)
        result.append(
            {
                "name": p.name,
                "path": str(p),
                "hash": h,
                "content": content,
            }
        )
    return result


def _preflight_checks() -> dict[str, dict[str, str | bool]]:
    import importlib.util
    import shutil

    from dotenv import load_dotenv
    from runner.paths import PROJECT_ROOT

    load_dotenv(PROJECT_ROOT / ".env")

    checks: dict[str, dict[str, str | bool]] = {}

    def _cmd_exists(name: str) -> bool:
        return shutil.which(name) is not None

    docker_ok = False
    try:
        proc = subprocess.run(
            ["docker", "ps"], capture_output=True, timeout=10, check=False
        )
        docker_ok = proc.returncode == 0
    except Exception:
        pass
    checks["docker"] = {
        "label": "Docker Daemon",
        "ok": docker_ok,
        "detail": "running" if docker_ok else "not reachable",
    }

    swebench_ok = importlib.util.find_spec("swebench") is not None
    checks["swebench"] = {
        "label": "swebench-Modul",
        "ok": swebench_ok,
        "detail": "installiert" if swebench_ok else "fehlt",
    }

    datasets_ok = importlib.util.find_spec("datasets") is not None
    checks["datasets"] = {
        "label": "datasets-Modul",
        "ok": datasets_ok,
        "detail": "installiert" if datasets_ok else "fehlt",
    }

    aider_ok = _cmd_exists("aider")
    checks["aider"] = {
        "label": "aider CLI",
        "ok": aider_ok,
        "detail": shutil.which("aider") if aider_ok else "nicht gefunden",
    }

    api_key = os.environ.get("MINIMAX_API_KEY") or ""
    key_ok = len(api_key) > 10 and api_key.startswith("sk-")
    checks["apikey"] = {
        "label": "MINIMAX_API_KEY",
        "ok": key_ok,
        "detail": f"{len(api_key)} chars" if api_key else "leer",
    }

    litellm_ok = False
    litellm_detail = ""
    try:
        from runner.config import load_config, subprocess_env
        from litellm import completion

        config = load_config()
        env = subprocess_env(config)
        response = completion(
            model=config.aider_model,
            messages=[{"role": "user", "content": "Reply with the single word OK."}],
            temperature=0,
            max_tokens=8,
            timeout=30,
            api_key=env.get("MINIMAX_API_KEY"),
            api_base=env.get("MINIMAX_API_BASE", "https://api.minimax.io/v1"),
        )
        content = (response.choices[0].message.content or "").strip()
        litellm_ok = bool(content)
        litellm_detail = f"Antwort: {content[:50]}" if content else "leere Antwort"
    except Exception as exc:
        litellm_detail = f"{type(exc).__name__}: {str(exc)[:120]}"
    checks["litellm"] = {
        "label": "LiteLLM Completion",
        "ok": litellm_ok,
        "detail": litellm_detail,
    }

    return checks


@app.get("/api/preflight")
async def api_preflight():
    return _preflight_checks()


@app.get("/api/running")
async def api_running():
    with _active_lock:
        if _active_run is None:
            return {"running": False}
        proc = _active_run.get("process")
        if proc is None or proc.poll() is not None:
            return {
                "running": False,
                "run_id": _active_run.get("run_id"),
                "finished": True,
            }
        phase_path = Path(_active_run["artifacts_dir"]) / ".phase"
        phase = (
            phase_path.read_text(encoding="utf-8").strip()
            if phase_path.exists()
            else "unknown"
        )
        return {
            "running": True,
            "run_id": _active_run["run_id"],
            "task_id": _active_run["task_id"],
            "condition": _active_run["condition"],
            "phase": phase,
        }


@app.post("/api/runs")
async def api_launch_run(req: LaunchRequest):
    global _active_run
    with _active_lock:
        if _active_run is not None:
            proc = _active_run.get("process")
            if proc is not None and proc.poll() is None:
                raise HTTPException(
                    409, f"Run already in progress: {_active_run['run_id']}"
                )

    init_db()
    task_id = req.task_id
    condition = req.condition
    iteration = req.iteration
    run_index = req.run_index
    clean_task = task_id.replace("/", "__")
    run_id = f"{condition}_{clean_task}_run{run_index:02d}"
    artifacts_dir = RESULTS_DIR / condition / task_id / run_id
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    conventions_path = req.conventions_path or str(
        HARNESS_DIR / "CONVENTIONS.baseline.md"
    )

    cmd = [
        sys.executable,
        "-m",
        "runner.run_once",
        "--task-id",
        task_id,
        "--condition",
        condition,
        "--iteration",
        str(iteration),
        "--run-index",
        str(run_index),
        "--conventions-path",
        conventions_path,
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    with _active_lock:
        _active_run = {
            "run_id": run_id,
            "task_id": task_id,
            "condition": condition,
            "process": proc,
            "artifacts_dir": str(artifacts_dir),
        }

    def _cleanup():
        proc.wait()
        with _active_lock:
            if _active_run and _active_run.get("run_id") == run_id:
                _active_run["process"] = None

    threading.Thread(target=_cleanup, daemon=True).start()

    return {"run_id": run_id, "status": "starting", "artifacts_dir": str(artifacts_dir)}


@app.post("/api/runs/{run_id}/abort")
async def api_abort_run(run_id: str):
    with _active_lock:
        if _active_run is None or _active_run["run_id"] != run_id:
            raise HTTPException(404, f"No active run with id {run_id}")
        proc = _active_run.get("process")
        if proc is None or proc.poll() is not None:
            raise HTTPException(400, f"Run {run_id} is not running")
        proc.send_signal(signal.SIGTERM)
        return {"status": "terminating", "run_id": run_id}


@app.get("/api/runs/{run_id}/stream")
async def api_run_stream(run_id: str):
    conn = _db()
    try:
        row = conn.execute(
            "SELECT artifacts_dir FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
    finally:
        conn.close()

    if row:
        art_dir = Path(row["artifacts_dir"])
    else:
        with _active_lock:
            if _active_run and _active_run["run_id"] == run_id:
                art_dir = Path(_active_run["artifacts_dir"])
            else:
                raise HTTPException(404, f"Run {run_id} not found")

    stdout_path = art_dir / "agent_stdout.log"
    stderr_path = art_dir / "agent_stderr.log"
    phase_path = art_dir / ".phase"
    patch_path = art_dir / "git_diff.patch"

    async def event_generator():
        last_offset: dict[str, int] = {}
        last_phase = ""
        last_patch_mtime = 0.0
        finished = False

        for _ in range(7200):
            phase = (
                phase_path.read_text(encoding="utf-8").strip()
                if phase_path.exists()
                else ""
            )
            if phase != last_phase:
                yield {"event": "phase", "data": json.dumps({"phase": phase})}
                last_phase = phase
            if phase == "done" or phase == "error":
                finished = True

            for label, fpath in [("aider", stdout_path), ("aider_err", stderr_path)]:
                if fpath.exists():
                    size = fpath.stat().st_size
                    offset = last_offset.get(label, 0)
                    if size > offset:
                        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                            f.seek(offset)
                            new_content = f.read()
                        if new_content:
                            yield {
                                "event": "log",
                                "data": json.dumps(
                                    {"source": label, "content": new_content}
                                ),
                            }
                        last_offset[label] = size

            if patch_path.exists():
                mtime = patch_path.stat().st_mtime
                if mtime > last_patch_mtime:
                    last_patch_mtime = mtime
                    content = patch_path.read_text(encoding="utf-8", errors="replace")
                    lines_added = content.count("\n+") - content.count("\n+++")
                    lines_removed = content.count("\n-") - content.count("\n---")
                    yield {
                        "event": "patch_changed",
                        "data": json.dumps(
                            {
                                "files_changed": content.count("diff --git "),
                                "lines_added": max(0, lines_added),
                                "lines_removed": max(0, lines_removed),
                                "patch": content,
                            }
                        ),
                    }

            if finished:
                yield {"event": "done", "data": json.dumps({"run_id": run_id})}
                break
            await _async_sleep(0.5)

    return EventSourceResponse(event_generator())


async def _async_sleep(seconds: float):
    import asyncio

    await asyncio.sleep(seconds)


@app.delete("/api/runs/{run_id}")
async def api_delete_run(run_id: str):
    conn = _db()
    try:
        row = conn.execute(
            "SELECT artifacts_dir FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, f"Run {run_id} not found")
        conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
        conn.commit()
    finally:
        conn.close()
    return {"status": "deleted", "run_id": run_id}


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def main() -> None:
    parser = argparse.ArgumentParser(description="Harness Dashboard web server")
    parser.add_argument("--port", type=int, default=8420)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    ensure_project_dirs()
    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
