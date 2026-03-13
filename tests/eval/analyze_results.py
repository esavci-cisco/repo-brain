"""
Results analyzer for comparing scenarios.

Loads evaluation results and generates comparison reports with statistics and visualizations.
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


class ResultsAnalyzer:
    """Analyze and compare evaluation results across scenarios"""

    def __init__(self, results_dir: Path):
        self.results_dir = results_dir
        self.results = self._load_results()

    def _load_results(self) -> list[dict[str, Any]]:
        """Load all result JSON files"""
        results = []
        for json_file in self.results_dir.glob("*.json"):
            with open(json_file) as f:
                results.append(json.load(f))
        return results

    def generate_summary_report(self) -> str:
        """Generate a text summary report comparing scenarios"""
        if not self.results:
            return "No results found."

        report = ["# Evaluation Summary Report\n"]

        # Group by scenario
        by_scenario = defaultdict(list)
        for result in self.results:
            by_scenario[result["scenario"]].append(result)

        report.append(f"Total evaluations: {len(self.results)}\n")
        report.append(f"Scenarios compared: {', '.join(by_scenario.keys())}\n")

        # Summary statistics per scenario
        report.append("\n## Overall Statistics by Scenario\n")
        for scenario, results in by_scenario.items():
            report.append(f"\n### {scenario.upper()}\n")
            report.append(f"- Total tests: {len(results)}\n")

            # Count by test type
            by_type = defaultdict(int)
            for r in results:
                by_type[r["test_type"]] += 1

            report.append("- Tests by type:\n")
            for test_type, count in by_type.items():
                report.append(f"  - {test_type}: {count}\n")

        # Retrieval metrics comparison
        report.append("\n## Retrieval Metrics (Search Tests)\n")
        retrieval_data = self._aggregate_retrieval_metrics(by_scenario)
        report.append(self._format_retrieval_table(retrieval_data))

        # Scope analysis comparison
        report.append("\n## Scope Analysis Metrics\n")
        scope_data = self._aggregate_scope_metrics(by_scenario)
        report.append(self._format_scope_table(scope_data))

        # SME agent analysis
        if any(r["scenario"] == "sme-agents" for r in self.results):
            report.append("\n## SME Agent Metrics\n")
            sme_data = self._aggregate_sme_metrics(by_scenario)
            report.append(self._format_sme_table(sme_data))

        # Performance comparison
        report.append("\n## Performance Comparison\n")
        perf_data = self._aggregate_performance_metrics(by_scenario)
        report.append(self._format_performance_table(perf_data))

        return "".join(report)

    def _aggregate_retrieval_metrics(self, by_scenario: dict[str, list]) -> dict[str, dict]:
        """Aggregate retrieval metrics per scenario"""
        aggregated = {}
        for scenario, results in by_scenario.items():
            search_results = [
                r for r in results if r["test_type"] == "search" and r["metrics"]["retrieval"]
            ]
            if not search_results:
                continue

            metrics = {
                "precision@1": [],
                "precision@3": [],
                "recall@1": [],
                "recall@3": [],
                "mrr": [],
                "ndcg@3": [],
            }

            for r in search_results:
                ret = r["metrics"]["retrieval"]
                metrics["precision@1"].append(ret["precision@1"])
                metrics["precision@3"].append(ret["precision@3"])
                metrics["recall@1"].append(ret["recall@1"])
                metrics["recall@3"].append(ret["recall@3"])
                metrics["mrr"].append(ret["mrr"])
                metrics["ndcg@3"].append(ret["ndcg@3"])

            # Calculate averages
            aggregated[scenario] = {
                metric: sum(values) / len(values) if values else 0.0
                for metric, values in metrics.items()
            }
            aggregated[scenario]["count"] = len(search_results)

        return aggregated

    def _format_retrieval_table(self, data: dict[str, dict]) -> str:
        """Format retrieval metrics as markdown table"""
        if not data:
            return "_No search test results found._\n"

        lines = [
            "| Scenario | Count | P@1 | P@3 | R@1 | R@3 | MRR | NDCG@3 |",
            "|----------|-------|-----|-----|-----|-----|-----|--------|",
        ]

        for scenario, metrics in data.items():
            lines.append(
                f"| {scenario} | {metrics['count']} | "
                f"{metrics['precision@1']:.3f} | {metrics['precision@3']:.3f} | "
                f"{metrics['recall@1']:.3f} | {metrics['recall@3']:.3f} | "
                f"{metrics['mrr']:.3f} | {metrics['ndcg@3']:.3f} |"
            )

        return "\n".join(lines) + "\n"

    def _aggregate_scope_metrics(self, by_scenario: dict[str, list]) -> dict[str, dict]:
        """Aggregate scope analysis metrics per scenario"""
        aggregated = {}
        for scenario, results in by_scenario.items():
            scope_results = [
                r for r in results if r["test_type"] == "scope" and r["metrics"]["scope_analysis"]
            ]
            if not scope_results:
                continue

            files_p, files_r, files_f1 = [], [], []
            services_p, services_r, services_f1 = [], [], []

            for r in scope_results:
                scope = r["metrics"]["scope_analysis"]
                files_p.append(scope["files"]["precision"])
                files_r.append(scope["files"]["recall"])
                files_f1.append(scope["files"]["f1"])
                services_p.append(scope["services"]["precision"])
                services_r.append(scope["services"]["recall"])
                services_f1.append(scope["services"]["f1"])

            aggregated[scenario] = {
                "count": len(scope_results),
                "files_f1": sum(files_f1) / len(files_f1) if files_f1 else 0.0,
                "services_f1": sum(services_f1) / len(services_f1) if services_f1 else 0.0,
            }

        return aggregated

    def _format_scope_table(self, data: dict[str, dict]) -> str:
        """Format scope metrics as markdown table"""
        if not data:
            return "_No scope test results found._\n"

        lines = [
            "| Scenario | Count | Files F1 | Services F1 |",
            "|----------|-------|----------|-------------|",
        ]

        for scenario, metrics in data.items():
            lines.append(
                f"| {scenario} | {metrics['count']} | "
                f"{metrics['files_f1']:.3f} | {metrics['services_f1']:.3f} |"
            )

        return "\n".join(lines) + "\n"

    def _aggregate_sme_metrics(self, by_scenario: dict[str, list]) -> dict[str, dict]:
        """Aggregate SME agent metrics"""
        aggregated = {}
        sme_results = by_scenario.get("sme-agents", [])

        if not sme_results:
            return aggregated

        review_results = [
            r for r in sme_results if r["test_type"] == "code_review" and r["metrics"]["sme_agents"]
        ]

        if not review_results:
            return aggregated

        total_agents = []
        agent_counts = defaultdict(int)

        for r in review_results:
            sme = r["metrics"]["sme_agents"]
            agents = sme.get("agents_invoked", [])
            total_agents.append(len(agents))
            for agent in agents:
                agent_counts[agent] += 1

        aggregated["sme-agents"] = {
            "count": len(review_results),
            "avg_agents_per_review": (
                sum(total_agents) / len(total_agents) if total_agents else 0.0
            ),
            "agent_usage": dict(agent_counts),
        }

        return aggregated

    def _format_sme_table(self, data: dict[str, dict]) -> str:
        """Format SME metrics as text"""
        if not data:
            return "_No SME agent results found._\n"

        lines = []
        for scenario, metrics in data.items():
            lines.append(f"- Total code reviews: {metrics['count']}\n")
            lines.append(f"- Avg agents per review: {metrics['avg_agents_per_review']:.2f}\n")
            lines.append("- Agent usage breakdown:\n")
            for agent, count in sorted(
                metrics["agent_usage"].items(), key=lambda x: x[1], reverse=True
            ):
                lines.append(f"  - @{agent}: {count} times\n")

        return "".join(lines)

    def _aggregate_performance_metrics(self, by_scenario: dict[str, list]) -> dict[str, dict]:
        """Aggregate performance metrics per scenario"""
        aggregated = {}
        for scenario, results in by_scenario.items():
            perf_results = [r for r in results if r["metrics"]["performance"]]
            if not perf_results:
                continue

            latencies = []
            token_counts = []

            for r in perf_results:
                perf = r["metrics"]["performance"]
                if perf.get("latency", {}).get("p50_ms"):
                    latencies.append(perf["latency"]["p50_ms"])
                if perf.get("tokens", {}).get("total"):
                    token_counts.append(perf["tokens"]["total"])

            aggregated[scenario] = {
                "count": len(perf_results),
                "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
                "avg_tokens": sum(token_counts) / len(token_counts) if token_counts else 0.0,
            }

        return aggregated

    def _format_performance_table(self, data: dict[str, dict]) -> str:
        """Format performance metrics as markdown table"""
        if not data:
            return "_No performance metrics found._\n"

        lines = [
            "| Scenario | Count | Avg Latency (ms) | Avg Tokens |",
            "|----------|-------|------------------|------------|",
        ]

        for scenario, metrics in data.items():
            lines.append(
                f"| {scenario} | {metrics['count']} | "
                f"{metrics['avg_latency_ms']:.1f} | {metrics['avg_tokens']:.0f} |"
            )

        return "\n".join(lines) + "\n"

    def export_to_csv(self, output_file: Path):
        """Export results to CSV for further analysis"""
        rows = []
        for result in self.results:
            row = {
                "test_id": result["test_id"],
                "scenario": result["scenario"],
                "test_type": result["test_type"],
                "description": result["description"],
            }

            # Add retrieval metrics
            if result["metrics"].get("retrieval"):
                ret = result["metrics"]["retrieval"]
                row.update(
                    {
                        "precision@1": ret["precision@1"],
                        "precision@3": ret["precision@3"],
                        "recall@1": ret["recall@1"],
                        "recall@3": ret["recall@3"],
                        "mrr": ret["mrr"],
                    }
                )

            # Add scope metrics
            if result["metrics"].get("scope_analysis"):
                scope = result["metrics"]["scope_analysis"]
                row.update(
                    {
                        "files_f1": scope["files"]["f1"],
                        "services_f1": scope["services"]["f1"],
                    }
                )

            # Add performance metrics
            if result["metrics"].get("performance"):
                perf = result["metrics"]["performance"]
                row.update(
                    {
                        "latency_ms": perf.get("latency", {}).get("p50_ms", 0),
                        "tokens": perf.get("tokens", {}).get("total", 0),
                    }
                )

            rows.append(row)

        df = pd.DataFrame(rows)
        df.to_csv(output_file, index=False)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Analyze evaluation results")
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("tests/eval/results"),
        help="Directory containing result JSON files",
    )
    parser.add_argument(
        "--output-report",
        type=Path,
        default=Path("tests/eval/results/summary_report.md"),
        help="Output file for summary report",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("tests/eval/results/results.csv"),
        help="Output CSV file",
    )

    args = parser.parse_args()

    # Analyze results
    analyzer = ResultsAnalyzer(args.results_dir)

    # Generate report
    report = analyzer.generate_summary_report()
    with open(args.output_report, "w") as f:
        f.write(report)
    print(f"Summary report written to {args.output_report}")

    # Export to CSV
    try:
        analyzer.export_to_csv(args.output_csv)
        print(f"CSV export written to {args.output_csv}")
    except ImportError:
        print("pandas not installed - skipping CSV export")


if __name__ == "__main__":
    main()
