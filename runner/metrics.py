from __future__ import annotations

import json
from pathlib import Path
from typing import Any


EMPTY_TESTS = {
    "FAIL_TO_PASS": {"total": 0, "passed": 0, "failed": []},
    "PASS_TO_PASS": {"total": 0, "passed": 0, "failed": []},
}


def summarize_tests_status(tests_status: dict[str, Any] | None) -> dict[str, Any]:
    if not tests_status:
        return json.loads(json.dumps(EMPTY_TESTS))
    result: dict[str, Any] = {}
    for key in ("FAIL_TO_PASS", "PASS_TO_PASS"):
        section = tests_status.get(key, {})
        success = list(section.get("success", []))
        failure = list(section.get("failure", []))
        result[key] = {
            "total": len(success) + len(failure),
            "passed": len(success),
            "failed": failure,
        }
    return result


def totals_from_tests_json(tests: dict[str, Any]) -> tuple[int, int, int]:
    total = 0
    passed = 0
    for key in ("FAIL_TO_PASS", "PASS_TO_PASS"):
        total += int(tests.get(key, {}).get("total", 0))
        passed += int(tests.get(key, {}).get("passed", 0))
    success = int(total > 0 and passed == total)
    return total, passed, success


def load_report(report_path: Path, instance_id: str) -> dict[str, Any] | None:
    if not report_path.exists():
        return None
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return report.get(instance_id)


def tests_json_from_report(report_entry: dict[str, Any] | None) -> dict[str, Any]:
    if not report_entry:
        return json.loads(json.dumps(EMPTY_TESTS))
    return summarize_tests_status(report_entry.get("tests_status"))


def diff_stats(patch: str) -> tuple[int, int, int]:
    files: set[str] = set()
    added = 0
    removed = 0
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                files.add(parts[2][2:] if parts[2].startswith("a/") else parts[2])
        elif line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return len(files), added, removed


def changed_files_from_patch(patch: str) -> list[str]:
    files = []
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                path = parts[2][2:] if parts[2].startswith("a/") else parts[2]
                files.append(path)
    return files


def unrelated_edits_present(patch: str, expected_dirs: list[str] | None = None) -> bool:
    """
    Detect if patch contains edits outside expected directories.

    Args:
        patch: The git diff patch
        expected_dirs: List of directory prefixes that are allowed.
                      If None, only CONVENTIONS.md is allowed as unrelated.
    """
    if not patch.strip():
        return False

    changed = changed_files_from_patch(patch)
    if not expected_dirs:
        return False

    for path in changed:
        if path == "CONVENTIONS.md":
            continue
        normalized = path.lstrip("/")
        if not any(
            normalized.startswith(d.lstrip("/")) or d == "*" for d in expected_dirs
        ):
            return True
    return False
