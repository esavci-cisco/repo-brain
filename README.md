# repo-brain

Persistent repo intelligence for [OpenCode](https://opencode.ai). Gives your AI coding assistant structural memory that survives across sessions — without relying on the LLM to call the right tools.

## The Problem

Every new OpenCode session starts from zero. On a large codebase (34+ microservices, ~4,300 files), the AI wastes time rediscovering the same things: which services exist, how they connect, where the relevant code lives. MCP tools help, but they depend on the LLM remembering to call them — and it often doesn't.

## What repo-brain Does

repo-brain uses a **push architecture**: context is injected deterministically into the LLM's view, not pulled on demand by tool calls. No MCP server, no tool definitions, no hoping the model picks the right tool.

Two layers of automatic context:

1. **Repo Map (Macro)** — a Tree-sitter AST skeleton (file paths, class names, function signatures, no bodies) saved to `.repo-brain/repomap.md` and loaded into every system prompt via `opencode.json` instructions. The LLM always knows what exists and where.

2. **Auto-Context (Micro)** — an OpenCode plugin hooks `chat.message` and automatically runs a vector search against the user's message. The top 2 relevant code chunks are appended to the message *before* the LLM sees it. Every substantive message gets context-enriched without the user doing anything.

Plus two optional power-user commands:

- **`/q <query>`** — explicit semantic search, returns more chunks (3 by default) with full code
- **`/scope <description>`** — blast-radius analysis: affected services, key files, dependencies, risks

All data is stored locally at `~/.repo-brain/`. No Docker, no external services, no cloud.

## Quick Start

```bash
# Install
uv tool install /path/to/repo-brain

# Register and set up your repo
repo-brain init /path/to/your/repo
repo-brain setup
```

`repo-brain setup` runs four steps:
1. **Index** — scans files, chunks code (AST-aware), embeds into a local vector store (ChromaDB)
2. **Build graph** — parses `compose.yml`, `pyproject.toml`, and proto files into a dependency graph
3. **Generate map** — Tree-sitter extracts structural info → `.repo-brain/repomap.md`
4. **Generate OpenCode integration** — writes commands, plugin, and patches `opencode.json`

After setup, just open OpenCode in the repo. Everything works automatically.

## How It Works

### Automatic context (no user action needed)

```
User types: "fix the auth bug in the login flow"
  ↓
OpenCode fires chat.message hook
  ↓
Plugin reads user text, shells out to: repo-brain context "fix the auth bug..."
  ↓
Vector search finds 2 most relevant code chunks
  ↓
Plugin appends chunks to the message as <repo-context>
  ↓
LLM sees: user's question + relevant code already inline
  ↓
LLM starts working with the right files immediately
```

The plugin also refreshes the repo map on `session.created`, so the system prompt skeleton is always current.

### Filtering

Not every message needs context. The plugin skips:
- Short messages (< 20 chars)
- Conversational replies ("yes", "ok", "thanks", "lgtm", etc.)
- Messages that already contain `<repo-context>` (from `/q`)

### /q and /scope commands

These are power-user overrides when automatic context isn't enough:

```
/q authentication middleware    # explicit semantic search (3 chunks)
/scope add rate limiting to API # blast-radius analysis
```

`/q` is for targeted lookup. `/scope` is for understanding impact before starting work.

### scope in action

```
> /scope add device-to-rule relationship tracking in neo4j

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

## CLI Commands

```
repo-brain init <path>           # Register a repo
repo-brain setup [--full]        # Full pipeline: index → graph → map → opencode
repo-brain index [--full]        # Index codebase (incremental by default)
repo-brain build-graph           # Build dependency graph
repo-brain generate-map          # Generate Tree-sitter repo map
repo-brain generate-opencode     # Generate OpenCode integration files
repo-brain context <query>       # Return formatted code context (used by plugin + /q)
repo-brain scope <description>   # Scope a task (used by /scope)
repo-brain refresh [--no-pull]   # Git fetch + re-index changed files
repo-brain export-model          # Save embedding model locally (one-time)
repo-brain search <query>        # Search from terminal (human-readable)
repo-brain status                # Show index stats
repo-brain list                  # List registered repos
```

## Architecture

```
repo-brain/
├── src/repo_brain/
│   ├── cli.py                  # Click CLI (context, scope, generate-map, etc.)
│   ├── config.py               # Global + per-repo config
│   ├── ingestion/
│   │   ├── scanner.py          # .gitignore-aware file discovery
│   │   ├── chunker.py          # AST-aware code chunking
│   │   ├── embedder.py         # sentence-transformers wrapper
│   │   ├── build_graph.py      # Orchestrates parsers into dependency graph
│   │   └── parsers/            # Docker Compose, pyproject.toml, proto
│   ├── storage/
│   │   ├── vector_store.py     # ChromaDB (local persistent)
│   │   ├── metadata_db.py      # SQLite (file index, content hashes)
│   │   └── graph_store.py      # NetworkX + JSON serialization
│   ├── tools/
│   │   ├── scope.py            # Task scoping with blast-radius analysis
│   │   ├── search.py           # Semantic code search
│   │   └── refresh.py          # Git fetch + delta re-index
│   └── generators/
│       ├── repomap.py          # Tree-sitter repo map generator
│       └── opencode.py         # OpenCode integration file generator
```

## Generated Files

`repo-brain setup` creates these files in the target repo:

| File | Purpose | Committed? |
|------|---------|------------|
| `.repo-brain/repomap.md` | AST skeleton for system prompt | No (gitignored) |
| `.opencode/commands/q.md` | `/q` custom command | No (gitignored) |
| `.opencode/commands/scope.md` | `/scope` custom command | No (gitignored) |
| `.opencode/plugins/repo-brain.ts` | Auto-context plugin | No (gitignored) |
| `opencode.json` (patched) | Adds repomap.md to instructions | Yes |

Data stored at `~/.repo-brain/repos/<slug>/`:

```
├── config.toml        # Repo settings
├── chroma/            # Vector embeddings
├── metadata.db        # SQLite file index
└── graph.json         # Dependency graph
```

## Key Design Decisions

- **Push, not pull** — context is injected deterministically, not dependent on LLM tool selection
- **Two-layer context** — macro (repo map in system prompt) + micro (per-message code chunks)
- **Automatic enrichment** — `chat.message` hook means zero user friction for context
- **Zero infrastructure** — no Docker, no external services, everything runs locally
- **Multi-repo** — each repo gets isolated storage, auto-detected by working directory
- **Incremental indexing** — SHA-256 content hashing, only re-embeds changed files
- **Local embedding model** — `all-MiniLM-L6-v2` runs on-device, no API costs
- **Tree-sitter parsing** — Python, TypeScript/TSX, JavaScript/JSX support for repo map
- **Token-conscious** — repo map targets ~2K tokens; auto-context limited to 2 chunks per message

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended for installation)

## License

Private.
