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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from runner.config import load_config
from runner.db import (
    connect,
    delete_run_registry_row,
    fetch_run_registry_row,
    fetch_run_registry_rows,
    init_db,
    upsert_run_registry,
    update_run_registry,
)
from runner.run_once import is_infrastructure_error
from runner.paths import DATA_DIR, HARNESS_DIR, RESULTS_DIR, ensure_project_dirs

app = FastAPI(title="Harness Dashboard")

STATIC_DIR = Path(__file__).resolve().parent / "static"
DB_PATH = RESULTS_DIR / "experiment.db"
MAX_ACTIVE_RUNS = 10
ACTIVE_REGISTRY_STATUSES = {"starting", "running", "judging"}
TERMINAL_REGISTRY_STATUSES = {
    "completed",
    "failed",
    "cancelled",
    "failed_to_start",
    "orphaned",
}

_launch_lock = threading.Lock()
_launch_processes: dict[str, subprocess.Popen[Any]] = {}


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


def _read_phase(artifacts_dir: Path) -> str:
    phase_path = artifacts_dir / ".phase"
    if not phase_path.exists():
        return "starting"
    try:
        return phase_path.read_text(encoding="utf-8").strip() or "starting"
    except Exception:
        return "unknown"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_pid_alive(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _registry_status_is_active(status: str | None) -> bool:
    return status in ACTIVE_REGISTRY_STATUSES


def _registry_row_to_snapshot(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["condition"] = data.get("condition_id")
    data["phase"] = data.get("last_phase") or _read_phase(Path(data["artifacts_dir"]))
    data["source"] = "registry"
    data["active"] = _registry_status_is_active(data.get("status"))
    return data


def _find_run_row(conn: sqlite3.Connection, run_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()


def _resolve_terminal_status(
    *,
    run_row: sqlite3.Row | None,
    run_meta: dict[str, Any] | None,
    phase: str,
    pid_alive: bool,
    had_pid: bool,
) -> str:
    if run_row is not None:
        if int(run_row["task_success"]) == 1 and int(run_row["infrastructure_error"]) == 0:
            return "completed"
        if int(run_row["infrastructure_error"]) == 1:
            return "failed"
        return "failed"
    if run_meta is not None:
        if bool(run_meta.get("task_success")) and not bool(
            run_meta.get("infrastructure_error")
        ):
            return "completed"
        if bool(run_meta.get("infrastructure_error")):
            return "failed"
        return "failed"
    if not had_pid:
        return "failed_to_start"
    if phase in {"done", "error"} and not pid_alive:
        return "failed"
    return "orphaned"


def _reconcile_registry_row_locked(
    conn: sqlite3.Connection, row: sqlite3.Row
) -> dict[str, Any]:
    snapshot = dict(row)
    run_id = row["run_id"]
    artifacts_dir = Path(row["artifacts_dir"])
    phase = _read_phase(artifacts_dir)
    run_meta = _read_json(artifacts_dir / "run_meta.json")
    run_row = _find_run_row(conn, run_id)
    pid = row["pid"]
    pid_alive = _is_pid_alive(pid)
    had_pid = pid is not None
    status = row["status"]
    updated_ts = _utc_now()

    if status in TERMINAL_REGISTRY_STATUSES:
        if phase and phase != row["last_phase"]:
            update_run_registry(
                conn,
                run_id,
                updated_ts=updated_ts,
                last_phase=phase,
            )
        snapshot["last_phase"] = phase or row["last_phase"]
        snapshot["phase"] = snapshot["last_phase"]
        snapshot["source"] = "registry"
        snapshot["active"] = False
        return snapshot

    new_status = status
    if pid_alive:
        if phase == "docker_eval":
            new_status = "judging"
        elif phase == "aider_running":
            new_status = "running"
        elif phase in {"starting", "setup_repo"}:
            new_status = "starting"
        else:
            new_status = status if status in ACTIVE_REGISTRY_STATUSES else "starting"
        update_run_registry(
            conn,
            run_id,
            status=new_status,
            updated_ts=updated_ts,
            last_phase=phase,
        )
        snapshot.update(
            status=new_status,
            updated_ts=updated_ts,
            last_phase=phase,
            phase=phase,
            source="registry",
            active=True,
        )
        return snapshot

    terminal_status = _resolve_terminal_status(
        run_row=run_row,
        run_meta=run_meta,
        phase=phase,
        pid_alive=pid_alive,
        had_pid=had_pid,
    )
    terminal_ts = updated_ts
    update_run_registry(
        conn,
        run_id,
        status=terminal_status,
        updated_ts=updated_ts,
        last_phase=phase,
        terminal_ts=terminal_ts,
    )
    snapshot.update(
        status=terminal_status,
        updated_ts=updated_ts,
        last_phase=phase,
        phase=phase,
        terminal_ts=terminal_ts,
        source="registry",
        active=False,
    )
    return snapshot


def _reconcile_registry_locked(
    conn: sqlite3.Connection,
) -> list[dict[str, Any]]:
    rows = fetch_run_registry_rows(conn)
    snapshots: list[dict[str, Any]] = []
    for row in rows:
        snapshots.append(_reconcile_registry_row_locked(conn, row))
    return snapshots


def _active_registry_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = fetch_run_registry_rows(conn, statuses=tuple(ACTIVE_REGISTRY_STATUSES))
    snapshots = []
    for row in rows:
        snapshot = _registry_row_to_snapshot(_reconcile_registry_row_locked(conn, row))
        if snapshot.get("active"):
            snapshots.append(snapshot)
    return snapshots


def _filesystem_active_runs() -> dict[str, dict[str, Any]]:
    if not RESULTS_DIR.exists():
        return {}
    active: dict[str, dict[str, Any]] = {}
    for phase_file in RESULTS_DIR.rglob(".phase"):
        try:
            phase = phase_file.read_text(encoding="utf-8").strip()
        except Exception:
            continue
        if phase in ("done", "error") or not phase:
            continue
        artifacts_dir = phase_file.parent
        run_id = artifacts_dir.name
        if len(artifacts_dir.parents) < 2:
            continue
        task_dir = artifacts_dir.parent
        condition_dir = task_dir.parent
        active[run_id] = {
            "run_id": run_id,
            "task_id": task_dir.name,
            "condition_id": condition_dir.name,
            "condition": condition_dir.name,
            "iteration": None,
            "phase": phase,
            "artifacts_dir": str(artifacts_dir),
            "source": "filesystem",
        }
    return active


def _active_runs_payload() -> dict[str, Any]:
    with _launch_lock:
        with _db() as conn:
            active_runs = _active_registry_rows(conn)
    active_list = sorted(
        active_runs,
        key=lambda r: (r.get("start_ts") or "", r.get("run_id") or ""),
        reverse=True,
    )
    payload: dict[str, Any] = {
        "running": bool(active_list),
        "active_count": len(active_list),
        "active_run_count": len(active_list),
        "limit": MAX_ACTIVE_RUNS,
        "max_active_runs": MAX_ACTIVE_RUNS,
        "active_runs": active_list,
    }
    if active_list:
        first = active_list[0]
        payload.update(
            {
                "run_id": first["run_id"],
                "task_id": first.get("task_id"),
                "condition": first.get("condition"),
                "phase": first.get("phase"),
            }
        )
    return payload


def _find_artifacts_dir_for_run(run_id: str) -> Path | None:
    with _launch_lock:
        conn = _db()
        try:
            row = conn.execute(
                "SELECT artifacts_dir FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if row:
                return Path(row["artifacts_dir"])
            reg = fetch_run_registry_row(conn, run_id)
            if reg:
                return Path(reg["artifacts_dir"])
        finally:
            conn.close()
    for entry in _filesystem_active_runs().values():
        if entry["run_id"] == run_id:
            return Path(entry["artifacts_dir"])
    return None


def _reconcile_registry() -> None:
    with _launch_lock:
        with _db() as conn:
            _reconcile_registry_locked(conn)


@app.on_event("startup")
async def _startup_reconcile() -> None:
    init_db()
    _reconcile_registry()
    threading.Thread(target=_background_reconcile, daemon=True).start()


def _background_reconcile() -> None:
    while True:
        time.sleep(10)
        try:
            _reconcile_registry()
        except Exception:
            pass


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
    with _launch_lock:
        with _db() as conn:
            row = conn.execute(
                "SELECT r.*, c.content AS conventions_content, "
                "c.parent_hash AS conventions_parent_hash, "
                "c.mutation_note AS conventions_mutation_note "
                "FROM runs r LEFT JOIN conventions c ON r.conventions_hash = c.conventions_hash "
                "WHERE r.run_id = ?",
                (run_id,),
            ).fetchone()
            registry_row = fetch_run_registry_row(conn, run_id)
            if not row and not registry_row:
                raise HTTPException(404, f"Run {run_id} not found")
            result = dict(row) if row else {}
            if registry_row:
                registry = _registry_row_to_snapshot(
                    _reconcile_registry_row_locked(conn, registry_row)
                )
                result.setdefault("run_id", registry["run_id"])
                result.setdefault("task_id", registry["task_id"])
                result.setdefault("condition_id", registry["condition_id"])
                result.setdefault("iteration", registry["iteration"])
                result.setdefault("artifacts_dir", registry["artifacts_dir"])
                result.setdefault("conventions_path", registry["conventions_path"])
                result.setdefault("model_name", registry["model_name"])
                result.setdefault("start_ts", registry["start_ts"])
                result.setdefault("phase", registry.get("phase"))
                result.setdefault("status", registry.get("status"))
                result.setdefault("active", registry.get("active"))
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
                judge_path = art_dir / "judge_result.json"
                if judge_path.exists():
                    try:
                        result["judge_result"] = json.loads(
                            judge_path.read_text(encoding="utf-8")
                        )
                    except Exception:
                        result["judge_result_error"] = "Unable to parse judge_result.json"
                phase_path = art_dir / ".phase"
                if phase_path.exists():
                    result["phase"] = phase_path.read_text(encoding="utf-8").strip()
            return result


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
    with _launch_lock:
        with _db() as conn:
            registry_rows = [
                r
                for r in _active_registry_rows(conn)
                if _registry_status_is_active(r.get("status"))
            ]
            run_rows = conn.execute(
                "SELECT run_id, task_id, condition_id, iteration, task_success, "
                "tests_passed, tests_total, duration_seconds, start_ts, end_ts, "
                "files_changed, lines_added, lines_removed, judge_score, artifacts_dir, "
                "infrastructure_error, failure_kind, error_detail "
                "FROM runs ORDER BY start_ts DESC LIMIT 20"
            ).fetchall()
            merged: dict[str, dict[str, Any]] = {
                row["run_id"]: dict(row) for row in run_rows
            }
            for row in registry_rows:
                merged[row["run_id"]] = row
            ordered = sorted(
                merged.values(),
                key=lambda r: (r.get("start_ts") or "", r.get("run_id") or ""),
                reverse=True,
            )
            return ordered[:20]


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
    art_dir = _find_artifacts_dir_for_run(run_id)
    if art_dir is None:
        raise HTTPException(404, f"Run {run_id} not found")
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
    art_dir = _find_artifacts_dir_for_run(run_id)
    if art_dir is None:
        raise HTTPException(404, f"Run {run_id} not found")
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
    return _active_runs_payload()


@app.get("/api/runs/active")
async def api_active_runs():
    return _active_runs_payload()


@app.post("/api/runs")
async def api_launch_run(req: LaunchRequest):
    init_db()
    config = load_config()
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

    now = _utc_now()
    with _launch_lock:
        with _db() as conn:
            active_rows = _active_registry_rows(conn)
            active_map = {row["run_id"]: row for row in active_rows}
            if run_id in active_map:
                raise HTTPException(409, f"Run already in progress: {run_id}")
            if len(active_map) >= MAX_ACTIVE_RUNS:
                raise HTTPException(
                    409,
                    {
                        "error": "active_run_cap_reached",
                        "message": f"Maximum of {MAX_ACTIVE_RUNS} active runs reached",
                        "active_run_count": len(active_map),
                        "max_active_runs": MAX_ACTIVE_RUNS,
                    },
                )
            upsert_run_registry(
                conn,
                {
                    "run_id": run_id,
                    "task_id": task_id,
                    "condition_id": condition,
                    "iteration": iteration,
                    "model_name": config.aider_model,
                    "conventions_path": conventions_path,
                    "status": "starting",
                    "pid": None,
                    "artifacts_dir": str(artifacts_dir),
                    "start_ts": now,
                    "updated_ts": now,
                    "last_phase": "starting",
                    "error_detail": None,
                    "terminal_ts": None,
                },
            )

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        with _launch_lock:
            with _db() as conn:
                update_run_registry(
                    conn,
                    run_id,
                    status="failed_to_start",
                    updated_ts=_utc_now(),
                    terminal_ts=_utc_now(),
                )
        raise

    with _launch_lock:
        _launch_processes[run_id] = proc
        with _db() as conn:
            update_run_registry(
                conn,
                run_id,
                pid=proc.pid,
                status="running",
                updated_ts=_utc_now(),
                last_phase="starting",
                error_detail=None,
            )

    def _cleanup():
        proc.wait()
        with _launch_lock:
            _launch_processes.pop(run_id, None)
            with _db() as conn:
                row = fetch_run_registry_row(conn, run_id)
                if row is None:
                    return
                reconciled = _reconcile_registry_row_locked(conn, row)
                if reconciled.get("status") in ACTIVE_REGISTRY_STATUSES:
                    meta = _read_json(artifacts_dir / "run_meta.json")
                    if meta is not None:
                        terminal = _resolve_terminal_status(
                            run_row=_find_run_row(conn, run_id),
                            run_meta=meta,
                            phase=_read_phase(artifacts_dir),
                            pid_alive=False,
                            had_pid=True,
                        )
                    else:
                        terminal = "failed"
                    update_run_registry(
                        conn,
                        run_id,
                        status=terminal,
                        updated_ts=_utc_now(),
                        terminal_ts=_utc_now(),
                        last_phase=_read_phase(artifacts_dir),
                    )

    threading.Thread(target=_cleanup, daemon=True).start()

    return {
        "run_id": run_id,
        "status": "starting",
        "artifacts_dir": str(artifacts_dir),
        "active_run_count": len(_active_runs_payload()["active_runs"]),
        "max_active_runs": MAX_ACTIVE_RUNS,
    }


@app.post("/api/runs/{run_id}/abort")
async def api_abort_run(run_id: str):
    with _launch_lock:
        with _db() as conn:
            row = fetch_run_registry_row(conn, run_id)
            if row is None or not _registry_status_is_active(row["status"]):
                raise HTTPException(404, f"No active run with id {run_id}")
            proc = _launch_processes.get(run_id)
            pid = row["pid"]
            if proc is not None and proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
            elif pid is not None and _is_pid_alive(pid):
                os.kill(pid, signal.SIGTERM)
            else:
                raise HTTPException(400, f"Run {run_id} is not running")
            update_run_registry(
                conn,
                run_id,
                status="cancelled",
                updated_ts=_utc_now(),
                terminal_ts=_utc_now(),
            )
            return {"status": "terminating", "run_id": run_id}


@app.get("/api/runs/{run_id}/stream")
async def api_run_stream(run_id: str):
    art_dir = _find_artifacts_dir_for_run(run_id)
    if art_dir is None:
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
    with _db() as conn:
        row = conn.execute(
            "SELECT artifacts_dir FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row:
            conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
        delete_run_registry_row(conn, run_id)
        conn.commit()
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
