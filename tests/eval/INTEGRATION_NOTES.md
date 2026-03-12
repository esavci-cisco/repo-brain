# What Was Fixed: Parsing repo-brain Output

## The Problem

The evaluation script (`tests/eval/run_comparison.py`) was calling repo-brain commands but **not parsing the output**, so it always returned empty results.

### Before (Lines 143-159)

```python
def _repo_brain_search(self, query: str) -> tuple[list[str], list[float]]:
    """Execute repo-brain semantic search"""
    try:
        cmd = ["repo-brain", "search", "--query", query, "--repo", str(self.repo_path)]
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
        
        # ❌ Output captured but never used!
        # ❌ Always returns empty lists
        retrieved = []
        scores = []
        return retrieved, scores
```

**Result**: No actual comparison possible because repo-brain results were always empty.

---

## The Fix

### 1. Parse Search Output (Lines 143-183)

**repo-brain search output format:**
```
[1] services/auth-service/utils/jwt.go — fragment: lines_96_195 (auth-service)
    Score: 0.6444  Lines: 96-195

[2] services/auth-service/internal/jwt/token.go — module: __file__ (auth-service)
    Score: 0.6334  Lines: 1-71
```

**Now parses:**
- File paths using regex: `r"\[\d+\]\s+(.*?)\s+—"`
- Similarity scores using: `r"Score:\s+([\d.]+)"`
- Returns `(["file1.go", "file2.go"], [0.6444, 0.6334])`

### 2. Parse Scope Output (Lines 232-265)

**repo-brain scope output format:**
```markdown
### Affected Services
- **rest-api** (20 matches)
- **auth-service** (5 matches)

### Key Files
- `services/rest-api/app/middleware/rate_limiter.py` — RateLimitScope
- `services/rest-api/app/main.py` — Application setup
```

**Now parses:**
- Services using: `r"-\s+\*\*([a-z0-9-]+)\*\*"`
- Files using: `r"-\s+\`([^\`]+)\`\s+—"`
- Returns `{"files": [...], "services": [...], "dependencies": []}`

---

## Now What Works

### ✅ Search Comparison Works
```bash
python tests/eval/run_comparison.py --test-suite search
```

Will now:
1. ✅ Run repo-brain search and extract results
2. ✅ Run grep search for comparison
3. ✅ Calculate Precision@K, Recall@K, NDCG
4. ✅ Save metrics to JSON

### ✅ Scope Comparison Works
```bash
python tests/eval/run_comparison.py --test-suite scope
```

Will now:
1. ✅ Run repo-brain scope and extract files/services
2. ✅ Compare against ground truth
3. ✅ Calculate F1 scores for files, services, dependencies
4. ✅ Save metrics to JSON

---

## What Still Needs Work

### 1. SME Agent Integration (Line ~290)

**Current state:**
```python
def _invoke_sme_agents(self, files_changed, pr_number=None):
    # TODO: Actually invoke agents through OpenCode
    metrics.agents_invoked = list(agents_to_invoke)
    metrics.review_quality = {agent: 0.0 for agent in agents_to_invoke}  # ❌ Placeholder
    return metrics
```

**What's needed:**
- Call OpenCode's Task tool to invoke SME agents
- Parse review output (issues found, severity, etc.)
- Calculate review quality metrics

**How to fix:**
You'll need to integrate with OpenCode's API or CLI to actually invoke agents like `@artemis`, `@dara`, etc.

### 2. Test Dataset Validation

**Current state:**
- Example test cases in `datasets/*.json`
- Need real ground truth data from your actual repos

**What's needed:**
- Add real queries you want to test
- Manually label which files/chunks should be retrieved
- Add real PRs for code review testing

### 3. Task Completion Tests (Line ~256)

**Current state:**
```python
def _run_task_test(self, test_case, scenario, result):
    # Task completion requires manual/LLM evaluation
    # For now, create placeholder metrics
    result.task_completion = TaskCompletionMetrics()  # ❌ Empty
```

**What's needed:**
- Define how to measure task completion
- Either manual evaluation or automated checking
- Compare solution quality across scenarios

---

## Quick Test to Verify It Works

```bash
# 1. Make sure repo-brain is set up
repo-brain list

# 2. Run a quick search test
python tests/eval/run_comparison.py \
  --test-suite search \
  --scenarios repo-brain \
  --repo Fully-Autonomous-Agents

# 3. Check results
cat tests/eval/results/*.json
```

You should now see actual file paths and scores in the results instead of empty lists!

---

## Summary

**Fixed:**
- ✅ repo-brain search output parsing (regex extraction)
- ✅ repo-brain scope output parsing (markdown parsing)
- ✅ Proper return of file paths and similarity scores

**Still TODO:**
- ⚠️ SME agent invocation (needs OpenCode integration)
- ⚠️ Real test dataset creation (needs manual labeling)
- ⚠️ Task completion evaluation (needs success criteria)

The core evaluation infrastructure is now **functional** for search and scope comparisons!
