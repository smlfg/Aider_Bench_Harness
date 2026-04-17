from __future__ import annotations

from enum import StrEnum


class FailureReason(StrEnum):
    # setup
    REPO_CLONE_ERROR = "repo_clone_error"
    REPO_CHECKOUT_ERROR = "repo_checkout_error"
    REPO_PATCH_ERROR = "repo_patch_error"

    # agent
    AGENT_IMPORT_ERROR = "agent_import_error"
    AGENT_TIMEOUT = "agent_timeout"
    AGENT_EXIT_NONZERO = "agent_exit_nonzero"

    # eval
    EVAL_CONTAINER_NAME_CONFLICT = "eval_container_name_conflict"
    EVAL_IMAGE_BUILD_ERROR = "eval_image_build_error"
    EVAL_TIMEOUT = "eval_timeout"
    EVAL_REPORT_MISSING = "eval_report_missing"
    EVAL_PARSE_ERROR = "eval_parse_error"
    EVAL_CONTAINER_CLEANUP_ERROR = "eval_container_cleanup_error"

    # outcome
    TASK_FAILURE = "task_failure"
    SUCCESS = "success"


def derive_status(reason: FailureReason) -> str:
    if reason == FailureReason.SUCCESS:
        return "success"
    if reason == FailureReason.TASK_FAILURE:
        return "failed"
    return "infra_failed"


def enforce_task_failure_guard(
    reason: FailureReason,
    *,
    tests_total: int,
    fallback: FailureReason = FailureReason.EVAL_REPORT_MISSING,
) -> FailureReason:
    """Prevent task_failure when no tests were actually observed."""
    if reason == FailureReason.TASK_FAILURE and tests_total == 0:
        return fallback
    return reason


def infer_eval_failure_reason(stdout: str, stderr: str, returncode: int) -> FailureReason:
    text = f"{stdout}\n{stderr}".lower()
    if "409 client error" in text and "container name" in text:
        return FailureReason.EVAL_CONTAINER_NAME_CONFLICT
    if "buildimageerror" in text or "error building image" in text:
        return FailureReason.EVAL_IMAGE_BUILD_ERROR
    if "timeout" in text or returncode in {-9, -15}:
        return FailureReason.EVAL_TIMEOUT
    return FailureReason.EVAL_PARSE_ERROR


def infer_agent_failure_reason(stdout: str, stderr: str, returncode: int) -> FailureReason:
    text = f"{stdout}\n{stderr}".lower()
    if "cannot import name __version__ from aider" in text or "importerror" in text:
        return FailureReason.AGENT_IMPORT_ERROR
    if "timeout" in text or returncode in {-9, -15}:
        return FailureReason.AGENT_TIMEOUT
    return FailureReason.AGENT_EXIT_NONZERO
