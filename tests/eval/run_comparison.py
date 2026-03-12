"""
Main evaluation runner for comparing repo-brain vs regular vs SME agents.

Usage:
    python tests/eval/run_comparison.py --test-suite search --output results/
    python tests/eval/run_comparison.py --test-suite all --scenarios repo-brain,sme-agents
"""

import argparse
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any

from metrics import (
    EvaluationResult,
    PerformanceMetrics,
    ScenarioType,
    SMEAgentMetrics,
    TaskCompletionMetrics,
    calculate_retrieval_metrics,
    calculate_scope_metrics,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class EvaluationRunner:
    """Orchestrates evaluation across different scenarios"""

    def __init__(self, output_dir: Path, repo_path: Path, repo_name: str | None = None):
        self.output_dir = output_dir
        self.repo_path = repo_path
        self.repo_name = repo_name or repo_path.name
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run_test_suite(
        self, test_suite: str, scenarios: list[ScenarioType]
    ) -> list[EvaluationResult]:
        """Run a test suite across all scenarios"""
        logger.info(f"Running test suite: {test_suite}")
        all_results = []

        # Load test cases
        test_cases = self._load_test_cases(test_suite)
        logger.info(f"Loaded {len(test_cases)} test cases")

        for scenario in scenarios:
            logger.info(f"Running scenario: {scenario.value}")
            for test_case in test_cases:
                result = self._run_single_test(test_case, scenario)
                all_results.append(result)
                result.save(self.output_dir)

        return all_results

    def _load_test_cases(self, test_suite: str) -> list[dict[str, Any]]:
        """Load test cases from dataset files"""
        dataset_file = Path(__file__).parent / "datasets" / f"{test_suite}.json"
        if not dataset_file.exists():
            logger.warning(f"Dataset file not found: {dataset_file}")
            return []

        with open(dataset_file) as f:
            data = json.load(f)
            return data.get("test_cases", [])

    def _run_single_test(
        self, test_case: dict[str, Any], scenario: ScenarioType
    ) -> EvaluationResult:
        """Run a single test case in the given scenario"""
        test_type = test_case["type"]
        test_id = test_case["id"]

        logger.info(f"Running {test_id} in {scenario.value}")

        # Create result object
        result = EvaluationResult(
            test_id=test_id,
            scenario=scenario,
            test_type=test_type,
            description=test_case.get("description", ""),
            ground_truth=test_case.get("ground_truth", {}),
            metadata=test_case.get("metadata", {}),
        )

        # Route to appropriate test executor
        start_time = time.time()
        if test_type == "search":
            result = self._run_search_test(test_case, scenario, result)
        elif test_type == "scope":
            result = self._run_scope_test(test_case, scenario, result)
        elif test_type == "task":
            result = self._run_task_test(test_case, scenario, result)
        elif test_type == "code_review":
            result = self._run_code_review_test(test_case, scenario, result)
        else:
            logger.warning(f"Unknown test type: {test_type}")

        # Add performance metrics
        elapsed_time = time.time() - start_time
        if not result.performance:
            result.performance = PerformanceMetrics()
        result.performance.p50_latency_ms = elapsed_time * 1000

        return result

    def _run_search_test(
        self,
        test_case: dict[str, Any],
        scenario: ScenarioType,
        result: EvaluationResult,
    ) -> EvaluationResult:
        """Run semantic search evaluation"""
        query = test_case["query"]
        ground_truth = test_case["ground_truth"]
        relevant_chunks = set(ground_truth.get("relevant_chunks", []))

        if scenario == ScenarioType.REPO_BRAIN:
            # Use repo-brain search
            retrieved, scores = self._repo_brain_search(query)
        elif scenario == ScenarioType.REGULAR:
            # Use regular grep/ripgrep
            retrieved, scores = self._regular_search(query)
        else:  # SME_AGENTS
            # SME agents don't do semantic search - use repo-brain as baseline
            retrieved, scores = self._repo_brain_search(query)

        # Calculate metrics
        relevance_scores = ground_truth.get("relevance_scores", {})
        result.retrieval = calculate_retrieval_metrics(
            retrieved=retrieved,
            relevant=relevant_chunks,
            relevance_scores=relevance_scores if relevance_scores else None,
            similarity_scores=scores,
        )
        result.raw_output = json.dumps({"retrieved": retrieved, "scores": scores}, indent=2)

        return result

    def _repo_brain_search(self, query: str) -> tuple[list[str], list[float]]:
        """Execute repo-brain semantic search"""
        try:
            cmd = ["repo-brain", "search", "-r", self.repo_name, "-l", "10", query]
            output = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)

            # Parse repo-brain output
            # Format: [1] file.py — fragment: lines_X_Y (service)
            #         Score: 0.xxxx  Lines: X-Y
            retrieved = []
            scores = []

            import re

            # Match patterns like:
            # [1] services/auth-service/utils/jwt.go — fragment: lines_96_195
            # Score: 0.6444
            file_pattern = r"\[\d+\]\s+(.*?)\s+—"
            score_pattern = r"Score:\s+([\d.]+)"

            lines = output.split("\n")
            current_file = None

            for line in lines:
                # Extract file path
                file_match = re.search(file_pattern, line)
                if file_match:
                    current_file = file_match.group(1)

                # Extract score
                score_match = re.search(score_pattern, line)
                if score_match and current_file:
                    score = float(score_match.group(1))
                    retrieved.append(current_file)
                    scores.append(score)
                    current_file = None  # Reset for next result

            return retrieved, scores
        except subprocess.CalledProcessError as e:
            logger.error(f"repo-brain search failed: {e}")
            return [], []

    def _regular_search(self, query: str) -> tuple[list[str], list[float]]:
        """Execute regular grep-based search with multi-word query support"""
        try:
            # Split query into keywords and search for each
            # Use the first keyword as the main search term
            keywords = query.split()
            if not keywords:
                return [], []

            # Search for the first keyword
            cmd = [
                "rg",
                "--files-with-matches",
                "--no-heading",
                "--color=never",
                keywords[0],
                str(self.repo_path),
            ]
            output = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)

            # Parse file paths and make them relative to repo root
            retrieved = []
            if output.strip():
                for line in output.strip().split("\n"):
                    # Make paths relative to repo_path
                    abs_path = Path(line).resolve()
                    try:
                        rel_path = abs_path.relative_to(self.repo_path.resolve())
                        rel_path_str = str(rel_path)

                        # If there are multiple keywords, filter files that contain other keywords too
                        if len(keywords) > 1:
                            try:
                                content = abs_path.read_text(errors="ignore")
                                # Check if file contains other keywords (case insensitive)
                                content_lower = content.lower()
                                if all(kw.lower() in content_lower for kw in keywords[1:]):
                                    retrieved.append(rel_path_str)
                            except Exception:
                                # If we can't read the file, include it anyway
                                retrieved.append(rel_path_str)
                        else:
                            retrieved.append(rel_path_str)
                    except ValueError:
                        # If path is not relative to repo, skip it
                        pass

            # No similarity scores for grep, all matches are equally relevant
            scores = [1.0] * len(retrieved)

            return retrieved, scores
        except subprocess.CalledProcessError:
            # No matches found
            return [], []

    def _run_scope_test(
        self,
        test_case: dict[str, Any],
        scenario: ScenarioType,
        result: EvaluationResult,
    ) -> EvaluationResult:
        """Run scope analysis evaluation"""
        description = test_case["description"]
        ground_truth = test_case["ground_truth"]

        if scenario == ScenarioType.REPO_BRAIN:
            predicted = self._repo_brain_scope(description)
        elif scenario == ScenarioType.REGULAR:
            predicted = self._regular_scope(description)
        else:  # SME_AGENTS
            predicted = self._sme_scope(description)

        # Calculate metrics
        result.scope_analysis = calculate_scope_metrics(
            predicted_files=set(predicted.get("files", [])),
            ground_truth_files=set(ground_truth.get("files", [])),
            predicted_services=set(predicted.get("services", [])),
            ground_truth_services=set(ground_truth.get("services", [])),
            predicted_deps=set(predicted.get("dependencies", [])),
            ground_truth_deps=set(ground_truth.get("dependencies", [])),
        )
        result.raw_output = json.dumps(predicted, indent=2)

        return result

    def _repo_brain_scope(self, description: str) -> dict[str, Any]:
        """Execute repo-brain scope analysis"""
        try:
            cmd = ["repo-brain", "scope", "-r", self.repo_name, description]
            output = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)

            # Parse scope output
            # Format:
            # ### Affected Services
            # - **rest-api** (20 matches)
            #
            # ### Key Files
            # - `services/rest-api/app/src/.../file.py` — Description

            import re

            services = []
            files = []

            # Extract services: - **service-name** (N matches)
            service_pattern = r"-\s+\*\*([a-z0-9-]+)\*\*"
            for match in re.finditer(service_pattern, output):
                services.append(match.group(1))

            # Extract files: - `filepath` —
            file_pattern = r"-\s+`([^`]+)`\s+—"
            for match in re.finditer(file_pattern, output):
                files.append(match.group(1))

            # Dependencies not directly shown in scope output
            # Would need to parse dependency graph separately
            return {"files": files, "services": services, "dependencies": []}
        except subprocess.CalledProcessError as e:
            logger.error(f"repo-brain scope failed: {e}")
            return {"files": [], "services": [], "dependencies": []}

    def _regular_scope(self, description: str) -> dict[str, Any]:
        """Manual scope analysis (baseline)"""
        # In regular scenario, user would manually identify files
        # For evaluation, this would need to be pre-computed
        return {"files": [], "services": [], "dependencies": []}

    def _sme_scope(self, description: str) -> dict[str, Any]:
        """SME agent-assisted scope analysis"""
        # This would involve invoking SME agents through OpenCode
        # For now, placeholder
        return {"files": [], "services": [], "dependencies": []}

    def _run_task_test(
        self,
        test_case: dict[str, Any],
        scenario: ScenarioType,
        result: EvaluationResult,
    ) -> EvaluationResult:
        """Run task completion evaluation"""
        task_description = test_case["task"]
        test_case["ground_truth"]

        # Task completion requires manual/LLM evaluation
        # For now, create placeholder metrics
        result.task_completion = TaskCompletionMetrics()
        result.raw_output = f"Task: {task_description}"

        return result

    def _run_code_review_test(
        self,
        test_case: dict[str, Any],
        scenario: ScenarioType,
        result: EvaluationResult,
    ) -> EvaluationResult:
        """Run code review evaluation (SME agents specific)"""
        pr_number = test_case.get("pr_number")
        files_changed = test_case.get("files_changed", [])
        test_case["ground_truth"]

        if scenario == ScenarioType.SME_AGENTS:
            # Invoke appropriate SME agents
            sme_results = self._invoke_sme_agents(files_changed, pr_number)
            result.sme_agents = sme_results
        else:
            # Non-SME scenarios don't have code review capability
            result.sme_agents = SMEAgentMetrics()

        result.raw_output = json.dumps(result.sme_agents.to_dict(), indent=2)
        return result

    def _invoke_sme_agents(
        self, files_changed: list[str], pr_number: str | None = None
    ) -> SMEAgentMetrics:
        """Invoke appropriate SME agents based on files changed"""
        from sme_invoker import (
            determine_sme_agents,
            invoke_sme_agent_via_git,
        )

        metrics = SMEAgentMetrics()

        # Determine which agents to invoke
        agents_to_invoke = determine_sme_agents(files_changed)
        metrics.agents_invoked = agents_to_invoke

        # Invoke each agent and collect results
        review_quality = {}
        time_per_agent = {}

        for agent_name in agents_to_invoke:
            logger.info(f"Invoking SME agent: @{agent_name}")

            start_time = time.time()

            # Invoke agent (uses git diff analysis)
            review_result = invoke_sme_agent_via_git(
                agent_name=agent_name, repo_path=self.repo_path, pr_number=pr_number
            )

            elapsed = time.time() - start_time
            time_per_agent[agent_name] = elapsed

            # Calculate quality score (requires ground truth in test case)
            # For now, use a simple heuristic based on issues found
            if review_result.get("review_completed"):
                issues_found = len(review_result.get("issues_found", []))
                # Quality score based on thoroughness (placeholder)
                review_quality[agent_name] = min(1.0, issues_found / 5.0)
            else:
                review_quality[agent_name] = 0.0

        metrics.review_quality = review_quality
        metrics.time_per_agent = time_per_agent

        # Calculate aggregate metrics
        if agents_to_invoke:
            metrics.agent_selection_accuracy = 1.0  # Placeholder - needs ground truth
            metrics.issue_coverage = sum(review_quality.values()) / len(review_quality)
            metrics.false_positive_rate = 0.0  # Placeholder - needs ground truth

        return metrics


