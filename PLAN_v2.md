# repo-brain — Revised Build Specification

## Problem Statement

OpenCode is stateless across sessions and shallow across large repos. For a monorepo with 34+ microservices, 14 MCP servers, 13 shared libraries, and ~3,000 Python files, every new session starts from zero. The symptom: "I have to tell it to research every time."

OpenCode already has ripgrep, glob, LSP, git context, and task planning. For exact searches and symbol tracing, those are fast and precise. But they cannot provide:

- Persistent architectural understanding
- Semantic search across naming conventions
- Cross-service dependency awareness
- Domain knowledge that survives between sessions
- Impact analysis for shared code changes

repo-brain fills that gap.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Infrastructure | Zero — standalone tool, no Docker/DB deps | Must work on fresh clone, offline, without the application stack running |
| Embedding model | Local (`sentence-transformers`, configurable) | Zero cost, works offline, fast indexing |
| Storage location | `~/.repo-brain/repos/<repo-slug>/` | Central, multi-repo, survives repo deletion |
| Vector DB | ChromaDB (local persistent mode) | Simple, Python-native, no server process |
| Metadata DB | SQLite | Single file, zero config |
| Graph | NetworkX + JSON serialization | In-memory, fast traversal, no database |
| Index management | On-demand CLI + MCP tool with git remote refresh | User controls when to index, can pull latest develop |
| Architecture docs | Semi-automated: generate once, manually curate | LLM-generated docs are a starting point, human curation adds real value |
| Multi-repo | Supported from day one | Designed to work across any repo |
| OpenCode integration | MCP server (local subprocess) | Native OpenCode integration, no ports, no separate process management |

---

## What repo-brain Is NOT

- Not a replacement for OpenCode's grep/glob — those are faster for exact/keyword searches
- Not a UI or dashboard
- Not a runtime dependency of any application
- Not an auto-updating doc system that overwrites your edits

---

## Where repo-brain Adds Value vs OpenCode Defaults

| Query type | OpenCode alone | With repo-brain |
|---|---|---|
| "Find function `validate_token`" | Grep — instant, perfect | No improvement needed |
| "How is authentication handled?" | Need to know to search `jwt`, `auth`, `token`, `middleware` across Go + Python | Semantic search finds conceptually related code |
| "What services deal with user data?" | Manual grep across 34 services | Embeddings cluster related code regardless of naming |
| "What breaks if I change faa-models?" | Cannot traverse runtime deps | Dependency graph gives upstream/downstream impact |
| "How does test execution flow end-to-end?" | 10+ manual grep/read cycles | Architecture docs give it in one tool call |
| Context loading on session start | Starts from zero every time | Architecture docs pre-loaded, instant orientation |

The primary Phase 1 value is **architecture context loading**, not search. Pre-loaded architecture docs that OpenCode reads every session provide ~70% of the benefit. Semantic search is a complement to grep, not a replacement.

---

## Project Structure

```
repo-brain/
├── pyproject.toml
├── src/
│   └── repo_brain/
│       ├── __init__.py
│       ├── cli.py                  # Click CLI entry point
│       ├── mcp_server.py           # MCP server (OpenCode spawns this)
│       ├── config.py               # Config management (global + per-repo)
│       │
│       ├── ingestion/
│       │   ├── __init__.py
│       │   ├── scanner.py          # File discovery (respects .gitignore)
│       │   ├── chunker.py          # AST-aware code chunking
│       │   ├── embedder.py         # Embedding generation wrapper
│       │   └── parsers/
│       │       ├── __init__.py
│       │       ├── python_ast.py   # Python function/class extraction
│       │       ├── compose.py      # Docker Compose -> service topology
│       │       ├── proto.py        # Proto -> gRPC service contracts
│       │       ├── toml_deps.py    # pyproject.toml -> library deps
│       │       └── helm.py         # Helm charts -> deployment topology
│       │
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── vector_store.py     # ChromaDB wrapper
│       │   ├── metadata_db.py      # SQLite (file index, timestamps)
│       │   └── graph_store.py      # NetworkX + JSON persistence
│       │
│       ├── tools/                  # MCP tool implementations
│       │   ├── __init__.py
│       │   ├── search.py           # search_code(query)
│       │   ├── scope.py            # scope_task(description) — primary daily workflow tool
│       │   ├── dependencies.py     # query_dependencies(module)
│       │   ├── architecture.py     # get_architecture(), get_service_info()
│       │   └── refresh.py          # refresh_index() — pull + re-index delta
│       │
│       └── generators/             # One-shot doc generation
│           ├── __init__.py
│           ├── architecture.py     # architecture.md generation
│           ├── domain_terms.py     # domain_terms.md generation
│           └── service_map.py      # service_map.json generation
│
└── tests/
    └── ...
```

---

## Data Layout

