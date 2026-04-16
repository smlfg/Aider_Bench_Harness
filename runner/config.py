from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from runner.paths import PROJECT_ROOT


@dataclass(frozen=True)
class HarnessConfig:
    aider_model: str
    aider_extra_args: tuple[str, ...]
    minimax_api_key: str | None
    minimax_base_url: str | None
    judge_model: str
    judge_command: str | None
    agent_input_usd_per_1m: float
    agent_output_usd_per_1m: float
    judge_input_usd_per_1m: float
    judge_output_usd_per_1m: float


def _float_env(name: str) -> float:
    raw = os.environ.get(name, "0").strip()
    return float(raw) if raw else 0.0


def load_config(env_path: Path | None = None) -> HarnessConfig:
    load_dotenv(env_path or PROJECT_ROOT / ".env")
    extra = os.environ.get("AIDER_EXTRA_ARGS", "--yes-always --no-auto-commits")
    return HarnessConfig(
        aider_model=os.environ.get("AIDER_MODEL", "MiniMax-M2.7-highspeed"),
        aider_extra_args=tuple(shlex.split(extra)),
        minimax_api_key=os.environ.get("MINIMAX_API_KEY") or None,
        minimax_base_url=os.environ.get("MINIMAX_BASE_URL") or None,
        judge_model=os.environ.get("JUDGE_MODEL", "claude-sonnet-4.5"),
        judge_command=os.environ.get("JUDGE_COMMAND") or None,
        agent_input_usd_per_1m=_float_env("AGENT_INPUT_USD_PER_1M"),
        agent_output_usd_per_1m=_float_env("AGENT_OUTPUT_USD_PER_1M"),
        judge_input_usd_per_1m=_float_env("JUDGE_INPUT_USD_PER_1M"),
        judge_output_usd_per_1m=_float_env("JUDGE_OUTPUT_USD_PER_1M"),
    )


def subprocess_env(config: HarnessConfig) -> dict[str, str]:
    env = os.environ.copy()
    if config.minimax_api_key:
        env["MINIMAX_API_KEY"] = config.minimax_api_key
        env.setdefault("OPENAI_API_KEY", config.minimax_api_key)
    if config.minimax_base_url:
        env["MINIMAX_API_BASE"] = config.minimax_base_url
        env["MINIMAX_BASE_URL"] = config.minimax_base_url
        env.setdefault("OPENAI_API_BASE", config.minimax_base_url)
        env.setdefault("OPENAI_BASE_URL", config.minimax_base_url)
    env["JUDGE_MODEL"] = config.judge_model
    return env
