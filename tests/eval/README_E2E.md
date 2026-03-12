# End-to-End Task Completion Testing

## Overview

This directory contains tests for measuring **total token consumption** during complete coding tasks, comparing repo-brain vs regular (ripgrep) scenarios.

## Current Status: SIMULATION

⚠️ **The current implementation is a SIMULATION** based on observed patterns. Real token tracking requires integration with OpenCode's API.

## Simulation Results

Running `python tests/eval/e2e_task_completion.py`:

```
| Metric              | repo-brain | regular | Winner        |
|---------------------|-----------|---------|---------------|
| Total Tokens        | 9,500     | 19,400  | ✅ repo-brain |
| Completion Time     | ~2 min    | ~5 min  | ✅ repo-brain |
| LLM Calls           | 2         | 4       | ✅ repo-brain |
| Cost per task (GPT-4)| $0.38    | $0.78   | ✅ repo-brain |
```

**Key finding**: repo-brain uses **51% fewer tokens** by finding correct code immediately.

## Why repo-brain Uses Fewer Tokens

1. **Better initial search**: 43.3% precision → finds right code on first try
2. **No wasted reads**: Doesn't read wrong files that need to be discarded
3. **Fewer retry iterations**: Gets good context → LLM succeeds faster  
4. **Cleaner context**: Only relevant code sent to LLM

## Real-World Validation Needed

To get **real** token measurements, we need to:

### Option 1: OpenCode API Integration (Recommended)
```python
# Pseudo-code for real implementation
from opencode import OpenCodeClient

client = OpenCodeClient()
session = client.start_session(
    repo_path="/path/to/repo",
    use_repo_brain=True,
    track_tokens=True
)

result = session.run_task("Add user profile endpoint")
print(f"Total tokens: {result.total_tokens}")
```

### Option 2: Log Parser
- Parse OpenCode logs/output to extract token counts from LLM responses
- Aggregate all token usage throughout task completion
- Compare repo-brain vs regular runs

### Option 3: Manual Testing (Current)
User reported real-world observations:
- With repo-brain: ~2 minutes task completion
- Without repo-brain: ~5+ minutes task completion
- Fewer iterations with repo-brain = fewer tokens

## TODO: Implementation Plan

1. **Phase 1: Log Parser** (Easiest)
   - [ ] Parse OpenCode output for token counts
   - [ ] Aggregate across entire session
   - [ ] Compare repo-brain vs regular

2. **Phase 2: API Integration** (Best)
   - [ ] Add programmatic OpenCode API if available
   - [ ] Track tokens through API
   - [ ] Automate comparison runs

3. **Phase 3: Production Metrics** (Future)
   - [ ] Instrument OpenCode with metrics collection
   - [ ] Track token usage in production
   - [ ] Generate weekly reports

## Running the Simulation

```bash
# Run simulated comparison (3 tasks)
python tests/eval/e2e_task_completion.py --repo /path/to/repo

# Results saved to tests/eval/results_e2e/
```

## Cost Implications

Based on simulation:
- **Per task savings**: $0.40 (51% reduction)
- **Daily savings** (100 tasks): **$40/day**
- **Annual savings**: **~$14,600/year**

## Next Steps

Replace simulation with real OpenCode integration to validate these estimates with actual token usage data.
