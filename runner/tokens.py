from __future__ import annotations

import re

from runner.config import HarnessConfig


INT = r"([0-9][0-9,._]*)"
AIDER_INT = r"([0-9][0-9,._]*[kKmM]?)"
PATTERNS = [
    (re.compile(rf"input[_ ]tokens[\"':= ]+{INT}", re.I), "in"),
    (re.compile(rf"prompt[_ ]tokens[\"':= ]+{INT}", re.I), "in"),
    (re.compile(rf"tokens[_ ]in[\"':= ]+{INT}", re.I), "in"),
    (re.compile(rf"output[_ ]tokens[\"':= ]+{INT}", re.I), "out"),
    (re.compile(rf"completion[_ ]tokens[\"':= ]+{INT}", re.I), "out"),
    (re.compile(rf"tokens[_ ]out[\"':= ]+{INT}", re.I), "out"),
    (re.compile(rf"{INT}\s+tokens?\s+sent", re.I), "in"),
    (re.compile(rf"{INT}\s+tokens?\s+received", re.I), "out"),
    # Aider format: "Tokens: 2.0k sent, 337 received."
    (re.compile(rf"Tokens:\s*{AIDER_INT}\s+sent,\s*{AIDER_INT}\s+received", re.I), "aider"),
]


def _parse_int(raw: str) -> int:
    return int(raw.replace(",", "").replace("_", "").replace(".", ""))


def _parse_token_val(raw: str) -> int:
    """Parse token values like '2.0k', '163k', '337' into int."""
    raw = raw.strip().lower()
    if raw.endswith("k"):
        return int(float(raw[:-1]) * 1000)
    if raw.endswith("m"):
        return int(float(raw[:-1]) * 1_000_000)
    return int(raw)


def extract_token_counts(text: str) -> tuple[int | None, int | None]:
    tokens_in: int | None = None
    tokens_out: int | None = None
    aider_in: list[int] = []
    aider_out: list[int] = []
    for pattern, direction in PATTERNS:
        if direction == "aider":
            for m in pattern.finditer(text):
                raw_in = m.group(1)
                raw_out = m.group(2)
                if raw_in and raw_out:
                    try:
                        aider_in.append(_parse_token_val(raw_in))
                        aider_out.append(_parse_token_val(raw_out))
                    except ValueError:
                        pass
            continue
        matches = [_parse_int(match.group(1)) for match in pattern.finditer(text)]
        if not matches:
            continue
        if direction == "in":
            tokens_in = max(matches) if tokens_in is None else max(tokens_in, max(matches))
        else:
            tokens_out = max(matches) if tokens_out is None else max(tokens_out, max(matches))
    # Add Aider cumulative totals
    if aider_in:
        tokens_in = max(aider_in) if tokens_in is None else max(tokens_in, max(aider_in))
    if aider_out:
        tokens_out = max(aider_out) if tokens_out is None else max(tokens_out, max(aider_out))
    return tokens_in, tokens_out


def estimate_agent_cost(
    tokens_in: int | None,
    tokens_out: int | None,
    config: HarnessConfig,
) -> float | None:
    if tokens_in is None and tokens_out is None:
        return None
    input_cost = ((tokens_in or 0) / 1_000_000) * config.agent_input_usd_per_1m
    output_cost = ((tokens_out or 0) / 1_000_000) * config.agent_output_usd_per_1m
    return input_cost + output_cost


def estimate_judge_cost(
    tokens_in: int | None,
    tokens_out: int | None,
    config: HarnessConfig,
) -> float | None:
    if tokens_in is None and tokens_out is None:
        return None
    input_cost = ((tokens_in or 0) / 1_000_000) * config.judge_input_usd_per_1m
    output_cost = ((tokens_out or 0) / 1_000_000) * config.judge_output_usd_per_1m
    return input_cost + output_cost


def count_api_calls(text: str) -> int:
    """Count how many API calls Aider made."""
    return len(re.findall(r"Tokens:\s*[\d.]+[kKmM]?\s+sent,\s*[\d.]+[kKmM]?\s+received", text, re.I))
