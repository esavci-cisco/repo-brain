# repo-brain: Technical Overview for Engineering Leadership

## Executive Summary

**repo-brain** is a local-first repository intelligence system that provides persistent structural memory for AI coding assistants (OpenCode). It maintains a queryable knowledge graph, vector database, and AST-based repository map to eliminate cold-start inefficiency on large codebases.

**Value Proposition:** Trades token efficiency for architectural awareness and code quality. Provides blast-radius analysis, dependency mapping, and semantic search to help AI assistants make better architectural decisions.

---

## The Problem

On large, multi-service codebases (e.g., 34+ microservices, 4,300+ files), every new AI coding session starts from zero:

- **Rediscovering structure**: AI wastes time re-learning service topology, file locations, and dependency relationships
- **Tool call dependency**: MCP tools exist but rely on the LLM remembering to invoke them (which it frequently doesn't)
- **No persistent memory**: Knowledge gained in one session is lost in the next
- **Exploratory overhead**: Each task begins with grep/glob searches before actual implementation

**Impact:** Repeated context-building overhead, inconsistent architectural decisions, and lack of blast-radius awareness.

---

## Technical Architecture

### Core Components

**1. Vector Store (ChromaDB)**
- Local, persistent storage at `~/.repo-brain/`
- Embeddings via `all-MiniLM-L6-v2` (on-device, no API costs)
- Query-time uses ONNX runtime (<2s latency, no torch import)
- ~500MB for large repos

**2. AST-Based Repository Map**
- Tree-sitter parsing (Python, TypeScript/TSX, JavaScript/JSX)
- Extracts: file paths, class names, function signatures (no bodies)
- **Service-aware ranking**: Guarantees every service gets at least one key file
- Auto-refreshed on session start via plugin
- Targets ~6K tokens (~24KB) for efficiency
- **NOT auto-loaded** - used as reference by `/q` and `/scope` only

**3. Dependency Graph**
- Parsed from: `docker-compose.yml`, `pyproject.toml`, `.proto` files
- NetworkX graph serialized to JSON
- Powers blast-radius analysis

**4. Metadata Store (SQLite)**
- SHA-256 content hashing for incremental indexing
- Only re-embeds changed files
- ~1MB storage

### Integration Points

```
OpenCode Session
    ↓
Custom Commands (.opencode/commands/)
    ├── /scope <task>  → repo-brain scope
    ├── /q <query>     → repo-brain context
    └── /summarize     → repo-brain summarize-context
    ↓
repo-brain CLI
    ↓
Vector DB + Graph + Repo Map
```

---

## Key Features

### 1. `/scope <task>` — Blast-Radius Analysis

**What it does:**
- Identifies affected services, key files, and dependencies before implementation
- Provides risk assessment and architectural context
- Shows how changes propagate through the system

**Example output:**
```
## Task Scope Analysis

### Affected Services
- rule-grpc-api (9 matches) — gRPC Rule Management API
- rule-mcp (6 matches) — Rule MCP Server
- neo4j-init (2 matches) — Neo4j initialization service

### Key Files to Read
1. mcp_servers/rule-mcp/app/src/rule_mcp_server/neo4j_client.py
2. services/rule-grpc-api/src/rule_grpc_api/mcp/neo4j_tools.py
3. services/neo4j-init/init_neo4j.py

### Risk Assessment
- LOW RISK: Changes appear localized to specific services.
```

### 2. `/q <query>` — Semantic Code Search

**What it does:**
- Returns top 3 relevant code chunks with full source
- 4.7x better precision than ripgrep (43.3% vs 9.2% P@3)
- Understands intent, not just keywords

**Use case:** Finding similar patterns, architectural examples, or related functionality

### 3. Repo Map — Structural Skeleton

**What it does:**
- Provides AST-level overview of entire codebase
- **Service-aware coverage**: For microservices architectures, guarantees at least one key file per service from dependency graph (main.py, server.py, config.py)
- Shows class definitions, function signatures, type hints
- Used internally by `/q` and `/scope` for structural awareness
- **NOT auto-loaded** (avoids token waste) - only fetched when commands are invoked

**How it's generated:**
- Tree-sitter parses source files to extract symbols
- Scores files by importance (entry points, graph centrality, symbol count)
- **Phase 1**: Ensures every service gets represented
- **Phase 2**: Fills remaining budget with highest-ranked files
- Result: Comprehensive coverage of microservices architecture

---

## Performance Characteristics

### Search Quality (Semantic vs Keyword)

| Metric | repo-brain | ripgrep | Improvement |
|--------|------------|---------|-------------|
| **Precision@3** | 43.3% | 9.2% | **+373%** |
| **Recall@3** | 23.3% | 9.2% | **+155%** |
| **MRR** | 0.595 | 0.167 | **+257%** |
| **Latency** | 1.3s | 87ms | 15x slower |

---

## Value Proposition: When to Use

### ✅ Use repo-brain when:

1. **Large, multi-service codebases** (10+ services, 1000+ files)
   - Architectural awareness becomes critical
   - Blast-radius analysis prevents cross-service breakage

2. **Complex dependency chains**
   - Understanding impact across service boundaries
   - Tracking proto changes, shared libraries, config propagation

3. **Knowledge preservation**
   - Team members working on unfamiliar services
   - Onboarding new engineers to complex systems

4. **Architectural decisions**
   - Refactoring that spans multiple services
   - Evaluating change impact before implementation

5. **Code quality over speed**
   - Production implementations requiring careful consideration
   - Features that need proper architectural planning

### ❌ Don't use repo-brain when:

1. **Small codebases** (<100 files)
   - Overhead not justified
   - Simple grep is sufficient

2. **Token budget constraints**
   - 25% token overhead may be unacceptable
   - Cost-sensitive applications

3. **Speed-critical workflows**
   - Quick bug fixes
   - Rapid prototyping

4. **Single-file changes**
   - No architectural context needed
   - Local changes with clear scope

---

## Setup & Installation

### Initial Setup (60 seconds for 4K files)

```bash
# 1. Install globally
uv tool install /path/to/repo-brain

# 2. Register repo
repo-brain init /path/to/your/repo

# 3. Install indexing dependencies (first time only)
uv tool install --with 'repo-brain[index]' /path/to/repo-brain

# 4. Run full pipeline
repo-brain setup
```

This creates:
- Vector index at `~/.repo-brain/repos/<slug>/chroma/`
- Dependency graph at `~/.repo-brain/repos/<slug>/graph.json`
- Repo map at `.repo-brain/repomap.md` (in your repo)
- OpenCode commands at `.opencode/commands/` (in your repo)

### What Gets Created After Setup

The `repo-brain setup` command runs 4 sequential steps:

**Step 1: Indexing (`repo-brain index`)**
- **Location**: `~/.repo-brain/repos/<slug>/chroma/`
- **What it does**: Scans all source files, chunks them intelligently (AST-aware for Python/TS/JS, sliding window for others), generates embeddings using `all-MiniLM-L6-v2`, and stores in ChromaDB
- **Size**: ~500MB for large repos (4K+ files)
- **Used by**: `/q` command for semantic code search
- **Incremental**: SHA-256 hashing tracks changes; only modified files are re-indexed

**Step 2: Build Dependency Graph (`repo-brain build-graph`)**
- **Location**: `~/.repo-brain/repos/<slug>/graph.json`
- **What it does**: Parses `docker-compose.yml`, `pyproject.toml` files, and `.proto` files to extract service topology and dependency relationships
- **Format**: NetworkX graph serialized as JSON with nodes (services, libraries, data stores) and edges (dependencies)
- **Size**: ~50KB for typical microservices architecture
- **Used by**: `/scope` command for blast-radius analysis and dependency tracking

**Step 3: Generate Repo Map (`repo-brain generate-map`)**
- **Location**: `.repo-brain/repomap.md` (inside your repository)
- **What it does**: Uses Tree-sitter to parse source files and extract AST structure (classes, functions, signatures - no bodies). **NEW: Service-aware ranking** ensures every service from the dependency graph gets at least one representative file (main.py, server.py, config.py)
- **Format**: Markdown file with file paths and symbol signatures
- **Size**: ~24KB (targets 6K token budget)
- **Coverage**: For microservices architectures, guarantees coverage of all services discovered in Step 2
- **Used by**: Reference file for `/q` and `/scope` commands (NOT auto-loaded into prompts)
- **Refreshed**: Automatically regenerated on OpenCode session start via plugin

**Step 4: Generate OpenCode Integration (`repo-brain generate-opencode`)**
- **Location**: `.opencode/commands/` and `.opencode/plugins/` (inside your repository)
- **What it creates**:
  - `/q` command: Semantic code search (calls `repo-brain context`)
  - `/scope` command: Task scoping and blast-radius analysis (calls `repo-brain scope`)
  - `/summarize` command: Generate architectural summary (one-time, cached)
  - `repo-brain.ts` plugin: Auto-refreshes repo map on session start
- **How it works**: Commands inject context on-demand when you invoke them (not auto-loaded)

### Incremental Updates

**Automatic:** Plugin refreshes repo map on session start

**Manual:**
```bash
repo-brain index           # Re-index changed files (incremental)
repo-brain build-graph     # Rebuild dependency graph
repo-brain refresh         # Git pull + re-index delta
```

**Incremental indexing** uses SHA-256 hashing — only changed files are re-embedded (seconds, not minutes).

### Data Location & Usage

Everything stored locally:
```
~/.repo-brain/
├── config.toml                 # Global settings
├── models/
│   └── all-MiniLM-L6-v2/      # Local embedding model (downloaded once)
└── repos/<slug>/
    ├── chroma/                 # Vector embeddings (~500MB)
    │   ├── index/             # HNSW index for fast similarity search
    │   └── *.parquet          # Embedding vectors + metadata
    ├── metadata.db             # SQLite: SHA-256 hashes for incremental indexing (~1MB)
    └── graph.json              # NetworkX dependency graph (nodes + edges)

<your-repo>/.repo-brain/
└── repomap.md                  # AST-based structural overview

<your-repo>/.opencode/
├── commands/
│   ├── q.md                   # Semantic search command
│   ├── scope.md               # Task scoping command
│   └── summarize.md           # Architectural summary command
└── plugins/
    └── repo-brain.ts          # Auto-refresh plugin
```

**How Each Component is Used:**

1. **ChromaDB Vector Store** (`~/.repo-brain/repos/<slug>/chroma/`)
   - Queried by: `/q <query>` command
   - Query flow: User query → embed query → similarity search → return top-N chunks
   - ONNX runtime at query-time (no PyTorch import, <2s latency)

2. **Dependency Graph** (`~/.repo-brain/repos/<slug>/graph.json`)
   - Queried by: `/scope <task>` command
   - Analysis: BFS traversal to find upstream/downstream dependencies
   - Provides blast-radius analysis (which services are affected)

3. **Repo Map** (`.repo-brain/repomap.md`)
   - Used by: `/q` and `/scope` as structural reference
   - **NOT auto-loaded** into prompts (avoids token waste)
   - Provides file-to-service mapping and symbol signatures
   - Auto-refreshed on session start to stay current

4. **Metadata DB** (`~/.repo-brain/repos/<slug>/metadata.db`)
   - Internal use only: Tracks SHA-256 hashes of indexed files
   - Enables incremental indexing (only re-index changed files)
   - Updated during `repo-brain index` or `repo-brain refresh`

---

## Design Decisions

### Pull, Not Push
Context is **injected on-demand via commands** (`/scope`, `/q`), not auto-loaded into every message. This prevents token waste from unused context.

### Local-First
- No Docker, no external services, no cloud dependencies
- Embeddings run on-device (Apple Silicon optimized)
- Zero API costs for vector operations

### Multi-Repo Support
- Isolated storage per repository
- Auto-detection by working directory
- Independent configurations

### Incremental Everything
- SHA-256 content hashing
- Only re-embeds changed files
- Graph updates only when compose/toml/proto files change

---

## Limitations & Trade-offs

### The Token Trade-off

**repo-brain uses more tokens** (typically +25-30% per task) because it loads:
- Architectural context (service relationships from dependency graph)
- Blast-radius analysis (affected components)
- Semantic search results (more comprehensive than keyword matches)

This additional context helps AI make better architectural decisions and avoid breaking changes, but comes at a token cost.

### Technical Limitations

1. **Language support**: Tree-sitter parsing limited to Python/TS/JS
   - Other languages use sliding-window chunking (less precise symbol extraction)
2. **Initial setup**: Requires ~60s indexing for large repos (4K+ files)
3. **Storage**: ~500MB vector index for large codebases
4. **Embedding model**: `all-MiniLM-L6-v2` is fast but less semantically powerful than cloud models (e.g., OpenAI ada-002)
5. **Search latency**: ~1.3s for semantic search vs 87ms for ripgrep

### Operational Considerations

- **Re-indexing frequency**: After major refactors or adding new services
- **Stale data**: Auto-refresh on session start helps, but manual `repo-brain refresh` recommended after large PRs
- **Team adoption**: Requires consistent use of `/scope` workflow to realize benefits

---

## Technical Stack Summary

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Vector DB | ChromaDB | Semantic search via embeddings |
| Embeddings | all-MiniLM-L6-v2 + ONNX | Fast on-device inference |
| AST Parsing | Tree-sitter | Language-agnostic code structure |
| Graph | NetworkX | Dependency relationship modeling |
| Metadata | SQLite | Incremental indexing state |
| Integration | OpenCode custom commands | User-triggered context injection |
| Deployment | Local-first, no containers | Zero infrastructure overhead |

---

## Quick Start for Evaluation

```bash
# 1. Install
uv tool install /path/to/repo-brain

# 2. Index your largest repo
repo-brain init /path/to/complex/repo
repo-brain setup

# 3. Test with OpenCode
cd /path/to/complex/repo
opencode

# In OpenCode, try:
/scope Add health check endpoint to all services
/q authentication middleware implementation
```

Evaluate whether the architectural context justifies the token overhead for your specific use case.

---

**Document Version:** 1.0  
**Last Updated:** March 23, 2026  
**Maintained by:** repo-brain development team  
**License:** Private
