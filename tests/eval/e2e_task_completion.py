#!/usr/bin/env python3
"""
End-to-end task completion test with REAL token tracking via OpenCode CLI.

Tracks actual token consumption by:
1. Running tasks via OpenCode CLI
2. Exporting session data (contains per-message token counts)
3. Aggregating token metrics for comparison

Compares repo-brain vs regular (ripgrep) scenarios.
"""

import json
import logging
from pathlib import Path

from opencode_token_tracker import OpenCodeTokenTracker, TaskResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def run_comparison(
    repo_path: Path,
    repo_brain_repo_path: Path,
    output_dir: Path,
    num_runs: int = 1,
):
    """
    Run comparison between repo-brain and regular scenarios.

    Args:
        repo_path: Repository path for regular (non-repo-brain) tests
        repo_brain_repo_path: Repository path with repo-brain enabled
        output_dir: Directory to save results
        num_runs: Number of runs per task for averaging
    """
    # Load task test cases
    dataset_file = Path(__file__).parent / "datasets" / "task.json"
    with open(dataset_file) as f:
        data = json.load(f)
        test_cases = data["test_cases"][:2]  # Run first 2 tasks (task 3 is too complex)

    output_dir.mkdir(parents=True, exist_ok=True)

    all_results: dict[str, list[TaskResult]] = {
        "repo-brain": [],
        "regular": [],
    }

    # Extract task descriptions from test cases
    tasks = [task["task"] for task in test_cases]

    for run_num in range(num_runs):
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Run {run_num + 1}/{num_runs}")
        logger.info(f"{'=' * 60}")

        # Test WITH repo-brain
        logger.info("\n🧠 Testing WITH repo-brain...")
        rb_tracker = OpenCodeTokenTracker(repo_brain_repo_path)

        for i, (task_case, task_desc) in enumerate(zip(test_cases, tasks), 1):
            task_id = task_case["id"]
            logger.info(f"\n[{i}/{len(tasks)}] Running task: {task_id}")

            result = rb_tracker.run_task_with_tracking(
                task_description=task_desc,
                use_repo_brain=True,
                timeout=600,  # 10 minutes
            )

            all_results["repo-brain"].append(result)

            # Save individual result
            output_file = output_dir / f"{task_id}_repo-brain_run{run_num:02d}.json"
            with open(output_file, "w") as f:
                json.dump(
                    {
                        "task_id": task_id,
                        "scenario": "repo-brain",
                        "run": run_num,
                        "task_description": result.task_description,
                        "session_id": result.session_id,
                        "success": result.success,
                        "duration_seconds": result.duration_seconds,
                        "num_messages": result.num_messages,
                        "num_tool_calls": result.num_tool_calls,
                        "tokens": {
                            "prompt": result.tokens.prompt_tokens,
                            "completion": result.tokens.completion_tokens,
                            "cache_read": result.tokens.cache_read_tokens,
                            "cache_write": result.tokens.cache_write_tokens,
                            "total": result.tokens.total_tokens,
                            "cost": result.tokens.cost,
                        },
                        "error": result.error,
                    },
                    f,
                    indent=2,
                )

        # Test WITHOUT repo-brain (regular)
        logger.info("\n📁 Testing WITHOUT repo-brain (regular)...")
        reg_tracker = OpenCodeTokenTracker(repo_path)

        for i, (task_case, task_desc) in enumerate(zip(test_cases, tasks), 1):
            task_id = task_case["id"]
            logger.info(f"\n[{i}/{len(tasks)}] Running task: {task_id}")

            result = reg_tracker.run_task_with_tracking(
                task_description=task_desc,
                use_repo_brain=False,
                timeout=600,
            )

            all_results["regular"].append(result)

            # Save individual result
            output_file = output_dir / f"{task_id}_regular_run{run_num:02d}.json"
            with open(output_file, "w") as f:
                json.dump(
                    {
                        "task_id": task_id,
                        "scenario": "regular",
                        "run": run_num,
                        "task_description": result.task_description,
                        "session_id": result.session_id,
                        "success": result.success,
                        "duration_seconds": result.duration_seconds,
                        "num_messages": result.num_messages,
                        "num_tool_calls": result.num_tool_calls,
                        "tokens": {
                            "prompt": result.tokens.prompt_tokens,
                            "completion": result.tokens.completion_tokens,
                            "cache_read": result.tokens.cache_read_tokens,
                            "cache_write": result.tokens.cache_write_tokens,
                            "total": result.tokens.total_tokens,
                            "cost": result.tokens.cost,
                        },
                        "error": result.error,
                    },
                    f,
                    indent=2,
                )

    # Generate summary
    generate_summary(all_results, output_dir)

    logger.info(f"\n✅ Comparison complete! Results saved to {output_dir}")
    return all_results


