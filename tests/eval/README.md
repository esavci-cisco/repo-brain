# Evaluation Framework for repo-brain Comparison

This directory contains a comprehensive evaluation framework for comparing three scenarios:

1. **repo-brain** - Push architecture with persistent context (repo map + semantic search)
2. **regular** - Traditional pull architecture (grep/ripgrep, no persistent context)
3. **sme-agents** - Specialized SME (Subject Matter Expert) agents from OpenCode

## Directory Structure

```
tests/eval/
├── metrics.py              # Metrics definitions and calculation functions
├── run_comparison.py       # Main evaluation runner
├── analyze_results.py      # Results analysis and reporting
├── datasets/               # Test case definitions
│   ├── search.json         # Semantic search test cases
│   ├── scope.json          # Scope analysis test cases
│   └── code_review.json    # Code review test cases (SME agents)
├── scenarios/              # Scenario-specific configurations
└── results/                # Evaluation results (JSON + reports)
```

## Quick Start

### 1. Run Search Evaluation

Compare semantic search quality across scenarios:

```bash
python tests/eval/run_comparison.py \
  --test-suite search \
  --scenarios repo-brain,regular \
  --repo /path/to/repo \
  --output tests/eval/results
```

### 2. Run Scope Analysis Evaluation

Compare task scoping accuracy:

```bash
python tests/eval/run_comparison.py \
  --test-suite scope \
  --scenarios repo-brain,regular \
  --repo /path/to/repo
```

### 3. Run Code Review Evaluation

Evaluate SME agent code review quality:

```bash
python tests/eval/run_comparison.py \
  --test-suite code_review \
  --scenarios sme-agents \
  --repo /path/to/repo
```

### 4. Run Full Evaluation

Test all scenarios across all test suites:

```bash
python tests/eval/run_comparison.py \
  --test-suite all \
  --scenarios repo-brain,regular,sme-agents \
  --repo /path/to/repo
```

### 5. Analyze Results

Generate summary report and CSV export:

```bash
python tests/eval/analyze_results.py \
  --results-dir tests/eval/results \
  --output-report tests/eval/results/summary_report.md \
  --output-csv tests/eval/results/results.csv
```

## Metrics

### Retrieval Metrics (Search Tests)

Measures semantic search quality:

- **Precision@K**: Fraction of retrieved chunks that are relevant
- **Recall@K**: Fraction of relevant chunks that were retrieved
- **MRR**: Mean Reciprocal Rank (rank of first relevant result)
- **NDCG@K**: Normalized Discounted Cumulative Gain (ranking quality)
- **Avg Score**: Average similarity score

### Scope Analysis Metrics

Measures task scoping accuracy:

- **Files Precision/Recall/F1**: Accuracy of identifying affected files
- **Services Precision/Recall/F1**: Accuracy of identifying affected services
- **Dependencies Precision/Recall/F1**: Accuracy of identifying dependencies
- **Risk Assessment Accuracy**: Accuracy of risk level prediction

### SME Agent Metrics

Measures code review quality (SME agents only):

- **Agent Selection Accuracy**: Were the correct agents invoked?
- **Review Quality**: Quality score per agent
- **Issue Coverage**: Fraction of issues caught
- **False Positive Rate**: Incorrectly flagged issues
- **Time per Agent**: Latency per agent invocation

### Task Completion Metrics

Measures end-to-end task execution:

- **Success Rate**: Did the task complete correctly?
- **Correctness Score**: Quality of the solution (0.0 to 1.0)
- **Time to Completion**: Total time taken
- **Tool Calls**: Number of tool/agent invocations
- **Iterations**: Number of retries needed

### Performance Metrics

Measures resource usage:

- **Latency**: P50, P95, P99 response times
- **Token Usage**: Prompt, completion, and total tokens
- **Memory Usage**: Peak memory consumption
- **Context Size**: Size of context in prompt

## Test Datasets

### Search Test Cases (`datasets/search.json`)

Semantic code search queries with ground truth:

- Query: Natural language description
- Relevant chunks: List of expected file:function pairs
- Relevance scores: Graded relevance (0.0 to 1.0)

Example:
```json
{
  "id": "search_001",
  "type": "search",
  "query": "JWT token generation and validation",
  "ground_truth": {
    "relevant_chunks": [
      "services/auth-service/internal/jwt/token.go:generate_token",
      "services/auth-service/internal/jwt/token.go:validate_token"
    ],
    "relevance_scores": {
      "services/auth-service/internal/jwt/token.go:generate_token": 1.0,
      "services/auth-service/internal/jwt/token.go:validate_token": 1.0
    }
  }
}
```

### Scope Test Cases (`datasets/scope.json`)

Task descriptions with expected blast radius:

- Description: Task to scope
- Files: Expected affected files
- Services: Expected affected services
- Dependencies: Expected new/modified dependencies
- Risk level: Expected risk assessment

### Code Review Test Cases (`datasets/code_review.json`)

PRs to review with expected issues:

- PR number: GitHub PR number
- Files changed: List of modified files
- Expected agents: Which SME agents should be invoked
- Critical issues: Must-fix issues with file:line
- Warnings: Should-fix issues

## Three-Way Comparison

### Scenario 1: repo-brain (Push Architecture)

**Features:**
- Persistent repo map (~6K tokens) in system prompt
- Architectural summary always available
- Semantic search via `/q <query>`
- Blast-radius analysis via `/scope <description>`

**Advantages:**
- No discovery phase (structure always known)
- Deterministic context injection
- Fast semantic search
- Dependency-aware scoping

**Limitations:**
- Token budget for large repos
- Repo map must be kept up-to-date

### Scenario 2: Regular (Pull Architecture)

**Features:**
- On-demand filesystem exploration
- Text-based search (grep/ripgrep)
- Manual file discovery
- No persistent context

**Advantages:**
- Zero token overhead
- Works with any codebase instantly
- Simple mental model

**Limitations:**
- Must rediscover structure each session
- Relies on LLM remembering to search
- No semantic search
- No dependency awareness

### Scenario 3: SME Agents (Specialized Experts)

**Features:**
- Domain-specific SME agents (11 agents):
  - @artemis - Authentication & JWT
  - @arik - REST API security
  - @dara - Database & migrations
  - @reina - React/TypeScript UI
  - @petra - Agent planning & orchestration
  - @luna - LLM evaluation & rubrics
  - @evan - Kafka events
  - @orion - Swarm coordination
  - @tarik - Task execution & RadKit
  - @marco - MCP tools
  - @kai - Streaming sanitization
- Automatic routing based on file paths
- Checklist-driven reviews
- Read-only, focused expertise

**Advantages:**
- Deep domain expertise
- Structured review format
- Catches domain-specific anti-patterns
- Parallel agent invocation

**Limitations:**
- Only useful for code review tasks
- Requires mapping files → agents
- No general code understanding

## Example Comparison Results

### Search Quality (Precision@3)

| Scenario | Precision@3 | Recall@3 | NDCG@3 |
|----------|-------------|----------|--------|
| repo-brain | 0.89 | 0.76 | 0.85 |
| regular | 0.45 | 0.38 | 0.42 |
| sme-agents | N/A | N/A | N/A |

### Scope Analysis (F1 Score)

| Scenario | Files F1 | Services F1 |
|----------|----------|-------------|
| repo-brain | 0.84 | 0.91 |
| regular | 0.52 | 0.48 |
| sme-agents | 0.73 | 0.82 |

### Code Review Quality (SME Agents)

- Average agents invoked per review: 1.8
- Issue coverage: 93%
- False positive rate: 7%
- Correct agent selection: 96%

### Performance Comparison

| Scenario | Avg Latency | Avg Tokens |
|----------|-------------|------------|
| repo-brain | 1250ms | 8200 |
| regular | 850ms | 3500 |
| sme-agents | 2100ms | 12000 |

## Adding New Test Cases

### 1. Create Test Case

Add to appropriate dataset file (`datasets/{test_type}.json`):

```json
{
  "id": "search_004",
  "type": "search",
  "description": "Your test description",
  "query": "Your search query",
  "ground_truth": {
    "relevant_chunks": ["file:function", ...],
    "relevance_scores": {"file:function": 1.0, ...}
  },
  "metadata": {
    "difficulty": "medium",
    "domain": "api"
  }
}
```

### 2. Run Evaluation

```bash
python tests/eval/run_comparison.py --test-suite search
```

### 3. Analyze Results

```bash
python tests/eval/analyze_results.py
```

## Integration with CI/CD

Add to your CI pipeline to track evaluation metrics over time:

```yaml
# .github/workflows/eval.yml
name: Evaluation
on: [push]
jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run evaluation
        run: |
          python tests/eval/run_comparison.py --test-suite all
          python tests/eval/analyze_results.py
      - name: Upload results
        uses: actions/upload-artifact@v2
        with:
          name: eval-results
          path: tests/eval/results/
```

## Next Steps

1. **Expand Test Coverage**: Add more test cases for each scenario
2. **Human Evaluation**: Add human scoring for subjective metrics
3. **Live Testing**: Integrate with real coding sessions
4. **Visualization**: Add charts and graphs to reports
5. **Regression Tracking**: Track metrics over time

## Related Documentation

- [repo-brain README](../../README.md) - Main repo-brain documentation
- [OpenCode Agents](https://opencode.ai/docs/agents) - SME agent documentation
- [Evaluation Best Practices](https://research.google/pubs/pub41543/) - Information retrieval evaluation
