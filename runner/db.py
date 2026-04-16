from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any

from runner.paths import DB_PATH, ensure_project_dirs


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  condition_id TEXT NOT NULL,
  iteration INTEGER NOT NULL,
  model_name TEXT NOT NULL,
  conventions_hash TEXT NOT NULL,
  conventions_path TEXT NOT NULL,
  start_ts TEXT NOT NULL,
  end_ts TEXT NOT NULL,
  duration_seconds REAL NOT NULL,
  exit_code INTEGER NOT NULL,
  infrastructure_error INTEGER NOT NULL DEFAULT 0,
  failure_kind TEXT NOT NULL DEFAULT 'unknown',
  tokens_in INTEGER,
  tokens_out INTEGER,
  cost_estimate REAL,
  tests_total INTEGER NOT NULL,
  tests_passed INTEGER NOT NULL,
  task_success INTEGER NOT NULL,
  files_changed INTEGER NOT NULL,
  lines_added INTEGER NOT NULL,
  lines_removed INTEGER NOT NULL,
  judge_score REAL,
  judge_model TEXT,
  judge_prompt_version TEXT,
  judge_scope_adherence INTEGER,
  judge_minimality INTEGER,
  judge_diff_clarity INTEGER,
  judge_verdict TEXT,
  judge_conclusion TEXT,
  judge_rationale TEXT,
  judge_tokens_in INTEGER,
  judge_tokens_out INTEGER,
  judge_cost_estimate REAL,
  judge_result_json TEXT,
  artifacts_dir TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conventions (
  conventions_hash TEXT PRIMARY KEY,
  content TEXT NOT NULL,
  parent_hash TEXT,
  mutation_note TEXT
);

CREATE TABLE IF NOT EXISTS run_registry (
  run_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  condition_id TEXT NOT NULL,
  iteration INTEGER NOT NULL,
  model_name TEXT NOT NULL,
  conventions_path TEXT NOT NULL,
  status TEXT NOT NULL,
  pid INTEGER,
  artifacts_dir TEXT NOT NULL,
  start_ts TEXT NOT NULL,
  updated_ts TEXT NOT NULL,
  last_phase TEXT,
  error_detail TEXT,
  terminal_ts TEXT
);

