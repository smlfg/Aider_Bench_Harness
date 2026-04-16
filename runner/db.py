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
  artifacts_dir TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conventions (
  conventions_hash TEXT PRIMARY KEY,
  content TEXT NOT NULL,
  parent_hash TEXT,
  mutation_note TEXT
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
        _ensure_column(conn, "runs", "error_detail", "TEXT")
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
