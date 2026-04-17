#!/usr/bin/env python3
"""
overnight_swe.py

Runs SWE-bench harness experiments overnight.
Cyles through conditions × tasks, using skip-eval for speed.

Usage:
    # Full overnight run — all conditions, all Tier A tasks
    python scripts/overnight_swe.py

    # Custom subset
    python scripts/overnight_swe.py --conditions baseline_v0 S01 S02 --tasks astropy__astropy-14182 astropy__astropy-14365

    # Dry run (show what would run)
    python scripts/overnight_swe.py --dry-run

    # Resume (continue from last run in experiment.db)
    python scripts/overnight_swe.py --resume
"""

import argparse
import json
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).parent.parent
DATA_FILE = BASE_DIR / "data" / "swebench_lite_candidates.json"
OUTPUT_RESULTS = BASE_DIR / "results"

# Tier definitions — NOTE: Only 3 astropy tasks exist in data/swebench_lite_candidates.json
# Samuel's original tiers referenced non-existent tasks; adjusted to real data
TIER_A = [  # Available: 3 tasks, 1-2 FAIL_TO_PASS, test_patch 33-44 lines
    "astropy__astropy-14182",
    "astropy__astropy-14365",
    "astropy__astropy-12907",
]

TIER_B = [  # No Tier B tasks in current data file
]

TIER_C = [  # No Tier C tasks in current data file
]

ALL_CONDITIONS = [
    "baseline_v0",
    "baseline_v0_plus_S01",
    "baseline_v0_plus_S02",
    "baseline_v0_plus_S03",
    # Add more as you create them with increment_mutations.py
]

DEFAULT_RUNS_PER_CELL = 5  # runs per (condition, task) pair
SKIP_EVAL = True  # Set False for full Docker eval (much slower)


def get_task_file_path(task_id: str) -> str:
    return str(DATA_FILE)


def build_run_cmd(condition: str, task_id: str, run_index: int, iteration: int = 1) -> list[str]:
    """Build the harness-run-once command for a single run."""
    cmd = [
        "uv", "run", "harness-run-once",
        "--task-id", task_id,
        "--task-file", get_task_file_path(task_id),
        "--condition", condition,
        "--iteration", str(iteration),
        "--run-index", str(run_index),
    ]
    if SKIP_EVAL:
        cmd.append("--skip-eval")
    return cmd


