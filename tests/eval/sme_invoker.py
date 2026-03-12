"""
SME Agent Invoker for OpenCode integration.

This module provides integration with OpenCode's SME agents for code review evaluation.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Agent mapping from AGENTS.md
AGENT_FILE_MAPPING = {
    "services/auth-service/": "artemis",
    "services/rest-api/": "arik",
    "services/radkit-rest-api/": "tarik",
    "agents/task/": "tarik",
    "mcp_servers/radkit/": "tarik",
    "services/swarm-node/": "orion",
    "libraries/python/swarm-coordination/": "orion",
    "services/event-swarm-node/": "evan",
    "libraries/python/faa-events/": "evan",
    "mcp_servers/": "marco",
    "services/ui/": "reina",
    "services/postgres/": "dara",
    "services/postgres-init/migrations/": "dara",
    "agents/planner-agent/": "petra",
    "libraries/python/deep-agent/": "petra",
    "tests/e2e/rubric-validation/": "luna",
    "sanitize.py": "kai",
    "swarm_node/main.py": "kai",
}


def determine_sme_agents(files_changed: list[str]) -> list[str]:
    """
    Determine which SME agents should be invoked based on files changed.

    Args:
        files_changed: List of file paths that were modified

    Returns:
        List of agent names (e.g., ['artemis', 'dara'])
    """
    agents = set()

    for file_path in files_changed:
        for pattern, agent in AGENT_FILE_MAPPING.items():
            if pattern in file_path:
                agents.add(agent)

    return sorted(list(agents))


def invoke_sme_agent_via_git(
    agent_name: str, repo_path: Path, pr_number: str | None = None, branch: str | None = None
) -> dict[str, Any]:
    """
    Invoke an SME agent by analyzing git changes.

    This uses git to get the diff and then simulates what the agent would review.

    Args:
        agent_name: Name of the SME agent (e.g., 'artemis')
        repo_path: Path to the repository
        pr_number: Optional PR number for context
        branch: Optional branch to compare against (default: 'develop')

    Returns:
        Dictionary with review results
    """
    if not branch:
        branch = "develop"

    try:
        # Get list of changed files
        cmd = ["git", "diff", f"{branch}...HEAD", "--name-only"]
        files_output = subprocess.check_output(
            cmd, cwd=repo_path, text=True, stderr=subprocess.STDOUT
        )
        changed_files = [f for f in files_output.strip().split("\n") if f]

        # Get the actual diff
        cmd = ["git", "diff", f"{branch}...HEAD"]
        diff_output = subprocess.check_output(
            cmd, cwd=repo_path, text=True, stderr=subprocess.STDOUT
        )

        # Parse for issues based on agent type
        issues = _simulate_agent_review(agent_name, changed_files, diff_output)

        return {
            "agent": agent_name,
            "files_reviewed": changed_files,
            "issues_found": issues,
            "review_completed": True,
        }

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get git diff: {e}")
        return {
            "agent": agent_name,
            "files_reviewed": [],
            "issues_found": [],
            "review_completed": False,
            "error": str(e),
        }


def _simulate_agent_review(agent_name: str, files: list[str], diff: str) -> list[dict[str, Any]]:
    """
    Simulate agent review by applying domain-specific patterns.

    In a real implementation, this would call OpenCode's Task tool.
    For now, we apply basic pattern matching based on agent expertise.
    """
    issues = []

    # Define patterns per agent (based on their checklists from AGENTS.md)
    patterns = {
        "artemis": {
            "critical": [
                (r"jwt\.secret\s*=\s*['\"][^'\"]+['\"]", "JWT secret hardcoded"),
                (r"password\s*==", "Timing-unsafe password comparison"),
            ],
            "warning": [
                (r"jwt\.expir.*=.*[0-9]{2,}.*day", "JWT expiration too long"),
            ],
        },
        "dara": {
            "critical": [
                (r"def downgrade\(\):\s*pass", "Missing downgrade implementation"),
                (r"Integer\(.*primary_key.*autoincrement", "Using auto-increment IDs"),
            ],
            "warning": [
                (r"\.execute\(.*\%", "Possible SQL injection (string formatting)"),
            ],
        },
        "arik": {
            "critical": [
                (r"@app\.(get|post).*\n(?!.*@limiter)", "Missing rate limiting"),
            ],
            "warning": [
                (r"HTTPException\(.*detail=.*user", "User enumeration risk"),
            ],
        },
        "reina": {
            "warning": [
                (r"useEffect\(\[.*\],\s*\[\]\)", "Empty dependency array in useEffect"),
                (r"any", "Using 'any' type"),
            ],
        },
    }

    import re

    agent_patterns = patterns.get(agent_name, {})

    for severity, pattern_list in agent_patterns.items():
        for pattern, description in pattern_list:
            matches = list(re.finditer(pattern, diff, re.MULTILINE | re.IGNORECASE))
            for match in matches:
                issues.append(
                    {
                        "severity": severity,
                        "description": description,
                        "pattern": pattern,
                        "line": diff[: match.start()].count("\n") + 1,
                    }
                )

    return issues


def invoke_sme_agent_via_opencode_cli(
    agent_name: str, repo_path: Path, prompt: str
) -> dict[str, Any]:
    """
    Invoke SME agent via OpenCode CLI (if available).

    This would be the preferred method if OpenCode exposes a CLI.

    Args:
        agent_name: SME agent name (e.g., '@artemis')
        repo_path: Repository path
        prompt: Review prompt to send to the agent

    Returns:
        Review results dictionary
    """
    # Check if opencode CLI exists
    try:
        # Try to invoke via hypothetical OpenCode CLI
        cmd = [
            "opencode",
            "agent",
            "invoke",
            f"@{agent_name}",
            "--repo",
            str(repo_path),
            "--prompt",
            prompt,
            "--output",
            "json",
        ]

        output = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
        return json.loads(output)

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning(f"OpenCode CLI not available: {e}")
        logger.info("Falling back to git-based analysis")
        return invoke_sme_agent_via_git(agent_name, repo_path)


def parse_sme_review_output(review_text: str) -> dict[str, Any]:
    """
    Parse SME agent review output.

    Expected format (from AGENTS.md response style):
    ```
    ## Authentication Review for PR #XXX

    ### Summary
    <Brief overview>

    ### Security Analysis
    | Check | Status | Notes |
    |-------|--------|-------|
    | JWT Expiration | Pass/FAIL | ... |

    ### Issues Found

    #### Critical (Must Fix)
    1. **Issue Name** - `file:line`
       - Problem: ...
       - Risk: ...
       - Fix: ...

    #### Warning (Should Fix)
    ...
    ```
    """
    import re

    result = {
        "summary": "",
        "critical_issues": [],
        "warnings": [],
        "checks": {},
    }

    # Extract summary
    summary_match = re.search(r"### Summary\n(.*?)\n###", review_text, re.DOTALL)
    if summary_match:
        result["summary"] = summary_match.group(1).strip()

    # Extract critical issues
    critical_section = re.search(r"#### Critical.*?\n(.*?)(?:####|\Z)", review_text, re.DOTALL)
    if critical_section:
        issue_pattern = r"\d+\.\s+\*\*(.+?)\*\*\s+-\s+`(.+?)`"
        for match in re.finditer(issue_pattern, critical_section.group(1)):
            result["critical_issues"].append({"title": match.group(1), "location": match.group(2)})

    # Extract warnings
    warning_section = re.search(r"#### Warning.*?\n(.*?)(?:####|\Z)", review_text, re.DOTALL)
    if warning_section:
        issue_pattern = r"\d+\.\s+\*\*(.+?)\*\*\s+-\s+`(.+?)`"
        for match in re.finditer(issue_pattern, warning_section.group(1)):
            result["warnings"].append({"title": match.group(1), "location": match.group(2)})

    return result


def calculate_review_quality_score(
    review_result: dict[str, Any], ground_truth: dict[str, Any]
) -> float:
    """
    Calculate review quality score by comparing with ground truth.

    Args:
        review_result: Parsed SME review results
        ground_truth: Expected issues from test case

    Returns:
        Quality score from 0.0 to 1.0
    """
    expected_critical = set(issue["issue"] for issue in ground_truth.get("critical_issues", []))
    expected_warnings = set(issue["issue"] for issue in ground_truth.get("warnings", []))

    found_critical = set(issue["title"] for issue in review_result.get("critical_issues", []))
    found_warnings = set(issue["title"] for issue in review_result.get("warnings", []))

    # Calculate precision and recall for critical issues
    if expected_critical:
        critical_recall = len(found_critical & expected_critical) / len(expected_critical)
    else:
        critical_recall = 1.0 if not found_critical else 0.0

    if found_critical:
        critical_precision = len(found_critical & expected_critical) / len(found_critical)
    else:
        critical_precision = 1.0 if not expected_critical else 0.0

    # Calculate precision and recall for warnings
    if expected_warnings:
        warning_recall = len(found_warnings & expected_warnings) / len(expected_warnings)
    else:
        warning_recall = 1.0 if not found_warnings else 0.0

    if found_warnings:
        warning_precision = len(found_warnings & expected_warnings) / len(found_warnings)
    else:
        warning_precision = 1.0 if not expected_warnings else 0.0

    # Weighted score (critical issues more important)
    score = (
        0.4 * critical_recall
        + 0.3 * critical_precision
        + 0.2 * warning_recall
        + 0.1 * warning_precision
    )

    return score
