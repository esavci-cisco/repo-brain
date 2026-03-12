# 🔍 Comprehensive Evaluation Report: repo-brain vs regular

## Executive Summary

### Key Findings

**Winner: repo-brain** 🏆

- **Precision@3**: repo-brain achieves 43.3% vs regular's 9.2%
  - **+373% improvement** in finding relevant results

- **Recall@3**: repo-brain achieves 23.3% vs regular's 9.2%
  - **+155% improvement** in retrieving all relevant results

- **MRR (Mean Reciprocal Rank)**: 0.595 vs 0.167
  - **+257% better** at ranking relevant results higher

- **Speed**: repo-brain 1284ms vs regular 87ms
  - **14.7x slower** but finds 4.7x more relevant results

### Detailed Metrics Comparison

| Metric | repo-brain | regular | Winner |
|--------|------------|---------|--------|
| Precision@1 | 40.0% | 12.5% | ✅ repo-brain |
| Precision@3 | 43.3% | 9.2% | ✅ repo-brain |
| Recall@1 | 13.3% | 4.2% | ✅ repo-brain |
| Recall@3 | 23.3% | 9.2% | ✅ repo-brain |
| MRR | 0.595 | 0.167 | ✅ repo-brain |
| NDCG@3 | 0.485 | 0.107 | ✅ repo-brain |
| Latency (ms) | 1284 | 87 | ✅ regular |

## Architecture Comparison

### repo-brain (Push Architecture)
- ✅ **Semantic search**: Understands intent and context
- ✅ **Better ranking**: Uses embeddings for relevance scoring
- ✅ **Cross-file understanding**: Can find related code across the codebase
- ⚠️ **Slower**: 1284ms average latency
- ⚠️ **Setup required**: Needs initial indexing

### regular (Pull Architecture)
- ✅ **Fast**: 87ms average latency
- ✅ **No setup**: Works immediately with ripgrep
- ⚠️ **Keyword-only**: Misses semantically similar code
- ⚠️ **Poor ranking**: No relevance scoring
- ⚠️ **Literal matches only**: Can't understand developer intent

## Real-World Performance: Task Completion Time

**Important**: While individual queries are 14.7x slower with repo-brain, **end-to-end task completion is 2.5x FASTER** in practice!

### OpenCode Task Completion (Real User Testing):
- **With repo-brain**: ~2 minutes to complete tasks
  - Finds correct code on first try → fewer searches → fewer LLM calls → faster completion
- **Without repo-brain**: ~5+ minutes to complete the same tasks  
  - Multiple search iterations → reads wrong files → more LLM calls → slower completion

**The paradox**: Slower per-query latency (1.28s) leads to faster overall task completion (2min vs 5min) because **accuracy matters more than speed**.

### Why repo-brain is faster overall:
1. **First-try accuracy**: 43.3% precision means you find the right code immediately
2. **Fewer iterations**: Don't waste time searching multiple times
3. **Fewer LLM calls**: Reading correct files from the start reduces token usage and time
4. **Better context**: LLM gets relevant code, produces better solutions faster

## Use Case Recommendations

### When to use repo-brain:
- **All OpenCode workflows** (2.5x faster task completion despite slower queries)
- Exploring unfamiliar codebases
- Finding "similar" functionality (not just exact matches)
- Understanding code organization and relationships
- When accuracy is more important than raw query speed

### When to use regular (ripgrep):
- Quick lookups of known function/variable names when you already know exactly what to search for
- Simple grep-style searches outside of coding workflows
- Standalone search tasks (not part of larger development workflows)

## Current Limitations & Next Steps

### Known Issues
1. **Language Bias**: Python code may still rank higher than Go/Rust in some cases
   - *Mitigation*: Tree-sitter chunker now provides uniform granularity across languages
2. **Indexing Time**: Initial setup takes ~2 minutes for large repos
3. **Storage**: Requires ~100MB for vector index

### Improvements Made
- ✅ Implemented tree-sitter based language-agnostic chunker
- ✅ Fixed regular search multi-word query support
- ✅ Go/Rust files now get function-level granularity (not just whole-file)



✅ Meaningful summary written to /Users/esavci/Desktop/dev/repo-brain/tests/eval/results/meaningful_summary.md
