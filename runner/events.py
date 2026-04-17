from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RunContext:
    run_id: str
    condition_id: str
    task_id: str
    iteration: int
    run_index: int


class EventLogger:
    def __init__(self, path: Path, context: RunContext) -> None:
        self.path = path
        self.context = context
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(
        self,
        *,
        phase: str,
        event: str,
        status: str = "ok",
        failure_reason: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "ts": _ts(),
            "run_id": self.context.run_id,
            "condition_id": self.context.condition_id,
            "task_id": self.context.task_id,
            "iteration": self.context.iteration,
            "run_index": self.context.run_index,
            "phase": phase,
            "event": event,
            "status": status,
            "failure_reason": failure_reason,
            "details": details or {},
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
