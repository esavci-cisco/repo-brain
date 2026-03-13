"""
Metrics collection for comparing repo-brain, regular scenarios, and SME agents.

This module provides metric calculation for three evaluation scenarios:
1. With repo-brain (push architecture with persistent context)
2. Without repo-brain (regular tool-based pull architecture)
3. With SME agents (specialized domain expert agents)
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class ScenarioType(Enum):
    """Three scenarios to compare"""

    REPO_BRAIN = "repo-brain"
    REGULAR = "regular"
    SME_AGENTS = "sme-agents"


@dataclass
class RetrievalMetrics:
    """Metrics for search/retrieval quality (for /q command evaluation)"""

    # Precision@K: What fraction of retrieved chunks are relevant?
    precision_at_1: float = 0.0
    precision_at_3: float = 0.0
    precision_at_5: float = 0.0

    # Recall@K: What fraction of relevant chunks were retrieved?
    recall_at_1: float = 0.0
    recall_at_3: float = 0.0
    recall_at_5: float = 0.0

    # Mean Reciprocal Rank: 1/rank of first relevant result
    mrr: float = 0.0

    # Normalized Discounted Cumulative Gain
    ndcg_at_3: float = 0.0
    ndcg_at_5: float = 0.0

    # Average cosine similarity score
    avg_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "precision@1": self.precision_at_1,
            "precision@3": self.precision_at_3,
            "precision@5": self.precision_at_5,
            "recall@1": self.recall_at_1,
            "recall@3": self.recall_at_3,
            "recall@5": self.recall_at_5,
            "mrr": self.mrr,
            "ndcg@3": self.ndcg_at_3,
            "ndcg@5": self.ndcg_at_5,
            "avg_score": self.avg_score,
        }


@dataclass
class TaskCompletionMetrics:
    """Metrics for task completion quality"""

    # Did the task complete successfully?
    success: bool = False

    # Was the solution correct?
    correctness_score: float = 0.0  # 0.0 to 1.0

    # Time taken to complete (seconds)
    time_to_completion: float = 0.0

    # Number of tool calls / agent invocations
    tool_calls: int = 0

    # Total tokens used (if tracking LLM usage)
    total_tokens: int = 0

    # Number of edits/retries needed
    iterations: int = 1

    # Human evaluation score (optional)
    human_score: float | None = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "correctness": self.correctness_score,
            "time_seconds": self.time_to_completion,
            "tool_calls": self.tool_calls,
            "total_tokens": self.total_tokens,
            "iterations": self.iterations,
            "human_score": self.human_score,
        }


@dataclass
class ScopeAnalysisMetrics:
    """Metrics for /scope command evaluation"""

    # Did it identify the correct files?
    files_precision: float = 0.0  # Correct files / Total suggested
    files_recall: float = 0.0  # Correct files / Total relevant
    files_f1: float = 0.0

    # Did it identify the correct services?
    services_precision: float = 0.0
    services_recall: float = 0.0
    services_f1: float = 0.0

    # Did it identify the correct dependencies?
    dependencies_precision: float = 0.0
    dependencies_recall: float = 0.0
    dependencies_f1: float = 0.0

    # Risk assessment accuracy
    risk_assessment_accuracy: float = 0.0  # 0.0 to 1.0

    def to_dict(self) -> dict:
        return {
            "files": {
                "precision": self.files_precision,
                "recall": self.files_recall,
                "f1": self.files_f1,
            },
            "services": {
                "precision": self.services_precision,
                "recall": self.services_recall,
                "f1": self.services_f1,
            },
            "dependencies": {
                "precision": self.dependencies_precision,
                "recall": self.dependencies_recall,
                "f1": self.dependencies_f1,
            },
            "risk_accuracy": self.risk_assessment_accuracy,
        }


@dataclass
class CodeUnderstandingMetrics:
    """Metrics for understanding codebase structure"""

    # Architectural understanding score (0.0 to 1.0)
    architecture_score: float = 0.0

    # Dependency identification accuracy
    dependency_accuracy: float = 0.0

    # Pattern recognition accuracy
    pattern_recognition: float = 0.0

    # Context relevance (was the right context used?)
    context_relevance: float = 0.0

    def to_dict(self) -> dict:
        return {
            "architecture": self.architecture_score,
            "dependencies": self.dependency_accuracy,
            "patterns": self.pattern_recognition,
            "context_relevance": self.context_relevance,
        }


@dataclass
class SMEAgentMetrics:
    """Metrics specific to SME agent evaluation"""

    # Which SME agents were invoked?
    agents_invoked: list[str] = field(default_factory=list)

    # Were the correct SME agents chosen?
    agent_selection_accuracy: float = 0.0

    # Review quality score per agent
    review_quality: dict[str, float] = field(default_factory=dict)

    # Coverage: did agents catch all issues?
    issue_coverage: float = 0.0

    # False positive rate: issues flagged incorrectly
    false_positive_rate: float = 0.0

    # Time per agent
    time_per_agent: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "agents_invoked": self.agents_invoked,
            "selection_accuracy": self.agent_selection_accuracy,
            "review_quality": self.review_quality,
            "issue_coverage": self.issue_coverage,
            "false_positive_rate": self.false_positive_rate,
            "time_per_agent": self.time_per_agent,
        }


@dataclass
class PerformanceMetrics:
    """Performance and resource usage metrics"""

    # Latency percentiles (milliseconds)
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0

    # Token usage
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    # Memory usage (MB)
    memory_usage_mb: float = 0.0

    # Context size in prompt (tokens)
    context_tokens: int = 0

    def to_dict(self) -> dict:
        return {
            "latency": {
                "p50_ms": self.p50_latency_ms,
                "p95_ms": self.p95_latency_ms,
                "p99_ms": self.p99_latency_ms,
            },
            "tokens": {
                "prompt": self.prompt_tokens,
                "completion": self.completion_tokens,
                "total": self.total_tokens,
                "context": self.context_tokens,
            },
            "memory_mb": self.memory_usage_mb,
        }


@dataclass
class EvaluationResult:
    """Complete evaluation result for a single test case"""

    # Metadata
    test_id: str
    scenario: ScenarioType
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    test_type: str = ""  # "search", "task", "scope", "code_review", etc.
    description: str = ""

    # Metrics
    retrieval: RetrievalMetrics | None = None
    task_completion: TaskCompletionMetrics | None = None
    scope_analysis: ScopeAnalysisMetrics | None = None
    code_understanding: CodeUnderstandingMetrics | None = None
    sme_agents: SMEAgentMetrics | None = None
    performance: PerformanceMetrics | None = None

    # Raw results for manual inspection
    raw_output: str = ""
    ground_truth: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "test_id": self.test_id,
            "scenario": self.scenario.value,
            "timestamp": self.timestamp,
            "test_type": self.test_type,
            "description": self.description,
            "metrics": {
                "retrieval": self.retrieval.to_dict() if self.retrieval else None,
                "task_completion": (
                    self.task_completion.to_dict() if self.task_completion else None
                ),
                "scope_analysis": (self.scope_analysis.to_dict() if self.scope_analysis else None),
                "code_understanding": (
                    self.code_understanding.to_dict() if self.code_understanding else None
                ),
                "sme_agents": self.sme_agents.to_dict() if self.sme_agents else None,
                "performance": self.performance.to_dict() if self.performance else None,
            },
            "raw_output": self.raw_output,
            "ground_truth": self.ground_truth,
            "metadata": self.metadata,
        }

    def save(self, output_dir: Path) -> Path:
        """Save result to JSON file"""
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{self.test_id}_{self.scenario.value}_{self.timestamp}.json"
        filepath = output_dir / filename
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return filepath


# Metric calculation functions


def calculate_precision_recall_f1(predicted: set, ground_truth: set) -> tuple[float, float, float]:
    """Calculate precision, recall, and F1 score"""
    if not predicted:
        return 0.0, 0.0, 0.0
    if not ground_truth:
        return 0.0, 0.0, 0.0

    true_positives = len(predicted & ground_truth)
    precision = true_positives / len(predicted) if predicted else 0.0
    recall = true_positives / len(ground_truth) if ground_truth else 0.0

    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * (precision * recall) / (precision + recall)

    return precision, recall, f1


def calculate_precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Calculate Precision@K for retrieval"""
    retrieved_at_k = retrieved[:k]
    relevant_at_k = [doc for doc in retrieved_at_k if doc in relevant]
    return len(relevant_at_k) / k if k > 0 else 0.0