```
~/.repo-brain/
├── config.toml                         # Global config (default model, etc.)
└── repos/
    └── fully-autonomous-agents/        # Keyed by git remote URL slug
        ├── config.toml                 # Repo config (path, remote, branch, github token)
        ├── chroma/                     # ChromaDB persistent directory
        ├── metadata.db                 # SQLite: file index, chunk mappings, timestamps
        ├── graph.json                  # Serialized NetworkX dependency graph
        └── docs/
            ├── architecture.md         # Generated then manually curated
            ├── domain_terms.md
            ├── service_map.json        # Structured: services, deps, data stores
            └── gotchas.md
```

---

## CLI Commands

```
repo-brain init <repo-path>        # Register a repo, create config
repo-brain index [--full]          # Index current repo (incremental by default)
repo-brain refresh                 # git fetch + re-index changed files
repo-brain generate-docs           # One-shot architecture doc generation
repo-brain status                  # Show index health: file count, staleness
repo-brain search <query>          # Quick search from terminal
repo-brain serve                   # Start MCP server (usually OpenCode does this)
repo-brain list                    # List registered repos
```

---

## MCP Tools (what OpenCode sees)

| Tool | Input | Output | Purpose |
|------|-------|--------|---------|
| `scope_task` | `description: str` | Affected services, key files, deps, risks | **Primary tool** — scope any new task before implementing |
| `search_code` | `query: str, limit: int` | File paths, snippets, scores | Semantic code search |
| `get_architecture` | none | Full architecture.md content | Load repo context |
| `get_service_info` | `service: str` | Service-specific architecture, deps, key files | Focused context for a known service |
| `query_dependencies` | `module: str, direction: up\|down\|both` | Dependency list with risk assessment | Impact analysis |
| `refresh_index` | `pull: bool` | Status message | Pull latest + re-index delta |
| `index_status` | none | Staleness info, file counts, last indexed | Quick health check |

---

## OpenCode Integration

In the target repo's `opencode.json`:

```json
{
  "mcp": {
    "repo-brain": {
      "type": "local",
      "command": ["repo-brain", "serve"],
      "enabled": true,
      "environment": {
        "REPO_PATH": "/path/to/your/repo",
        "GITHUB_TOKEN": "{env:GITHUB_TOKEN}"
      }
    }
  }
}
```

In `AGENTS.md` / instructions:

```markdown
## repo-brain

Starting a new task (feature, ticket, bug fix — anything where you don't know which files are affected):
- Call `scope_task(description)` first — returns affected services, key files, deps, and risks.

Targeted queries (you already know what you're looking for):
- "What is this repo?" → `get_architecture`
- "Tell me about service X" → `get_service_info(service_name)`
- "What breaks if I change X?" → `query_dependencies(module)`
- "Find code that does X" (fuzzy) → `search_code(query)`
- Exact names or keywords → grep/glob (built-in tools are faster)

Do NOT call multiple repo-brain tools preemptively. Call scope_task once at the start,
then use targeted tools only if you need more specific info.
```

---

## Implementation Phases

### Phase 1 — Architecture context + semantic search (1-2 weeks)

**Goal**: OpenCode gets instant repo orientation and can semantically search code.

1. Project scaffolding: pyproject.toml, CLI skeleton (Click), config module
2. File scanner: walk repo, respect .gitignore, filter by language/extension
3. Code chunker: Python AST parser — chunk at function/class level. Non-Python (TS, Go, YAML) falls back to sliding window with overlap
4. Embedder: sentence-transformers wrapper with `all-MiniLM-L6-v2` default (configurable)
5. ChromaDB storage: local persistent mode, collection per repo
6. SQLite metadata: track indexed files, chunk-to-file mappings, content hashes, timestamps
7. `search_code` tool: query ChromaDB, return ranked results with file paths and snippets
8. MCP server: minimal server exposing `search_code`, `get_architecture`, `index_status`
9. `generate-docs` CLI: analyze repo structure, produce initial architecture.md and service_map.json
10. OpenCode wiring: add MCP config to target repo's opencode.json

**Exit criteria**: Ask OpenCode "where is authentication handled?" — it calls `search_code`, gets relevant results from auth-service, REST API JWT middleware, and Go auth service without you having to tell it where to look.

### Phase 2 — Dependency graph + refresh (1-2 weeks)

**Goal**: Impact analysis and incremental re-indexing.

1. Python import parser: build module-level import graph from AST
2. Compose parser: parse compose.yml -> service dependency edges
3. Proto parser: parse .proto files -> gRPC service contracts
4. pyproject.toml parser: parse all pyproject.toml files -> library dependency edges
5. NetworkX graph: merge all parsers into unified graph, serialize to JSON
6. `query_dependencies` tool: given a module/service, traverse graph for up/downstream
7. Refresh command: `git fetch`, diff changed files, re-index only delta, update graph if topology files changed
8. `get_service_info` tool: combine architecture docs + graph data for focused service view