def main():
    parser = argparse.ArgumentParser(
        description="Run comparison evaluation between repo-brain, regular, and SME agents"
    )
    parser.add_argument(
        "--test-suite",
        choices=["search", "scope", "task", "code_review", "all"],
        default="all",
        help="Which test suite to run",
    )
    parser.add_argument(
        "--scenarios",
        default="repo-brain,regular,sme-agents",
        help="Comma-separated list of scenarios to test",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tests/eval/results"),
        help="Output directory for results",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="Repository path to evaluate",
    )
    parser.add_argument(
        "--repo-name",
        type=str,
        help="Registered repository name in repo-brain (defaults to repo directory name)",
    )

    args = parser.parse_args()

    # Parse scenarios
    scenario_names = args.scenarios.split(",")
    scenarios = [ScenarioType(name.strip()) for name in scenario_names]

    # Create runner
    runner = EvaluationRunner(output_dir=args.output, repo_path=args.repo, repo_name=args.repo_name)

    # Run evaluation
    if args.test_suite == "all":
        test_suites = ["search", "scope", "task", "code_review"]
    else:
        test_suites = [args.test_suite]

    all_results = []
    for suite in test_suites:
        results = runner.run_test_suite(suite, scenarios)
        all_results.extend(results)

    logger.info(f"Completed {len(all_results)} evaluations")
    logger.info(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
