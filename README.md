# repo-brain

Persistent repo intelligence MCP server for [OpenCode](https://opencode.ai). Gives your AI coding assistant architectural memory that survives across sessions.

## The Problem

Every new OpenCode session starts from zero. On a large codebase (34+ microservices, ~4,300 files), the AI wastes time rediscovering the same things: which services exist, how they connect, where the relevant code lives. You end up saying "research the codebase" at the start of every conversation.

## What repo-brain Does

repo-brain provides two layers of persistent, pre-computed knowledge:

1. **Static knowledge** (via AGENTS.md) -- a compact codebase overview injected into AGENTS.md so the LLM has architectural context from the first message. Covers tech stack, components, dependency hotspots, and gotchas.

2. **Interactive tools** (via MCP + custom subagent) -- semantic search and task scoping accessible through a custom OpenCode subagent that competes with the built-in `explore` agent:
   - **Task scoping** -- describe what you want to do, get back affected services, key files, dependencies, and risks
   - **Semantic code search** -- find code by concept ("authentication flow") when grep won't work
   - **Dependency graph** -- upstream/downstream impact analysis from Docker Compose, pyproject.toml, and proto files
   - **Incremental indexing** -- re-index only changed files, keeps context fresh

All data is stored locally at `~/.repo-brain/`. No Docker, no external services, no cloud.

## Quick Start

```bash
# Install globally
uv tool install /path/to/repo-brain

# Register and set up your repo (index + build-graph + generate-docs)
repo-brain init /path/to/your/repo
repo-brain setup
```

Add to your repo's `opencode.json`:

```json
{
  "mcp": {
    "repo-brain": {
      "type": "local",
      "command": ["repo-brain", "serve"],
      "enabled": true,
      "environment": {
        "REPO_PATH": "/path/to/your/repo"
      }
    }
  }
}
```

`repo-brain setup` does three things:
1. Indexes the codebase into a local vector store (ChromaDB)
2. Builds a dependency graph from compose.yml, pyproject.toml, and proto files
3. Generates docs: injects a codebase overview into AGENTS.md, and creates a custom OpenCode subagent at `.opencode/agents/repo-brain.md`

## How It Works with OpenCode

### The subagent (key mechanism)

OpenCode's system prompt directs the LLM to use subagents (via the Task tool) for codebase exploration. repo-brain generates a custom `repo-brain` subagent that appears alongside the built-in `explore` and `general` agents. Its description is tuned to match exploration queries ("how does X work?", "find code related to Y"), so the LLM picks it over `explore`.

The subagent has access to repo-brain's MCP tools (`search_code`, `scope_task`) plus `read`, so it can:
1. Query the semantic index to find relevant files
2. Read those files to provide detailed answers
3. Scope tasks with dependency awareness

### AGENTS.md injection

`repo-brain setup` also injects a compact codebase overview between `<!-- repo-brain:start -->` and `<!-- repo-brain:end -->` markers at the end of AGENTS.md. Existing content above the markers is never modified. This gives the LLM architectural context (tech stack, components, dependency hotspots) from the first message without any tool calls.

## MCP Tools

The MCP server exposes 3 tools, accessed through the repo-brain subagent:

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `search_code(query)` | Semantic code search by meaning | Finding code by concept |
| `scope_task(description)` | Scope a task -- returns affected files, deps, risks | Starting any new work |
| `refresh_index(pull)` | Git fetch + re-index changed files | Updating the index |

### scope_task in Action

Paste a ticket description, feature request, or just a one-liner:

```
> add device-to-rule relationship tracking in neo4j with execution lineage
```

Returns:

```
## Task Scope Analysis

### Affected Services
- rule-grpc-api (9 matches) -- gRPC Rule Management API
- rule-mcp (6 matches) -- Rule MCP Server with ChromaDB integration
- neo4j-init (2 matches) -- Neo4j initialization service

### Key Files to Read
1. mcp_servers/rule-mcp/app/src/rule_mcp_server/neo4j_client.py
2. services/rule-grpc-api/src/rule_grpc_api/mcp/neo4j_tools.py
3. services/neo4j-init/init_neo4j.py

### Risk Assessment
- LOW RISK: Changes appear localized to specific services.
```

## CLI Commands

```
repo-brain init <path>         # Register a repo
repo-brain setup [--full]      # Run full pipeline: index + build-graph + generate-docs
repo-brain index [--full]      # Index codebase (incremental by default)
repo-brain build-graph         # Build dependency graph from compose/toml/proto
repo-brain generate-docs       # Generate docs + AGENTS.md injection + subagent
repo-brain refresh [--no-pull] # Git fetch + re-index changed files
repo-brain export-model        # Save embedding model locally (one-time)
repo-brain search <query>      # Search from terminal
repo-brain status              # Show index stats
repo-brain list                # List registered repos
repo-brain serve               # Start MCP server (OpenCode does this automatically)
```

## Architecture

```
repo-brain/
├── src/repo_brain/
│   ├── cli.py                  # Click CLI
│   ├── mcp_server.py           # MCP server (3 tools: search, scope, refresh)
│   ├── config.py               # Global + per-repo config
│   ├── ingestion/
│   │   ├── scanner.py          # .gitignore-aware file discovery
│   │   ├── chunker.py          # AST-aware code chunking (Python)
│   │   ├── embedder.py         # sentence-transformers wrapper
│   │   ├── build_graph.py      # Orchestrates parsers into NetworkX graph
│   │   └── parsers/            # Docker Compose, pyproject.toml, proto
│   ├── storage/
│   │   ├── vector_store.py     # ChromaDB (local persistent)
│   │   ├── metadata_db.py      # SQLite (file index, content hashes)
│   │   └── graph_store.py      # NetworkX + JSON serialization
│   ├── tools/                  # MCP tool implementations
│   │   ├── scope.py            # scope_task -- primary daily workflow tool
│   │   ├── search.py           # Semantic code search
│   │   └── refresh.py          # Git fetch + delta re-index
│   └── generators/
│       └── architecture.py     # AGENTS.md injection + subagent generator
```

## Generated Files in Target Repos

`repo-brain generate-docs` creates these files in the target repo:

| File | Purpose | Committed? |
|------|---------|------------|
| `AGENTS.md` (injected section) | Codebase overview for LLM context | Yes |
| `.opencode/agents/repo-brain.md` | Custom subagent definition | Yes |
| `.repo-brain/codebase-overview.md` | Reference copy of the overview | No (gitignored) |

It also generates internal docs at `~/.repo-brain/repos/<slug>/docs/`:

```
~/.repo-brain/repos/<slug>/
├── config.toml        # Repo settings
├── chroma/            # Vector embeddings (~500MB for large repos)
├── metadata.db        # SQLite file index
├── graph.json         # Dependency graph (NetworkX JSON)
└── docs/
    ├── architecture.md    # Full architecture doc
    ├── service_map.json   # Structured service data
    ├── domain_terms.md    # Domain vocabulary
    └── gotchas.md         # Known pitfalls
```

## Key Design Decisions

- **Zero infrastructure** -- no Docker, no external services. Everything runs locally
- **Custom subagent** -- works with OpenCode's architecture instead of fighting the system prompt
- **AGENTS.md injection** -- static knowledge delivered without tool calls, idempotent updates
- **MCP server** -- OpenCode spawns it as a subprocess via stdio, not HTTP
- **Multi-repo** -- each repo gets isolated storage, auto-detected by working directory
- **Incremental indexing** -- SHA-256 content hashing, only re-embeds changed files
- **Local embedding model** -- `all-MiniLM-L6-v2` runs on-device, no API costs
- **3 tools only** -- minimal token overhead from tool definitions (~85% cached by providers after first turn)

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended for installation)

## License

Private.