**Exit criteria**: Ask OpenCode "what would be affected if I change the faa-models library?" — it calls `query_dependencies`, returns the 15+ services that depend on it.

### Phase 3 — Incident memory (1 week, only if useful)

**Goal**: Recall past bugs and fixes.

Only build this if you have incident data to feed it. Otherwise skip.

1. SQLite incident table: structured entries (cause, resolution, modules, lessons)
2. Embeddings for incidents: embed text, store in ChromaDB collection
3. `recall_incident` tool: semantic search over past incidents
4. Capture workflow: CLI `repo-brain add-incident` or parse from git commits / PR descriptions

### Phase 4 — Polish + multi-repo (1 week)

**Goal**: Production-quality multi-repo support.

1. Multi-repo config: `repo-brain init` for additional repos
2. Repo auto-detection: MCP server infers which repo based on working directory
3. Diff suggestions: detect new services/files not in architecture docs, write to `pending_updates.md`
4. Helm chart parser: parse helm-charts for deployment topology
5. Kafka topic parser: parse kafka-init configs for event flow edges

---

## Key Technical Decisions

### Chunking strategy

Do NOT use naive line-window chunking. For Python (~3,000 files), parse the AST and chunk at function/class boundaries. Each chunk gets metadata:

```json
{
  "file_path": "services/auth-service/app/main.go",
  "function_name": "ValidateToken",
  "class_name": null,
  "line_start": 45,
  "line_end": 82,
  "imports": ["github.com/golang-jwt/jwt/v5"],
  "service": "auth-service",
  "language": "go"
}
```

This makes search results actionable — "function X in file Y at line Z" not "lines 45-80 of some file."

### Embedding model

Start with `all-MiniLM-L6-v2` (384-dim, fast, good enough). If search quality is poor for code, swap to a code-specific model via config:

- `nomic-embed-code`
- `Salesforce/SFR-Embedding-Code`
- `voyage-code-3` (cloud, if needed)

Change one config value, re-index, done.

### Incremental indexing

SQLite tracks `(file_path, content_hash, last_indexed)`. On re-index:

1. Hash each file
2. Skip files where hash hasn't changed
3. Only re-embed changed files
4. Delete chunks for removed files

This makes refresh fast even on a 3,000-file repo.

### MCP server lifecycle

OpenCode spawns and kills the process. The server reads config, connects to local ChromaDB/SQLite, serves tools. No manual process management. Lazy-load the embedding model on first search call, not on startup — keeps MCP server startup fast.

### Multi-repo data isolation

Each repo gets its own directory under `~/.repo-brain/repos/`. Keyed by git remote URL slug (e.g., `github.com-CXEPI-nova-avf-core` or a user-provided name). No cross-contamination between repos.

---

## Dependencies

```toml
[project]
name = "repo-brain"
requires-python = ">=3.11"

dependencies = [
    "click",                    # CLI
    "mcp",                      # MCP Python SDK
    "chromadb",                 # Vector storage (local mode)
    "sentence-transformers",    # Local embeddings
    "networkx",                 # Dependency graph
    "pyyaml",                   # Compose/Helm parsing
    "tomli",                    # pyproject.toml parsing (Python <3.11 compat)
    "gitpython",                # Git operations for refresh
]

[project.optional-dependencies]
dev = [
    "pytest",
    "ruff",
]
```

---

## Non-Goals

| Excluded | Reason |
|----------|--------|
| UI / dashboard | This is a tool for OpenCode, not humans |
| Cloud deployment | Runs on your laptop |
| Real-time file watching | Over-engineered — on-demand is sufficient |
| Auto-updating architecture docs | Risk of noise and overwriting manual edits |
| Full-text search (BM25) | OpenCode already has ripgrep |
| Runtime event tracing | Would require hooking into running services |
| FastAPI HTTP server | MCP server is the correct integration for OpenCode |

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Embedding quality poor for code | Pluggable model — swap to code-specific model |
| Initial indexing slow for 3K files | Incremental by default, full index is one-time |
| ChromaDB local mode perf limits | Fine for <100K chunks. ~30K chunks max for this repo |
| Architecture docs go stale | Phase 4 adds drift detection. Short-term: manual discipline |
| MCP server startup latency | Lazy-load embedding model on first search, not on startup |
| sentence-transformers is a heavy dependency | One-time install. Could swap to lighter `onnxruntime` backend later |

---

## Success Criteria

repo-brain is successful if:

1. OpenCode answers "how does X work?" without manual grep guidance
2. Architecture questions get correct answers on the first try
3. Cross-service changes come with impact awareness
4. New sessions start productive immediately (no "research the codebase first")
5. The tool works on a fresh machine with just `uv tool install` + `repo-brain init`