def count_completed_runs(condition: str, task_id: str) -> int:
    """Count how many runs exist in experiment.db for this cell."""
    try:
        import sqlite3
        db_path = BASE_DIR / "results" / "experiment.db"
        if not db_path.exists():
            return 0
        conn = sqlite3.connect(db_path)
        cur = conn.execute(
            "SELECT COUNT(*) FROM runs WHERE condition_id=? AND task_id=?",
            (condition, task_id)
        )
        count = cur.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def run_single(condition: str, task_id: str, run_index: int, iteration: int = 1, max_time: int = 600) -> dict:
    """Run a single harness invocation. Returns result dict."""
    cmd = build_run_cmd(condition, task_id, run_index, iteration)
    start = time.time()
    
    print(f"  [{datetime.now().strftime('%H:%M:%S')}] {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=max_time,
        )
        duration = time.time() - start
        
        return {
            "condition": condition,
            "task_id": task_id,
            "run_index": run_index,
            "duration": duration,
            "exit_code": result.returncode,
            "stdout": result.stdout[-500:] if result.stdout else "",
            "stderr": result.stderr[-500:] if result.stderr else "",
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        duration = time.time() - start
        return {
            "condition": condition,
            "task_id": task_id,
            "run_index": run_index,
            "duration": duration,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Timeout after {max_time}s",
            "success": False,
        }


def plan_overnight_runs(conditions: list, tasks: list, runs_per_cell: int) -> list[tuple]:
    """Return list of (condition, task_id, run_index) that need to run."""
    pending = []
    for condition in conditions:
        for task in tasks:
            completed = count_completed_runs(condition, task)
            needed = runs_per_cell - completed
            if needed > 0:
                for r in range(completed + 1, completed + needed + 1):
                    pending.append((condition, task, r))
    return pending


def print_plan(pending: list):
    print(f"\nPlanned runs: {len(pending)}")
    by_condition = {}
    for cond, task, run in pending:
        by_condition.setdefault(cond, []).append(task)
    for cond, tasks in by_condition.items():
        print(f"  {cond}: {len(tasks)} runs")
    print()


def estimate_time(pending: list, avg_seconds: float = 270) -> str:
    """Estimate total time for remaining runs."""
    total_seconds = len(pending) * avg_seconds
    if total_seconds < 60:
        return f"~{total_seconds}s"
    elif total_seconds < 3600:
        return f"~{total_seconds/60:.0f} min"
    else:
        hours = total_seconds / 3600
        if hours < 24:
            return f"~{hours:.1f} hours"
        else:
            days = hours / 24
            return f"~{days:.1f} days"


def run(args):
    # Resolve conditions
    if args.all_conditions:
        conditions = sorted([c for c in ALL_CONDITIONS if (BASE_DIR / "harness" / f"CONVENTIONS.{c}.md").exists()])
    else:
        conditions = args.conditions

    # Resolve tasks
    if args.all_tiers:
        tasks = TIER_A + TIER_B + TIER_C
    elif args.tier:
        tier_map = {"a": TIER_A, "b": TIER_B, "c": TIER_C}
        tasks = tier_map.get(args.tier.lower(), TIER_A)
    else:
        tasks = args.tasks

    print(f"Conditions: {conditions}")
    print(f"Tasks: {tasks}")
    print(f"Runs per cell: {args.runs_per_cell}")
    print(f"Skip eval: {SKIP_EVAL}")

    pending = plan_overnight_runs(conditions, tasks, args.runs_per_cell)
    print_plan(pending)
    
    if not pending:
        print("All runs complete!")
        return

    print(f"Estimated time: {estimate_time(pending)}")
    
    if args.dry_run:
        print("(dry run — exiting)")
        return

    if args.max_runs:
        pending = pending[:args.max_runs]
        print(f"Capped to {args.max_runs} runs: {estimate_time(pending)}")

    # Start runs
    print(f"\nStarting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    for i, (condition, task, run_idx) in enumerate(pending):
        print(f"\n[{i+1}/{len(pending)}] {condition} × {task} run {run_idx}")
        result = run_single(condition, task, run_idx, max_time=args.max_time)
        
        if result["success"]:
            print(f"  ✓ {result['duration']:.0f}s")
        else:
            print(f"  ✗ exit={result['exit_code']} after {result['duration']:.0f}s")
            if result["stderr"]:
                print(f"    stderr: {result['stderr'][:200]}")

        # Small delay between runs
        time.sleep(2)

    print("\n" + "=" * 60)
    print(f"Done at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    remaining = plan_overnight_runs(conditions, tasks, args.runs_per_cell)
    if remaining:
        print(f"Still pending: {len(remaining)} runs — resume with --resume")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Overnight SWE-bench harness runner")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without running")
    parser.add_argument("--conditions", nargs="+", default=["baseline_v0", "baseline_v0_plus_S01", "baseline_v0_plus_S02", "baseline_v0_plus_S03"])
    parser.add_argument("--all-conditions", action="store_true", help="Use all available conditions")
    parser.add_argument("--tasks", nargs="+", default=TIER_A)
    parser.add_argument("--tier", type=str, choices=["a", "b", "c"], help="Use predefined tier")
    parser.add_argument("--all-tiers", action="store_true", help="Use all tiers")
    parser.add_argument("--runs-per-cell", type=int, default=DEFAULT_RUNS_PER_CELL)
    parser.add_argument("--max-runs", type=int, default=0, help="Max runs per session (0=unlimited)")
    parser.add_argument("--max-time", type=int, default=600, help="Per-run timeout in seconds")
    parser.add_argument("--resume", action="store_true", help="Auto-detect and continue pending runs")
    
    args = parser.parse_args()
    
    if args.resume:
        # Auto-detect what's pending
        conditions = sorted([c for c in ALL_CONDITIONS if (BASE_DIR / "harness" / f"CONVENTIONS.{c}.md").exists()])
        tasks = TIER_A  # Default resume on Tier A
        args.conditions = conditions
        args.tasks = tasks
    
    run(args)
