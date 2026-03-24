"""
OpenCode Token Tracker

Tracks token usage during real OpenCode task execution by:
1. Running tasks via OpenCode CLI
2. Exporting session data (contains per-message token counts)
3. Aggregating token metrics for comparison

Compares two scenarios:
- Regular OpenCode (no repo-brain, uses built-in tools)
- OpenCode with /scope (repo-brain's on-demand context injection)

Uses OpenCode CLI commands:
- `opencode run` - Execute tasks
- `opencode session list` - Get session IDs
- `opencode export <sessionID>` - Export session data with token details
"""

import json
import logging
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Token usage metrics for a task."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        """Add two TokenUsage instances."""
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            cost=self.cost + other.cost,
        )


@dataclass
class TaskResult:
    """Result of executing an OpenCode task."""

    task_description: str
    session_id: str
    success: bool
    tokens: TokenUsage
    duration_seconds: float
    num_messages: int
    num_tool_calls: int
    error: str | None = None


class OpenCodeTokenTracker:
    """
    Tracks token usage during OpenCode task execution.

    Uses OpenCode CLI to run tasks and extract token metrics from session exports.
    """

    def __init__(self, repo_path: Path, opencode_bin: Path | None = None):
        """
        Initialize tracker.

        Args:
            repo_path: Path to repository
            opencode_bin: Path to OpenCode binary (defaults to ~/.opencode/bin/opencode)
        """
        self.repo_path = Path(repo_path).resolve()
        self.opencode_bin = opencode_bin or (Path.home() / ".opencode" / "bin" / "opencode")

        if not self.opencode_bin.exists():
            raise FileNotFoundError(f"OpenCode binary not found at {self.opencode_bin}")

        if not self.repo_path.exists():
            raise FileNotFoundError(f"Repository not found at {self.repo_path}")

    def run_task_with_tracking(
        self,
        task_description: str,
        use_repo_brain: bool = True,
        timeout: int = 600,
    ) -> TaskResult:
        """
        Run an OpenCode task and track token usage.

        Args:
            task_description: Task to execute.
                For repo-brain tests, should start with "/scope <task>"
                For regular tests, just the task description
            use_repo_brain: Whether repo-brain is enabled (affects which repo is used)
            timeout: Maximum execution time in seconds

        Returns:
            TaskResult with token usage metrics
        """
        logger.info(f"Running task: '{task_description}' (repo-brain={use_repo_brain})")

        # Run task
        start_time = time.time()
        session_id = None
        try:
            result = self._run_opencode_task(task_description, use_repo_brain, timeout)
            duration = time.time() - start_time
            success = result.returncode == 0

            # Extract session ID from JSON output
            if success and result.stdout:
                session_id = self._extract_session_id_from_output(result.stdout)

            error = None if success else result.stderr
        except subprocess.TimeoutExpired:
            duration = timeout
            success = False
            error = f"Task timed out after {timeout} seconds"
            logger.error(error)
            return TaskResult(
                task_description=task_description,
                session_id="timeout",
                success=False,
                tokens=TokenUsage(),
                duration_seconds=duration,
                num_messages=0,
                num_tool_calls=0,
                error=error,
            )
        except Exception as e:
            duration = time.time() - start_time
            error = f"Failed to run task: {e}"
            logger.error(error)
            return TaskResult(
                task_description=task_description,
                session_id="error",
                success=False,
                tokens=TokenUsage(),
                duration_seconds=duration,
                num_messages=0,
                num_tool_calls=0,
                error=error,
            )

        # Check if we got a session ID
        if not session_id:
            logger.warning("No session ID found in output")
            return TaskResult(
                task_description=task_description,
                session_id="unknown",
                success=success,
                tokens=TokenUsage(),
                duration_seconds=duration,
                num_messages=0,
                num_tool_calls=0,
                error="No session ID in output",
            )

        logger.info(f"Found session: {session_id}")

        # Export session data
        try:
            session_data = self._export_session(session_id)
        except Exception as e:
            error = f"Failed to export session: {e}"
            logger.error(error)
            return TaskResult(
                task_description=task_description,
                session_id=session_id,
                success=success,
                tokens=TokenUsage(),
                duration_seconds=duration,
                num_messages=0,
                num_tool_calls=0,
                error=error,
            )

        # Extract token usage
        tokens = self._extract_token_usage(session_data)
        num_messages = len(session_data.get("messages", []))
        num_tool_calls = self._count_tool_calls(session_data)

        logger.info(
            f"Task completed: {num_messages} messages, "
            f"{tokens.total_tokens} total tokens, "
            f"{duration:.1f}s"
        )

        return TaskResult(
            task_description=task_description,
            session_id=session_id,
            success=success,
            tokens=tokens,
            duration_seconds=duration,
            num_messages=num_messages,
            num_tool_calls=num_tool_calls,
            error=error,
        )

    def _run_opencode_task(
        self, task_description: str, use_repo_brain: bool, timeout: int
    ) -> subprocess.CompletedProcess:
        """
        Run OpenCode task via CLI.

        Args:
            task_description: Task to execute
            use_repo_brain: Whether repo-brain is enabled in the target repository
                (Note: This is informational only - the tracker uses different repos
                for with/without repo-brain tests)
            timeout: Maximum execution time in seconds

        Returns:
            CompletedProcess result
        """
        # Note: The use_repo_brain flag doesn't affect the command itself.
        # Instead, we use different repository directories:
        # - Regular repo: No .opencode/commands/scope.md or repo-brain setup
        # - Repo-brain repo: Has repo-brain configured with /scope and /q commands

        cmd = [
            str(self.opencode_bin),
            "run",
            "--dir",
            str(self.repo_path),
            "--format",
            "json",
            "--title",
            f"Token tracking: {task_description[:50]}",
            task_description,
        ]

        logger.info(f"Running task: '{task_description[:60]}...'")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=self.repo_path,
        )

        return result

    def _extract_session_id_from_output(self, output: str) -> str | None:
        """
        Extract session ID from OpenCode JSON output.

        Args:
            output: JSON output from `opencode run --format json`

        Returns:
            Session ID (e.g., "ses_abc123") or None if not found
        """
        # Parse first JSON line to get session ID
        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if "sessionID" in data:
                    return data["sessionID"]
            except json.JSONDecodeError:
                continue

        logger.warning("No session ID found in output")
        return None

    def _get_session_ids(self) -> list[str]:
        """
        Get list of OpenCode session IDs for this repository.

        Returns:
            List of session IDs (e.g., ["ses_abc123", "ses_def456"])
        """
        try:
            result = subprocess.run(
                [str(self.opencode_bin), "session", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                logger.warning(f"Failed to list sessions: {result.stderr}")
                return []

            # Parse session IDs from output
            # Expected format: Lines with session IDs like "ses_xxxxx"
            session_ids = re.findall(r"ses_[a-zA-Z0-9]+", result.stdout)
            return session_ids

        except Exception as e:
            logger.warning(f"Failed to get session IDs: {e}")
            return []

    def _export_session(self, session_id: str) -> dict[str, Any]:
        """
        Export session data from OpenCode.

        Args:
            session_id: Session ID to export

        Returns:
            Parsed JSON session data

        Raises:
            subprocess.CalledProcessError: If export fails
            json.JSONDecodeError: If response is not valid JSON
        """
        result = subprocess.run(
            [str(self.opencode_bin), "export", session_id],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,  # Raise exception on non-zero exit
        )

        return json.loads(result.stdout)

    def _extract_token_usage(self, session_data: dict[str, Any]) -> TokenUsage:
        """
        Extract token usage from session data.

        Session data format (from OpenCode export):
        {
          "info": {...},
          "messages": [
            {
              "info": {
                "role": "assistant",
                "tokens": {
                  "total": 13628,
                  "input": 13174,
                  "output": 454,
                  "cache": {
                    "read": 12797,
                    "write": 0
                  }
                },
                "cost": 0.042
              }
            },
            ...
          ]
        }

        Args:
            session_data: Parsed JSON from opencode export

        Returns:
            Aggregated token usage
        """
        usage = TokenUsage()

        for message in session_data.get("messages", []):
            msg_info = message.get("info", {})

            # Only count assistant messages (user messages don't consume tokens)
            if msg_info.get("role") != "assistant":
                continue

            tokens = msg_info.get("tokens", {})
            cache = tokens.get("cache", {})

            usage.prompt_tokens += tokens.get("input", 0)
            usage.completion_tokens += tokens.get("output", 0)
            usage.cache_read_tokens += cache.get("read", 0)
            usage.cache_write_tokens += cache.get("write", 0)
            usage.total_tokens += tokens.get("total", 0)
            usage.cost += msg_info.get("cost", 0.0)

        return usage

    def _count_tool_calls(self, session_data: dict[str, Any]) -> int:
        """
        Count number of tool calls in session.

        Args:
            session_data: Parsed JSON from opencode export

        Returns:
            Number of tool invocations
        """
        tool_calls = 0

        for message in session_data.get("messages", []):
            # Check if message contains tool uses
            if "content" in message:
                content = message.get("content", [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "tool_use":
                            tool_calls += 1

        return tool_calls

    def compare_approaches(
        self,
        tasks: list[str],
        runs_per_task: int = 3,
    ) -> dict[str, Any]:
        """
        Compare token usage between /scope approach and regular OpenCode.

        Args:
            tasks: List of task descriptions to test
                For repo-brain tests, prepend "/scope " to trigger blast-radius analysis
            runs_per_task: Number of runs per task for averaging

        Returns:
            Comparison results with aggregated metrics
        """
        logger.info(f"Comparing approaches across {len(tasks)} tasks...")

        repo_brain_results = []
        regular_results = []

        for i, task in enumerate(tasks, 1):
            logger.info(f"\n=== Task {i}/{len(tasks)}: {task} ===")

            # Run with repo-brain
            for run in range(runs_per_task):
                logger.info(f"  Run {run + 1}/{runs_per_task} with repo-brain...")
                result = self.run_task_with_tracking(task, use_repo_brain=True)
                repo_brain_results.append(result)

            # Run without repo-brain
            for run in range(runs_per_task):
                logger.info(f"  Run {run + 1}/{runs_per_task} without repo-brain...")
                result = self.run_task_with_tracking(task, use_repo_brain=False)
                regular_results.append(result)

        # Aggregate results
        def aggregate(results: list[TaskResult]) -> dict[str, Any]:
            successful = [r for r in results if r.success]
            total_tokens = sum(r.tokens.total_tokens for r in successful)
            total_cost = sum(r.tokens.cost for r in successful)
            avg_duration = (
                sum(r.duration_seconds for r in successful) / len(successful) if successful else 0
            )
            avg_messages = (
                sum(r.num_messages for r in successful) / len(successful) if successful else 0
            )

            return {
                "num_tasks": len(results),
                "successful": len(successful),
                "failed": len(results) - len(successful),
                "total_tokens": total_tokens,
                "avg_tokens_per_task": total_tokens / len(successful) if successful else 0,
                "total_cost": total_cost,
                "avg_cost_per_task": total_cost / len(successful) if successful else 0,
                "avg_duration": avg_duration,
                "avg_messages": avg_messages,
            }

        repo_brain_stats = aggregate(repo_brain_results)
        regular_stats = aggregate(regular_results)

        # Calculate differences (positive = repo-brain uses less, negative = repo-brain uses more)
        token_diff = (
            (regular_stats["avg_tokens_per_task"] - repo_brain_stats["avg_tokens_per_task"])
            / regular_stats["avg_tokens_per_task"]
            * 100
            if regular_stats["avg_tokens_per_task"] > 0
            else 0
        )

        cost_diff = (
            (regular_stats["avg_cost_per_task"] - repo_brain_stats["avg_cost_per_task"])
            / regular_stats["avg_cost_per_task"]
            * 100
            if regular_stats["avg_cost_per_task"] > 0
            else 0
        )

        time_diff = (
            (regular_stats["avg_duration"] - repo_brain_stats["avg_duration"])
            / regular_stats["avg_duration"]
            * 100
            if regular_stats["avg_duration"] > 0
            else 0
        )

        return {
            "repo_brain": repo_brain_stats,
            "regular": regular_stats,
            "differences": {
                "token_diff_percent": token_diff,
                "cost_diff_percent": cost_diff,
                "time_diff_percent": time_diff,
            },
            "raw_results": {
                "repo_brain": repo_brain_results,
                "regular": regular_results,
            },
        }


def main():
    """Example usage."""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    if len(sys.argv) < 2:
        print("Usage: python opencode_token_tracker.py <repo_path> [task_description]")
        sys.exit(1)

    repo_path = Path(sys.argv[1])
    task = sys.argv[2] if len(sys.argv) > 2 else "List all API endpoints in this codebase"

    tracker = OpenCodeTokenTracker(repo_path)

    # Single task test
    logger.info("Running single task test...")
    result = tracker.run_task_with_tracking(task, use_repo_brain=True)

    print("\n" + "=" * 60)
    print("TASK RESULT")
    print("=" * 60)
    print(f"Task: {result.task_description}")
    print(f"Session ID: {result.session_id}")
    print(f"Success: {result.success}")
    print(f"Duration: {result.duration_seconds:.1f}s")
    print(f"Messages: {result.num_messages}")
    print(f"Tool calls: {result.num_tool_calls}")
    print("\nToken Usage:")
    print(f"  Prompt tokens: {result.tokens.prompt_tokens:,}")
    print(f"  Completion tokens: {result.tokens.completion_tokens:,}")
    print(f"  Cache read: {result.tokens.cache_read_tokens:,}")
    print(f"  Total tokens: {result.tokens.total_tokens:,}")
    print(f"  Cost: ${result.tokens.cost:.4f}")
    if result.error:
        print(f"\nError: {result.error}")


if __name__ == "__main__":
    main()
