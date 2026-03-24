"""Git history analyzer for inferring task complexity and patterns from past commits."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import Any

import git


@dataclass
class CommitStats:
    """Statistics about a commit."""

    hash: str
    message: str
    files_changed: list[str]
    lines_added: int
    lines_removed: int
    author: str
    date: str


@dataclass
class HistoricalPattern:
    """Pattern detected from git history."""

    similar_tasks: list[CommitStats]
    avg_files_changed: float
    avg_lines_changed: float
    median_files_changed: float
    median_lines_changed: float
    min_complexity: tuple[int, int]  # (files, lines) for simplest task
    max_complexity: tuple[int, int]  # (files, lines) for most complex task
    common_files: list[str]
    recommendation: str


class GitHistoryAnalyzer:
    """Analyzes git history to infer patterns for similar tasks."""

    def __init__(self, repo_path: str):
        """Initialize the analyzer.

        Args:
            repo_path: Path to the git repository
        """
        self.repo_path = Path(repo_path)
        try:
            self.repo = git.Repo(repo_path)
        except git.InvalidGitRepositoryError as e:
            raise ValueError(f"Not a valid git repository: {repo_path}") from e

    def analyze_task_history(
        self, task_description: str, max_commits: int = 50
    ) -> HistoricalPattern | None:
        """Analyze git history for similar tasks.

        Args:
            task_description: Description of the current task
            max_commits: Maximum number of commits to analyze

        Returns:
            Historical pattern if found, None otherwise
        """
        # Extract keywords and task type
        keywords = self._extract_keywords(task_description)
        task_type = self._classify_task_type(task_description)

        # Find commits with similar keywords
        similar_commits = self._find_similar_commits(keywords, max_commits)

        if not similar_commits:
            return None

        # Filter commits by task type to avoid mixing refactors with features
        filtered_commits = self._filter_by_task_type(similar_commits, task_type)

        if not filtered_commits:
            # Fall back to unfiltered if filtering removed everything
            filtered_commits = similar_commits

        # Remove outliers (tasks 3x+ median size)
        filtered_commits = self._remove_outliers(filtered_commits)

        if not filtered_commits:
            return None

        # Calculate statistics - use median to avoid outlier influence
        file_counts_list = sorted([len(c.files_changed) for c in filtered_commits])
        line_counts_list = sorted([c.lines_added + c.lines_removed for c in filtered_commits])

        total_files = sum(len(c.files_changed) for c in filtered_commits)
        total_lines = sum(c.lines_added + c.lines_removed for c in filtered_commits)
        avg_files = total_files / len(filtered_commits)
        avg_lines = total_lines / len(filtered_commits)

        median_files = file_counts_list[len(file_counts_list) // 2]
        median_lines = line_counts_list[len(line_counts_list) // 2]

        min_complexity = (file_counts_list[0], line_counts_list[0])
        max_complexity = (file_counts_list[-1], line_counts_list[-1])

        # Find common files
        file_counts = defaultdict(int)
        for commit in filtered_commits:
            for file in commit.files_changed:
                file_counts[file] += 1
        common_files = [
            f for f, count in file_counts.items() if count >= len(filtered_commits) * 0.3
        ]

        # Generate recommendation using median (more realistic)
        recommendation = self._generate_recommendation(
            median_files, median_lines, common_files, min_complexity, max_complexity
        )

        return HistoricalPattern(
            similar_tasks=filtered_commits,
            avg_files_changed=avg_files,
            avg_lines_changed=avg_lines,
            median_files_changed=median_files,
            median_lines_changed=median_lines,
            min_complexity=min_complexity,
            max_complexity=max_complexity,
            common_files=common_files,
            recommendation=recommendation,
        )

    def _classify_task_type(self, task_description: str) -> str:
        """Classify the type of task based on description.

        Args:
            task_description: Task description

        Returns:
            Task type: "endpoint", "refactor", "fix", "feature", "test", "docs"
        """
        desc_lower = task_description.lower()

        # Check for specific task types
        if any(word in desc_lower for word in ["endpoint", "route", "api"]) and any(
            word in desc_lower for word in ["add", "create"]
        ):
            return "endpoint"
        if any(
            word in desc_lower for word in ["refactor", "standardize", "restructure", "migrate"]
        ):
            return "refactor"
        if any(word in desc_lower for word in ["fix", "bug", "issue", "error"]):
            return "fix"
        if any(word in desc_lower for word in ["test", "spec", "unit", "integration"]):
            return "test"
        if any(word in desc_lower for word in ["docs", "documentation", "readme"]):
            return "docs"

        return "feature"

    def _filter_by_task_type(
        self, commits: list[CommitStats], target_type: str
    ) -> list[CommitStats]:
        """Filter commits to only include similar task types.

        Args:
            commits: List of commits
            target_type: Target task type

        Returns:
            Filtered list of commits
        """
        # Don't filter for generic "feature" type - too broad
        if target_type == "feature":
            return commits

        filtered = []

        for commit in commits:
            commit_type = self._classify_task_type(commit.message)

            # Match same type, or allow "feature" (generic fallback)
            if commit_type == target_type or commit_type == "feature":
                filtered.append(commit)
            # Special case: endpoint tasks can match features
            elif target_type == "endpoint" and commit_type in ("feature", "endpoint"):
                filtered.append(commit)

        return filtered if len(filtered) >= 3 else commits  # Need at least 3 results

    def _remove_outliers(self, commits: list[CommitStats]) -> list[CommitStats]:
        """Remove outlier commits that are unusually large.

        Args:
            commits: List of commits

        Returns:
            Filtered list without outliers
        """
        if len(commits) < 3:
            return commits  # Need at least 3 to detect outliers

        # Calculate median files and lines changed
        file_counts = sorted([len(c.files_changed) for c in commits])
        line_counts = sorted([c.lines_added + c.lines_removed for c in commits])

        median_files = file_counts[len(file_counts) // 2]
        median_lines = line_counts[len(line_counts) // 2]

        # Filter out commits that are 3x+ median in both files AND lines
        filtered = []
        for commit in commits:
            files = len(commit.files_changed)
            lines = commit.lines_added + commit.lines_removed

            # Only remove if BOTH metrics are extreme outliers
            is_outlier = files > median_files * 3 and lines > median_lines * 3

            if not is_outlier:
                filtered.append(commit)

        # Return original if filtering removed too many
        return filtered if len(filtered) >= len(commits) * 0.5 else commits

    def _extract_keywords(self, task_description: str) -> list[str]:
        """Extract meaningful keywords from task description.

        Args:
            task_description: Task description

        Returns:
            List of keywords
        """
        # Expanded stop words to focus on meaningful technical terms
        stop_words = {
            "add",
            "remove",
            "fix",
            "update",
            "create",
            "delete",
            "implement",
            "build",
            "make",
            "the",
            "a",
            "an",
            "to",
            "for",
            "in",
            "on",
            "with",
            "from",
            "and",
            "or",
        }
        words = task_description.lower().split()
        keywords = [w for w in words if len(w) > 3 and w not in stop_words]

        # Limit to most meaningful keywords (not too many to avoid over-filtering)
        return keywords[:4]

    def _find_similar_commits(self, keywords: list[str], max_commits: int) -> list[CommitStats]:
        """Find commits with similar keywords in commit messages.

        Args:
            keywords: Keywords to search for
            max_commits: Maximum commits to check

        Returns:
            List of similar commits
        """
        similar_commits = []

        for commit in list(self.repo.iter_commits())[:max_commits]:
            message = commit.message.lower()

            # Check if any keyword matches
            if any(keyword in message for keyword in keywords):
                # Get stats for this commit
                stats = self._get_commit_stats(commit)
                if stats:
                    similar_commits.append(stats)

        return similar_commits

    def _get_commit_stats(self, commit: git.Commit) -> CommitStats | None:
        """Extract statistics from a commit.

        Args:
            commit: Git commit object

        Returns:
            Commit statistics or None if unable to extract
        """
        try:
            # Get changed files and line stats
            files_changed = list(commit.stats.files.keys())

            # Use commit.stats for accurate line counts (more reliable than parsing diffs)
            lines_added = sum(stats.get("insertions", 0) for stats in commit.stats.files.values())
            lines_removed = sum(stats.get("deletions", 0) for stats in commit.stats.files.values())

            return CommitStats(
                hash=commit.hexsha[:8],
                message=commit.message.strip().split("\n")[0],
                files_changed=files_changed,
                lines_added=lines_added,
                lines_removed=lines_removed,
                author=str(commit.author),
                date=commit.committed_datetime.isoformat(),
            )
        except Exception:
            return None

    def _generate_recommendation(
        self,
        median_files: float,
        median_lines: float,
        common_files: list[str],
        min_complexity: tuple[int, int],
        max_complexity: tuple[int, int],
    ) -> str:
        """Generate a recommendation based on historical patterns.

        Args:
            median_files: Median files changed
            median_lines: Median lines changed
            common_files: Commonly modified files
            min_complexity: (files, lines) for simplest similar task
            max_complexity: (files, lines) for most complex similar task

        Returns:
            Recommendation string
        """
        recommendations = []

        # Show range to help calibrate expectations
        min_files, min_lines = min_complexity
        max_files, max_lines = max_complexity

        if median_files <= 5:
            recommendations.append(
                f"Simple (median: {median_files:.0f} files, ~{median_lines:.0f} lines)"
            )
            recommendations.append(
                f"Range: {min_files}-{max_files} files - start with minimal approach"
            )
        elif median_files <= 10:
            recommendations.append(
                f"Moderate (median: {median_files:.0f} files, ~{median_lines:.0f} lines)"
            )
            recommendations.append(
                f"Range: {min_files}-{max_files} files - balance simplicity & completeness"
            )
        else:
            recommendations.append(
                f"Complex (median: {median_files:.0f} files, ~{median_lines:.0f} lines)"
            )
            recommendations.append(
                f"Range: {min_files}-{max_files} files - plan carefully, test thoroughly"
            )

        if common_files:
            recommendations.append(f"Commonly modified: {', '.join(common_files[:3])}")

        return "; ".join(recommendations)

    def get_recent_patterns(self, days: int = 30) -> dict[str, Any]:
        """Get patterns from recent commits.

        Args:
            days: Number of days to look back

        Returns:
            Dictionary with pattern statistics
        """
        from datetime import datetime, timedelta

        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        commits = []
        for commit in self.repo.iter_commits():
            if commit.committed_datetime < cutoff_date:
                break
            stats = self._get_commit_stats(commit)
            if stats:
                commits.append(stats)

        if not commits:
            return {
                "commits_analyzed": 0,
                "avg_files_per_commit": 0,
                "avg_lines_per_commit": 0,
            }

        total_files = sum(len(c.files_changed) for c in commits)
        total_lines = sum(c.lines_added + c.lines_removed for c in commits)

        return {
            "commits_analyzed": len(commits),
            "avg_files_per_commit": total_files / len(commits),
            "avg_lines_per_commit": total_lines / len(commits),
            "period_days": days,
        }