CREATE TABLE IF NOT EXISTS calibration_runs (
  calibration_run_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  round INTEGER NOT NULL,
  run_index INTEGER NOT NULL,
  model_name TEXT NOT NULL,
  conventions_hash TEXT NOT NULL,
  start_ts TEXT NOT NULL,
  end_ts TEXT NOT NULL,
  duration_seconds REAL NOT NULL,
  exit_code INTEGER NOT NULL,
  infrastructure_error INTEGER NOT NULL DEFAULT 0,
  failure_kind TEXT NOT NULL DEFAULT 'unknown',
  tests_total INTEGER NOT NULL,
  tests_passed INTEGER NOT NULL,
  task_success INTEGER NOT NULL,
  artifacts_dir TEXT NOT NULL
);
"""


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    ensure_project_dirs()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        _ensure_column(
            conn, "runs", "infrastructure_error", "INTEGER NOT NULL DEFAULT 0"
        )
        _ensure_column(conn, "runs", "failure_kind", "TEXT NOT NULL DEFAULT 'unknown'")
        _ensure_column(
            conn,
            "calibration_runs",
            "infrastructure_error",
            "INTEGER NOT NULL DEFAULT 0",
        )
        _ensure_column(
            conn,
            "calibration_runs",
            "failure_kind",
            "TEXT NOT NULL DEFAULT 'unknown'",
        )
        _ensure_column(conn, "run_registry", "status", "TEXT NOT NULL DEFAULT 'starting'")
        _ensure_column(conn, "run_registry", "pid", "INTEGER")
        _ensure_column(conn, "run_registry", "artifacts_dir", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "run_registry", "start_ts", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "run_registry", "updated_ts", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "run_registry", "model_name", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(
            conn, "run_registry", "conventions_path", "TEXT NOT NULL DEFAULT ''"
        )
        _ensure_column(conn, "run_registry", "last_phase", "TEXT")
        _ensure_column(conn, "run_registry", "error_detail", "TEXT")
        _ensure_column(conn, "run_registry", "terminal_ts", "TEXT")
        _ensure_column(conn, "runs", "error_detail", "TEXT")
        _ensure_column(conn, "runs", "judge_model", "TEXT")
        _ensure_column(conn, "runs", "judge_prompt_version", "TEXT")
        _ensure_column(conn, "runs", "judge_scope_adherence", "INTEGER")
        _ensure_column(conn, "runs", "judge_minimality", "INTEGER")
        _ensure_column(conn, "runs", "judge_diff_clarity", "INTEGER")
        _ensure_column(conn, "runs", "judge_verdict", "TEXT")
        _ensure_column(conn, "runs", "judge_conclusion", "TEXT")
        _ensure_column(conn, "runs", "judge_rationale", "TEXT")
        _ensure_column(conn, "runs", "judge_tokens_in", "INTEGER")
        _ensure_column(conn, "runs", "judge_tokens_out", "INTEGER")
        _ensure_column(conn, "runs", "judge_cost_estimate", "REAL")
        _ensure_column(conn, "runs", "judge_result_json", "TEXT")
        _ensure_column(conn, "calibration_runs", "error_detail", "TEXT")


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    existing = conn.execute(f"PRAGMA table_info({table})").fetchall()
    if any(row[1] == column for row in existing):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return content_hash(path.read_text(encoding="utf-8"))


def upsert_conventions(
    conn: sqlite3.Connection,
    path: Path,
    *,
    parent_hash: str | None = None,
    mutation_note: str | None = None,
) -> str:
    content = path.read_text(encoding="utf-8")
    digest = content_hash(content)
    conn.execute(
        """
        INSERT INTO conventions (conventions_hash, content, parent_hash, mutation_note)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(conventions_hash) DO UPDATE SET
          content = excluded.content,
          parent_hash = COALESCE(excluded.parent_hash, conventions.parent_hash),
          mutation_note = COALESCE(excluded.mutation_note, conventions.mutation_note)
        """,
        (digest, content, parent_hash, mutation_note),
    )
    return digest


def insert_run(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    cols = [
        "run_id",
        "task_id",
        "condition_id",
        "iteration",
        "model_name",
        "conventions_hash",
        "conventions_path",
        "start_ts",
        "end_ts",
        "duration_seconds",
        "exit_code",
        "infrastructure_error",
        "error_detail",
        "failure_kind",
        "tokens_in",
        "tokens_out",
        "cost_estimate",
        "tests_total",
        "tests_passed",
        "task_success",
        "files_changed",
        "lines_added",
        "lines_removed",
        "judge_score",
        "judge_model",
        "judge_prompt_version",
        "judge_scope_adherence",
        "judge_minimality",
        "judge_diff_clarity",
        "judge_verdict",
        "judge_conclusion",
        "judge_rationale",
        "judge_tokens_in",
        "judge_tokens_out",
        "judge_cost_estimate",
        "judge_result_json",
        "artifacts_dir",
    ]
    conn.execute(
        f"INSERT OR REPLACE INTO runs ({', '.join(cols)}) "
        f"VALUES ({', '.join('?' for _ in cols)})",
        [row.get(col) for col in cols],
    )


def insert_calibration_run(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    cols = [
        "calibration_run_id",
        "task_id",
        "round",
        "run_index",
        "model_name",
        "conventions_hash",
        "start_ts",
        "end_ts",
        "duration_seconds",
        "exit_code",
        "infrastructure_error",
        "error_detail",
        "failure_kind",
        "tests_total",
        "tests_passed",
        "task_success",
        "artifacts_dir",
    ]
    conn.execute(
        f"INSERT OR REPLACE INTO calibration_runs ({', '.join(cols)}) "
        f"VALUES ({', '.join('?' for _ in cols)})",
        [row.get(col) for col in cols],
    )


def upsert_run_registry(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    cols = [
        "run_id",
        "task_id",
        "condition_id",
        "iteration",
        "model_name",
        "conventions_path",
        "status",
        "pid",
        "artifacts_dir",
        "start_ts",
        "updated_ts",
        "last_phase",
        "error_detail",
        "terminal_ts",
    ]
    conn.execute(
        f"INSERT INTO run_registry ({', '.join(cols)}) "
        f"VALUES ({', '.join('?' for _ in cols)}) "
        "ON CONFLICT(run_id) DO UPDATE SET "
        "task_id=excluded.task_id, "
        "condition_id=excluded.condition_id, "
        "iteration=excluded.iteration, "
        "model_name=excluded.model_name, "
        "conventions_path=excluded.conventions_path, "
        "status=excluded.status, "
        "pid=excluded.pid, "
        "artifacts_dir=excluded.artifacts_dir, "
        "start_ts=excluded.start_ts, "
        "updated_ts=excluded.updated_ts, "
        "last_phase=excluded.last_phase, "
        "error_detail=excluded.error_detail, "
        "terminal_ts=excluded.terminal_ts",
        [row.get(col) for col in cols],
    )


def update_run_registry(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    status: str | None = None,
    pid: int | None = None,
    updated_ts: str | None = None,
    last_phase: str | None = None,
    error_detail: str | None = None,
    terminal_ts: str | None = None,
) -> None:
    assignments = []
    params: list[Any] = []
    if status is not None:
        assignments.append("status = ?")
        params.append(status)
    if pid is not None:
        assignments.append("pid = ?")
        params.append(pid)
    if updated_ts is not None:
        assignments.append("updated_ts = ?")
        params.append(updated_ts)
    if last_phase is not None:
        assignments.append("last_phase = ?")
        params.append(last_phase)
    if error_detail is not None:
        assignments.append("error_detail = ?")
        params.append(error_detail)
    if terminal_ts is not None:
        assignments.append("terminal_ts = ?")
        params.append(terminal_ts)
    if not assignments:
        return
    params.append(run_id)
    conn.execute(
        f"UPDATE run_registry SET {', '.join(assignments)} WHERE run_id = ?",
        params,
    )


def fetch_run_registry_rows(
    conn: sqlite3.Connection, *, statuses: tuple[str, ...] | None = None
) -> list[sqlite3.Row]:
    query = "SELECT * FROM run_registry"
    params: list[Any] = []
    if statuses:
        query += " WHERE status IN (%s)" % ", ".join("?" for _ in statuses)
        params.extend(statuses)
    query += " ORDER BY start_ts"
    return conn.execute(query, params).fetchall()


def fetch_run_registry_row(conn: sqlite3.Connection, run_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM run_registry WHERE run_id = ?", (run_id,)).fetchone()


def delete_run_registry_row(conn: sqlite3.Connection, run_id: str) -> None:
    conn.execute("DELETE FROM run_registry WHERE run_id = ?", (run_id,))
