# 🔍 Comprehensive Evaluation Report: repo-brain vs regular

## Executive Summary

### Key Findings

**Winner: repo-brain** 🏆

- **Precision@3**: repo-brain achieves 43.3% vs regular's 5.6%
  - **+680% improvement** in finding relevant results

- **Recall@3**: repo-brain achieves 23.3% vs regular's 5.6%
  - **+320% improvement** in retrieving all relevant results

- **MRR (Mean Reciprocal Rank)**: 0.595 vs 0.119
  - **+398% better** at ranking relevant results higher

- **Speed**: repo-brain 1294ms vs regular 91ms
  - **14.3x slower** but finds 7.8x more relevant results

### Detailed Metrics Comparison

| Metric | repo-brain | regular | Winner |
|--------|------------|---------|--------|
| Precision@1 | 40.0% | 10.0% | ✅ repo-brain |
| Precision@3 | 43.3% | 5.6% | ✅ repo-brain |
| Recall@1 | 13.3% | 3.3% | ✅ repo-brain |
| Recall@3 | 23.3% | 5.6% | ✅ repo-brain |
| MRR | 0.595 | 0.119 | ✅ repo-brain |
| NDCG@3 | 0.485 | 0.070 | ✅ repo-brain |
| Latency (ms) | 1294 | 91 | ✅ regular |

## Architecture Comparison

### repo-brain (Push Architecture)
- ✅ **Semantic search**: Understands intent and context
- ✅ **Better ranking**: Uses embeddings for relevance scoring
- ✅ **Cross-file understanding**: Can find related code across the codebase
- ⚠️ **Slower**: 1294ms average latency
- ⚠️ **Setup required**: Needs initial indexing

### regular (Pull Architecture)
- ✅ **Fast**: 91ms average latency
- ✅ **No setup**: Works immediately with ripgrep
- ⚠️ **Keyword-only**: Misses semantically similar code
- ⚠️ **Poor ranking**: No relevance scoring
- ⚠️ **Literal matches only**: Can't understand developer intent

## Use Case Recommendations

### When to use repo-brain:
- Exploring unfamiliar codebases
- Finding "similar" functionality (not just exact matches)
- Understanding code organization and relationships
- When accuracy is more important than speed

### When to use regular (ripgrep):
- Quick lookups of known function/variable names
- Finding exact string matches
- When every millisecond counts
- Simple grep-style searches

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
