from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from runner.config import load_config, subprocess_env


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def completion_test(model: str) -> tuple[bool, str]:
    config = load_config()
    os.environ.update(subprocess_env(config))
    try:
        from litellm import completion
    except Exception as exc:  # pragma: no cover - dependency failure path
        return False, f"litellm import failed: {exc}"

    try:
        response = completion(
            model=model,
            messages=[{"role": "user", "content": "Reply with the single word OK."}],
            temperature=0,
            max_tokens=8,
            timeout=30,
        )
        content = response.choices[0].message.content if response.choices else ""
        text = (content or "").strip()
        if not text:
            return False, "empty completion response"
        return True, text
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def docker_hello_world() -> bool:
    proc = _run(["docker", "run", "hello-world"], timeout=180)
    print(f"docker run hello-world: {proc.returncode == 0}")
    if proc.returncode != 0:
        print(proc.stderr.strip())
    return proc.returncode == 0


def aider_echo_test(model: str) -> bool:
    config = load_config()
    with tempfile.TemporaryDirectory(prefix="aider-minimax-preflight-") as tmp:
        repo = Path(tmp)
        _run(["git", "init"], cwd=repo)
        (repo / "README.md").write_text("echo test\n", encoding="utf-8")
        (repo / "CONVENTIONS.md").write_text(
            "Reply briefly. Do not make code changes for echo tests.\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [
                "aider",
                "--model",
                model,
                "--yes-always",
                "--no-auto-commits",
                "--read",
                "CONVENTIONS.md",
                "--message",
                "echo test",
            ],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=subprocess_env(config),
            timeout=60,
            check=False,
        )
    print(f"aider echo test ({model}): {proc.returncode == 0}")
    if proc.returncode != 0:
        print((proc.stderr or proc.stdout).strip()[-1200:])
    return proc.returncode == 0


def aider_model_candidates(primary: str) -> list[str]:
    config = load_config()
    candidates = [primary]
    if config.minimax_base_url and not primary.startswith("openai/"):
        candidates.append(f"openai/{primary}")
    if config.minimax_base_url and primary.startswith("openai/"):
        candidates.append(primary.removeprefix("openai/"))
    candidates.extend(
        [
            "minimax/MiniMax-M2.7-highspeed",
            "minimax/MiniMax-M2.7",
            "minimax/MiniMax-M2.5",
            "MiniMax-M2.7",
        ]
    )
    return list(dict.fromkeys(candidates))


def main() -> None:
    parser = argparse.ArgumentParser(description="Preflight host/tooling for the experiment.")
    parser.add_argument("--skip-docker-run", action="store_true")
    parser.add_argument("--skip-aider-echo", action="store_true")
    parser.add_argument("--aider-model", default=load_config().aider_model)
    args = parser.parse_args()

    checks = {
        "python": sys.version.split()[0],
        "uv": shutil.which("uv") or "missing",
        "git": shutil.which("git") or "missing",
        "docker": shutil.which("docker") or "missing",
        "aider": shutil.which("aider") or "missing",
        "sqlite3": shutil.which("sqlite3") or "missing",
        "datasets module": str(_has_module("datasets")),
        "swebench module": str(_has_module("swebench")),
    }
    for key, value in checks.items():
        print(f"{key}: {value}")
    failed = False
    for key in ("uv", "git", "docker", "aider", "sqlite3"):
        if checks[key] == "missing":
            failed = True
    for key in ("datasets module", "swebench module"):
        if checks[key] != "True":
            failed = True
    if shutil.which("docker"):
        proc = _run(["docker", "ps"])
        print(f"docker daemon reachable: {proc.returncode == 0}")
        if proc.returncode != 0:
            print(proc.stderr.strip())
            failed = True
        elif not args.skip_docker_run:
            failed = not docker_hello_world() or failed
    if not args.skip_aider_echo:
        completion_ok = False
        for model in aider_model_candidates(args.aider_model):
            ok, detail = completion_test(model)
            print(f"completion test ({model}): {ok}")
            if not ok:
                print(detail)
                continue
            completion_ok = True
            break
        failed = failed or not completion_ok
        if shutil.which("aider"):
            aider_ok = False
            for model in aider_model_candidates(args.aider_model):
                if aider_echo_test(model):
                    aider_ok = True
                    break
            failed = failed or not aider_ok
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