def calculate_recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Calculate Recall@K for retrieval"""
    if not relevant:
        return 0.0
    retrieved_at_k = set(retrieved[:k])
    relevant_retrieved = retrieved_at_k & relevant
    return len(relevant_retrieved) / len(relevant)


def calculate_mrr(retrieved: list[str], relevant: set[str]) -> float:
    """Calculate Mean Reciprocal Rank"""
    for i, doc in enumerate(retrieved, 1):
        if doc in relevant:
            return 1.0 / i
    return 0.0


def calculate_ndcg_at_k(retrieved: list[str], relevance_scores: dict[str, float], k: int) -> float:
    """
    Calculate Normalized Discounted Cumulative Gain@K

    relevance_scores: dict mapping document_id -> relevance (0.0 to 1.0)
    """
    import math

    if k == 0:
        return 0.0

    # DCG: sum of (relevance / log2(rank+1))
    dcg = 0.0
    for i, doc in enumerate(retrieved[:k], 1):
        rel = relevance_scores.get(doc, 0.0)
        dcg += rel / math.log2(i + 1)

    # IDCG: DCG of perfect ranking
    sorted_relevances = sorted(relevance_scores.values(), reverse=True)[:k]
    idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(sorted_relevances))

    return dcg / idcg if idcg > 0 else 0.0


def calculate_retrieval_metrics(
    retrieved: list[str],
    relevant: set[str],
    relevance_scores: dict[str, float] | None = None,
    similarity_scores: list[float] | None = None,
) -> RetrievalMetrics:
    """Calculate all retrieval metrics"""
    metrics = RetrievalMetrics()

    # Precision@K
    metrics.precision_at_1 = calculate_precision_at_k(retrieved, relevant, 1)
    metrics.precision_at_3 = calculate_precision_at_k(retrieved, relevant, 3)
    metrics.precision_at_5 = calculate_precision_at_k(retrieved, relevant, 5)

    # Recall@K
    metrics.recall_at_1 = calculate_recall_at_k(retrieved, relevant, 1)
    metrics.recall_at_3 = calculate_recall_at_k(retrieved, relevant, 3)
    metrics.recall_at_5 = calculate_recall_at_k(retrieved, relevant, 5)

    # MRR
    metrics.mrr = calculate_mrr(retrieved, relevant)

    # NDCG (if relevance scores provided)
    if relevance_scores:
        metrics.ndcg_at_3 = calculate_ndcg_at_k(retrieved, relevance_scores, 3)
        metrics.ndcg_at_5 = calculate_ndcg_at_k(retrieved, relevance_scores, 5)

    # Average similarity score
    if similarity_scores:
        metrics.avg_score = sum(similarity_scores) / len(similarity_scores)

    return metrics


def calculate_scope_metrics(
    predicted_files: set[str],
    ground_truth_files: set[str],
    predicted_services: set[str],
    ground_truth_services: set[str],
    predicted_deps: set[str],
    ground_truth_deps: set[str],
) -> ScopeAnalysisMetrics:
    """Calculate scope analysis metrics"""
    metrics = ScopeAnalysisMetrics()

    # Files
    metrics.files_precision, metrics.files_recall, metrics.files_f1 = calculate_precision_recall_f1(
        predicted_files, ground_truth_files
    )

    # Services
    metrics.services_precision, metrics.services_recall, metrics.services_f1 = (
        calculate_precision_recall_f1(predicted_services, ground_truth_services)
    )

    # Dependencies
    metrics.dependencies_precision, metrics.dependencies_recall, metrics.dependencies_f1 = (
        calculate_precision_recall_f1(predicted_deps, ground_truth_deps)
    )

    return metrics
