# E2E Token Usage Comparison Tests

End-to-end tests that compare token usage between regular OpenCode and OpenCode with repo-brain's `/scope` command.

## What This Tests

### Two Scenarios

**1. Regular OpenCode (Baseline)**
- No repo-brain installed
- AI uses built-in tools: `ripgrep`, `glob`, `read`, etc.
- Discovers codebase structure through exploration
- Standard workflow: search → read → implement

**2. OpenCode with /scope (Optimized)**
- repo-brain enabled with `/scope` command
- Task prefixed with `/scope <task>` for blast-radius analysis
- AI receives targeted context upfront
- Optimized workflow: scope → implement

### What We Measure

- **Total tokens** (prompt + completion + cache reads/writes)
- **Completion time** (seconds)
- **Number of messages** (conversation length)
- **Cost** (USD, based on Claude pricing)
- **Success rate** (task completion)

## Running Tests

### Quick Test (1 run, 2 tasks)
```bash
./run_e2e_tests.sh
```

### Reliable Test (3 runs for averaging)
```bash
./run_e2e_tests.sh --runs 3
```

### Custom Repository
```bash
./run_e2e_tests.sh --repo /path/to/your/repo --runs 3
```

## Requirements

1. **Two repository copies**:
   - One WITHOUT repo-brain (for baseline)
   - One WITH repo-brain configured (`repo-brain setup`, `repo-brain generate-opencode`)

2. **OpenCode CLI** installed at `~/.opencode/bin/opencode`

3. **Task dataset** in `datasets/task.json` with test tasks

## How It Works

### 1. Test Execution (`e2e_task_completion.py`)

For each task:
1. **Regular scenario**: Run `opencode run "<task>"` in regular repo
2. **With /scope scenario**: Run `opencode run "/scope <task>\n\nImplement based on scope analysis"` in repo-brain repo
3. Capture session IDs from output

### 2. Token Extraction (`opencode_token_tracker.py`)

For each completed session:
1. Export session data: `opencode export <sessionID>`
2. Parse JSON to extract per-message token counts
3. Aggregate: prompt tokens, completion tokens, cache reads/writes, cost

### 3. Comparison

Calculate improvements:
- Token reduction: `(regular_tokens - scope_tokens) / regular_tokens * 100`
- Time reduction: `(regular_time - scope_time) / regular_time * 100`
- Cost reduction: `(regular_cost - scope_cost) / regular_cost * 100`

## Output

### Individual Results

```
tests/eval/results_e2e/
├── task_001_regular_run00.json        # Baseline run
├── task_001_with-scope_run00.json     # /scope run
├── task_002_regular_run00.json
├── task_002_with-scope_run00.json
└── token_usage_summary.md             # Summary report
```

### Summary Report

Markdown report with:
- Token usage comparison table
- Time and cost savings
- Explanation of why /scope is more efficient
- ROI calculations (daily/annual savings)

## Expected Results

Based on real testing with the Fully-Autonomous-Agents repo:

| Metric | With /scope | Regular | Improvement |
|--------|-------------|---------|-------------|
| Total Tokens | ~49k | ~136k | **66% fewer** |
| Time | ~3.2 min | ~6.1 min | **48% faster** |
| Files Changed | 3 | 6 | **More focused** |

## Adding New Test Tasks

Edit `datasets/task.json`:

```json
{
  "test_cases": [
    {
      "id": "task_001",
      "task": "Create GET /api/v1/users/{user_id}/profile endpoint",
      "description": "Simple CRUD operation",
      "expected_files": [
        "services/user-service/src/routes/profile.py"
      ]
    }
  ]
}
```

**Task design tips:**
- Make tasks realistic (actual development work)
- Require cross-service awareness (where /scope shines)
- Avoid trivial tasks (too quick to measure)
- Avoid overly complex tasks (>10 min timeout)

## Debugging Failed Tests

### Check OpenCode binary
```bash
which opencode
opencode --version
```

### Check session export
```bash
opencode session list
opencode export ses_xxxxx
```

### Check repo setup
```bash
# Repo-brain repo should have:
ls -la .opencode/commands/scope.md
ls -la .opencode/plugins/repo-brain.ts
cat opencode.json  # Should have basic config

# Regular repo should NOT have:
ls -la .opencode/commands/  # Should not exist or be empty
```

### Run single task manually
```bash
cd /path/to/repo-brain-enabled-repo
opencode run "/scope Create a health check endpoint"
```

## Limitations

1. **Requires manual repo setup**: Tests don't auto-configure repos (prevents test pollution)
2. **No automatic cleanup**: Old sessions accumulate (run `opencode session clear` manually)
3. **Network dependent**: OpenCode may call external APIs (can affect timing)
4. **Non-deterministic**: LLM responses vary (run multiple times for averages)

## CI/CD Integration

Not recommended for CI due to:
- Long execution time (4-12 minutes per run)
- Non-deterministic results (LLM variance)
- Requires OpenCode installation

Better for:
- Local benchmarking before releases
- Performance regression testing
- Demonstrating ROI to stakeholders
