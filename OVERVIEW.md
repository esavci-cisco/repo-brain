# repo-brain Overview

## What It Is
Persistent intelligence layer for OpenCode that gives the AI structural memory across sessions. Local vector DB + dependency graph that survives restarts.

## The Problem
Every OpenCode session starts from zero. On large codebases, the AI wastes time rediscovering what services exist, how they connect, and where code lives.

## Where Each Component Is Used

### Vector DB (ChromaDB)
**Storage**: `~/.repo-brain/{repo_name}/chroma/`

**Used by**:
- **`/q` command** — Semantic code search returns top 3 relevant chunks
- **`/scope` command** — Finds top 20 relevant chunks, then enriches with graph data

**What it stores**: Code chunks (functions, classes) with embeddings + metadata (file path, service, symbol names)

### Dependency Graph
**Storage**: `~/.repo-brain/{repo_name}/graph.json`

**Used by**:
- **`/scope` command** — Main use case:
  - Shows upstream dependencies (what this service needs)
  - Shows downstream dependents (what would break if you change this)
  - Risk assessment based on # of dependents
- **Repo map generation** — Boosts ranking of files in highly-connected services
- **Architecture summary** — Outputs service relationships for documentation

**What it stores**: NetworkX graph of services, their dependencies, and interconnections parsed from compose.yml, pyproject.toml, .proto files

### Repo Map
**Storage**: `{repo_root}/.repo-brain/repomap.md`

**Used by**:
- **Auto-refreshed** on each OpenCode session start
- **Architecture summary** — LLM reads it to write `architecture.md` (one-time)
- **Manual reference** — Developers can read it directly

**What it stores**: Tree-sitter AST skeleton (file paths, class/function signatures) — gives structural overview without full code

## Commands

### `/scope <task>` (Use This First)
1. Vector search finds relevant code
2. Extracts affected services from results
3. Graph queries show upstream/downstream dependencies
4. Outputs blast-radius analysis with risk assessment

### `/q <query>`
Pure vector search — returns top 3 code snippets matching your query

### `/summarize`
Combines repomap + graph + README → LLM writes `architecture.md`

## Known Issues

### Over-Engineering Bias
When AI sees comprehensive context from `/scope`, it can interpret it as implicit requirements:
- **Example**: Task "add filtering" → AI builds entire optimization library (3,815 lines) instead of adding one function (245 lines)
- **Why**: Seeing multiple services + architecture makes AI think "build proper infrastructure"
- **Reality**: Most tasks need simple, inline solutions

**Recent fix**: Added simplicity guidance to `/scope` output telling AI to:
- Solve immediate problem first (defer abstraction)
- Start where change belongs (resist new layers)
- Ask "am I over-engineering?"

### Token Usage
repo-brain typically uses **25-30% more tokens** than regular OpenCode because it loads:
- Architectural context (dependency graph)
- Blast-radius analysis
- Semantic search results (more comprehensive than grep)

**Trade-off**: More tokens upfront for better architectural awareness and fewer mistakes later.

## Technical Details
- **Local storage**: `~/.repo-brain/` (no Docker, no cloud)
- **Embeddings**: Run locally via sentence-transformers
- **Integration**: Custom OpenCode commands
- **Zero config**: Analyzes your repo automatically

## Setup
```bash
pip install -e .
repo-brain index /path/to/repo
```

Add commands to OpenCode, then use `/scope` before starting tasks.
