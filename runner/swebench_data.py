from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runner.paths import DEFAULT_CANDIDATES_PATH, ensure_project_dirs

DATASET_NAME = "princeton-nlp/SWE-bench_Lite"
DEFAULT_SPLIT = "test"


def _json_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return json.loads(value)
    return list(value)


def normalize_instance(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "instance_id": raw["instance_id"],
        "task_id": raw["instance_id"],
        "repo": raw["repo"],
        "base_commit": raw["base_commit"],
        "problem_statement": raw["problem_statement"],
        "test_patch": raw.get("test_patch", ""),
        "environment_setup_commit": raw.get("environment_setup_commit"),
        "FAIL_TO_PASS": _json_list(raw.get("FAIL_TO_PASS")),
        "PASS_TO_PASS": _json_list(raw.get("PASS_TO_PASS")),
        "version": raw.get("version"),
    }


def load_dataset_instances(
    *,
    dataset_name: str = DATASET_NAME,
    split: str = DEFAULT_SPLIT,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: datasets. Run `uv sync` before fetching SWE-bench Lite."
        ) from exc
    dataset = load_dataset(dataset_name, split=split)
    rows = [normalize_instance(dict(row)) for row in dataset]
    return rows[:limit] if limit else rows


def write_candidates(
    output: Path = DEFAULT_CANDIDATES_PATH,
    *,
    dataset_name: str = DATASET_NAME,
    split: str = DEFAULT_SPLIT,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    ensure_project_dirs()
    rows = load_dataset_instances(dataset_name=dataset_name, split=split, limit=limit)
    output.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return rows


def load_task_file(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_task(task_id: str, task_file: Path | None) -> dict[str, Any]:
    if task_file and task_file.exists():
        for row in load_task_file(task_file):
            if row.get("task_id") == task_id or row.get("instance_id") == task_id:
                return row
    for row in load_dataset_instances():
        if row["instance_id"] == task_id:
            return row
    raise SystemExit(f"Task not found: {task_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch SWE-bench Lite candidates.")
    parser.add_argument("--output", type=Path, default=DEFAULT_CANDIDATES_PATH)
    parser.add_argument("--dataset-name", default=DATASET_NAME)
    parser.add_argument("--split", default=DEFAULT_SPLIT)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    rows = write_candidates(
        args.output,
        dataset_name=args.dataset_name,
        split=args.split,
        limit=args.limit,
    )
    print(f"Wrote {len(rows)} candidates to {args.output}")


if __name__ == "__main__":
    main()

