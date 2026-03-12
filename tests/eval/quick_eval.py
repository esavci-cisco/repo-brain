#!/usr/bin/env python3
"""
Quick start script for running evaluations.

This script provides a simple interface for common evaluation workflows.
"""

import subprocess
import sys
from pathlib import Path


def print_header(text):
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def run_full_evaluation(repo_path: str):
    """Run complete evaluation across all scenarios"""
    print_header("Running Full Evaluation Suite")

    # Step 1: Run search evaluation
    print("Step 1/5: Running search evaluation...")
    subprocess.run(
        [
            sys.executable,
            "tests/eval/run_comparison.py",
            "--test-suite",
            "search",
            "--scenarios",
            "repo-brain,regular",
            "--repo",
            repo_path,
        ],
        check=True,
    )

    # Step 2: Run scope evaluation
    print("\nStep 2/5: Running scope evaluation...")
    subprocess.run(
        [
            sys.executable,
            "tests/eval/run_comparison.py",
            "--test-suite",
            "scope",
            "--scenarios",
            "repo-brain,regular",
            "--repo",
            repo_path,
        ],
        check=True,
    )

    # Step 3: Run code review evaluation (SME agents)
    print("\nStep 3/5: Running code review evaluation...")
    subprocess.run(
        [
            sys.executable,
            "tests/eval/run_comparison.py",
            "--test-suite",
            "code_review",
            "--scenarios",
            "sme-agents",
            "--repo",
            repo_path,
        ],
        check=True,
    )

    # Step 4: Analyze results
    print("\nStep 4/5: Analyzing results...")
    subprocess.run([sys.executable, "tests/eval/analyze_results.py"], check=True)

    # Step 5: Display report
    print("\nStep 5/5: Generating summary...")
    report_path = Path("tests/eval/results/summary_report.md")
    if report_path.exists():
        print_header("Evaluation Summary")
        with open(report_path) as f:
            print(f.read())
    else:
        print("No summary report generated.")

    print_header("Evaluation Complete!")
    print("Results saved to: tests/eval/results/")
    print("- Summary report: tests/eval/results/summary_report.md")
    print("- CSV export: tests/eval/results/results.csv")
    print("- Individual results: tests/eval/results/*.json")


def run_quick_search_test(repo_path: str):
    """Quick search evaluation only"""
    print_header("Quick Search Evaluation")

    subprocess.run(
        [
            sys.executable,
            "tests/eval/run_comparison.py",
            "--test-suite",
            "search",
            "--scenarios",
            "repo-brain,regular",
            "--repo",
            repo_path,
        ],
        check=True,
    )

    subprocess.run([sys.executable, "tests/eval/analyze_results.py"], check=True)

    print("\nDone! Check tests/eval/results/summary_report.md")


def run_sme_review_test(repo_path: str):
    """SME agent code review evaluation only"""
    print_header("SME Agent Code Review Evaluation")

    subprocess.run(
        [
            sys.executable,
            "tests/eval/run_comparison.py",
            "--test-suite",
            "code_review",
            "--scenarios",
            "sme-agents",
            "--repo",
            repo_path,
        ],
        check=True,
    )

    subprocess.run([sys.executable, "tests/eval/analyze_results.py"], check=True)

    print("\nDone! Check tests/eval/results/summary_report.md")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python tests/eval/quick_eval.py full /path/to/repo")
        print("  python tests/eval/quick_eval.py search /path/to/repo")
        print("  python tests/eval/quick_eval.py sme /path/to/repo")
        sys.exit(1)

    mode = sys.argv[1]
    repo_path = sys.argv[2] if len(sys.argv) > 2 else str(Path.cwd())

    if mode == "full":
        run_full_evaluation(repo_path)
    elif mode == "search":
        run_quick_search_test(repo_path)
    elif mode == "sme":
        run_sme_review_test(repo_path)
    else:
        print(f"Unknown mode: {mode}")
        print("Valid modes: full, search, sme")
        sys.exit(1)


if __name__ == "__main__":
    main()
