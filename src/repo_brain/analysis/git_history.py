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
        # Extract keywords from task description
        keywords = self._extract_keywords(task_description)

        # Find commits with similar keywords
        similar_commits = self._find_similar_commits(keywords, max_commits)

        if not similar_commits:
            return None

        # Calculate statistics
        total_files = sum(len(c.files_changed) for c in similar_commits)
        total_lines = sum(c.lines_added + c.lines_removed for c in similar_commits)
        avg_files = total_files / len(similar_commits)
        avg_lines = total_lines / len(similar_commits)

        # Find common files
        file_counts = defaultdict(int)
        for commit in similar_commits:
            for file in commit.files_changed:
                file_counts[file] += 1
        common_files = [
            f for f, count in file_counts.items() if count >= len(similar_commits) * 0.3
        ]

        # Generate recommendation
        recommendation = self._generate_recommendation(avg_files, avg_lines, common_files)

        return HistoricalPattern(
            similar_tasks=similar_commits,
            avg_files_changed=avg_files,
            avg_lines_changed=avg_lines,
            common_files=common_files,
            recommendation=recommendation,
        )

    def _extract_keywords(self, task_description: str) -> list[str]:
        """Extract meaningful keywords from task description.

        Args:
            task_description: Task description

        Returns:
            List of keywords
        """
        # Simple keyword extraction (can be enhanced with NLP)
        stop_words = {
            "add",
            "remove",
            "fix",
            "update",
            "create",
            "delete",
            "the",
            "a",
            "an",
            "to",
            "for",
            "in",
            "on",
        }
        words = task_description.lower().split()
        keywords = [w for w in words if len(w) > 3 and w not in stop_words]
        return keywords[:5]  # Limit to top 5 keywords

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
        self, avg_files: float, avg_lines: float, common_files: list[str]
    ) -> str:
        """Generate a recommendation based on historical patterns.

        Args:
            avg_files: Average files changed
            avg_lines: Average lines changed
            common_files: Commonly modified files

        Returns:
            Recommendation string
        """
        recommendations = []

        if avg_files <= 3:
            recommendations.append("Inline solution (typically 2-3 files modified)")
        elif avg_files <= 7:
            recommendations.append("Medium scope (typically 4-7 files modified)")
        else:
            recommendations.append("Large refactor (8+ files typically modified)")

        if avg_lines < 200:
            recommendations.append(f"Simple implementation (~{avg_lines:.0f} lines)")
        elif avg_lines < 500:
            recommendations.append(f"Moderate implementation (~{avg_lines:.0f} lines)")
        else:
            recommendations.append(f"Complex implementation (~{avg_lines:.0f} lines)")

        if common_files:
            recommendations.append("Commonly modified: {}".format(", ".join(common_files[:3])))

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