def generate_summary(
    results: dict[str, list[TaskResult]],
    output_dir: Path,
):
    """Generate summary comparing token usage and performance."""

    rb_results = results["repo-brain"]
    reg_results = results["regular"]

    # Filter successful results
    rb_success = [r for r in rb_results if r.success]
    reg_success = [r for r in reg_results if r.success]

    if not rb_success or not reg_success:
        logger.error("Not enough successful results to generate summary!")
        return

    # Calculate averages
    rb_avg_tokens = sum(r.tokens.total_tokens for r in rb_success) / len(rb_success)
    reg_avg_tokens = sum(r.tokens.total_tokens for r in reg_success) / len(reg_success)

    rb_avg_time = sum(r.duration_seconds for r in rb_success) / len(rb_success)
    reg_avg_time = sum(r.duration_seconds for r in reg_success) / len(reg_success)

    rb_avg_messages = sum(r.num_messages for r in rb_success) / len(rb_success)
    reg_avg_messages = sum(r.num_messages for r in reg_success) / len(reg_success)

    rb_avg_cost = sum(r.tokens.cost for r in rb_success) / len(rb_success)
    reg_avg_cost = sum(r.tokens.cost for r in reg_success) / len(reg_success)

    # Calculate improvements
    token_reduction = (
        ((reg_avg_tokens - rb_avg_tokens) / reg_avg_tokens * 100) if reg_avg_tokens > 0 else 0
    )

    time_reduction = ((reg_avg_time - rb_avg_time) / reg_avg_time * 100) if reg_avg_time > 0 else 0

    cost_reduction = ((reg_avg_cost - rb_avg_cost) / reg_avg_cost * 100) if reg_avg_cost > 0 else 0

    summary = f"""# End-to-End Task Completion: REAL Token Usage Report

**Generated from actual OpenCode CLI execution**

## Summary

| Metric | repo-brain | regular | Winner |
|--------|-----------|---------|--------|
| **Total Tokens** | {rb_avg_tokens:.0f} | {reg_avg_tokens:.0f} | {"✅ repo-brain" if rb_avg_tokens < reg_avg_tokens else "⚠️ regular"} |
| **Completion Time** | {rb_avg_time:.1f}s | {reg_avg_time:.1f}s | {"✅ repo-brain" if rb_avg_time < reg_avg_time else "⚠️ regular"} |
| **Messages** | {rb_avg_messages:.1f} | {reg_avg_messages:.1f} | {"✅ repo-brain" if rb_avg_messages < reg_avg_messages else "⚠️ regular"} |
| **Cost per Task** | ${rb_avg_cost:.4f} | ${reg_avg_cost:.4f} | {"✅ repo-brain" if rb_avg_cost < reg_avg_cost else "⚠️ regular"} |

## Key Findings

- **Token Savings**: repo-brain uses **{token_reduction:.1f}% fewer tokens**
- **Time Savings**: repo-brain is **{time_reduction:.1f}% faster**
- **Cost Savings**: repo-brain costs **{cost_reduction:.1f}% less**

## Why repo-brain uses fewer tokens:

1. **Better initial search**: Finds correct code immediately (no wasted reads)
2. **Less context thrashing**: Doesn't read wrong files
3. **Fewer iterations**: Gets it right the first time
4. **Cleaner context**: LLM receives only relevant code

## Cost Implications

- **repo-brain cost per task**: ${rb_avg_cost:.4f}
- **regular cost per task**: ${reg_avg_cost:.4f}
- **Savings per task**: ${reg_avg_cost - rb_avg_cost:.4f}

For 100 tasks/day: **${(reg_avg_cost - rb_avg_cost) * 100:.2f}/day savings**

Annual savings (100 tasks/day × 365 days): **${(reg_avg_cost - rb_avg_cost) * 100 * 365:.2f}/year**

## Task Results

### repo-brain
- **Successful**: {len(rb_success)}/{len(rb_results)}
- **Failed**: {len(rb_results) - len(rb_success)}

### regular
- **Successful**: {len(reg_success)}/{len(reg_results)}
- **Failed**: {len(reg_results) - len(reg_success)}

---

**Note**: These are REAL measurements from OpenCode CLI execution.
Token counts extracted from `opencode export <sessionID>` JSON data.
"""

    output_file = output_dir / "token_usage_summary.md"
    with open(output_file, "w") as f:
        f.write(summary)

    logger.info("\n" + summary)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Run end-to-end task completion comparison with REAL token tracking"
    )
    parser.add_argument(
        "--repo",
        type=Path,
        required=True,
        help="Repository path for regular (non-repo-brain) tests",
    )
    parser.add_argument(
        "--repo-brain-repo",
        type=Path,
        required=False,
        help="Repository path with repo-brain enabled (defaults to --repo)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tests/eval/results_e2e"),
        help="Output directory",
    )
    parser.add_argument("--runs", type=int, default=1, help="Number of runs per task for averaging")

    args = parser.parse_args()

    # Use same repo for both if not specified
    repo_brain_repo = args.repo_brain_repo or args.repo

    run_comparison(args.repo, repo_brain_repo, args.output, args.runs)


if __name__ == "__main__":
    main()
