# repo-brain

Persistent repo intelligence MCP server for [OpenCode](https://opencode.ai). Gives your AI coding assistant architectural memory that survives across sessions.

## The Problem

Every new OpenCode session starts from zero. On a large codebase (34+ microservices, ~4,300 files), the AI wastes time rediscovering the same things: which services exist, how they connect, where the relevant code lives. You end up saying "research the codebase" at the start of every conversation.

## What repo-brain Does

repo-brain runs as a local MCP server that OpenCode spawns automatically. It provides persistent, pre-computed knowledge:

- **Task scoping** -- describe what you want to do, get back affected services, key files, dependencies, and risks in one call
- **Architecture context** -- service map, data stores, infrastructure loaded instantly
- **Dependency graph** -- upstream/downstream impact analysis from Docker Compose, pyproject.toml, and proto files
- **Semantic code search** -- find code by concept when grep won't work
- **Incremental indexing** -- re-index only changed files, keeps context fresh

All data is stored locally at `~/.repo-brain/`. No Docker, no external services, no cloud.

## Quick Start

```bash
# Install globally
uv tool install /path/to/repo-brain

# Register and index your repo
repo-brain init /path/to/your/repo
repo-brain generate-docs
repo-brain build-graph
repo-brain index

# Add MCP config to your repo's opencode.json
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

Add to your repo's `AGENTS.md`:

```markdown
## repo-brain

Starting a new task (feature, ticket, bug fix):
- Call `scope_task(description)` first -- returns affected services, key files, deps, and risks.

Targeted queries:
- "What is this repo?" -> `get_architecture`
- "Tell me about service X" -> `get_service_info(service_name)`
- "What breaks if I change X?" -> `query_dependencies(module)`
- "Find code that does X" (fuzzy) -> `search_code(query)`
- Exact names or keywords -> grep/glob (built-in tools are faster)
```

## MCP Tools

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `scope_task(description)` | Scope any new task -- returns affected services, key files, deps, risks | Starting any new work |
| `get_architecture()` | Full architecture overview | "What is this repo?" |
| `get_service_info(service)` | Service-specific context with key files | Working on a known service |
| `query_dependencies(module)` | Upstream/downstream dependency traversal | Impact analysis |
| `search_code(query)` | Semantic code search | Finding code by concept |
| `refresh_index(pull)` | Git fetch + re-index changed files | Updating the index |
| `index_status()` | File counts, staleness info | Checking index health |

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
  - Depends on: neo4j, kg-schema

### Key Files to Read
1. mcp_servers/rule-mcp/app/src/rule_mcp_server/neo4j_client.py
2. services/rule-grpc-api/src/rule_grpc_api/mcp/neo4j_tools.py
3. services/neo4j-init/init_neo4j.py
...

### Risk Assessment
- LOW RISK: Changes appear localized to specific services.

### Suggested Reading Order
1. Service rule-grpc-api: neo4j_tools.py, client.py
2. Service rule-mcp: neo4j_client.py, server.py
3. Service neo4j-init: README.md, init_neo4j.py
```

OpenCode gets this context in one tool call instead of spending minutes exploring the codebase from scratch.

## CLI Commands

```
repo-brain init <path>         # Register a repo
repo-brain index [--full]      # Index codebase (incremental by default)
repo-brain build-graph         # Build dependency graph from compose/toml/proto
repo-brain generate-docs       # Generate architecture docs (one-shot, then curate)
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
│   ├── mcp_server.py           # MCP server entry point (7 tools)
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
│   │   ├── architecture.py     # Architecture doc serving
│   │   ├── dependencies.py     # Dependency graph queries
│   │   └── refresh.py          # Git fetch + delta re-index
│   └── generators/
│       └── architecture.py     # Auto-generates starter docs
```

## Data Storage

All data lives at `~/.repo-brain/repos/<repo-slug>/`:

```
~/.repo-brain/repos/<slug>/
├── config.toml        # Repo settings
├── chroma/            # Vector embeddings (~500MB for large repos)
├── metadata.db        # SQLite file index
├── graph.json         # Dependency graph (NetworkX JSON)
└── docs/
    ├── architecture.md    # Generated, then manually curated
    ├── service_map.json   # Structured service data
    ├── domain_terms.md    # Domain vocabulary
    └── gotchas.md         # Known pitfalls
```

## Key Design Decisions

- **Zero infrastructure** -- no Docker, no external services. Everything runs locally
- **MCP server** -- OpenCode spawns it as a subprocess via stdio, not HTTP
- **Multi-repo** -- each repo gets isolated storage, auto-detected by working directory
- **Incremental indexing** -- SHA-256 content hashing, only re-embeds changed files
- **Architecture docs are the primary value** -- curated docs loaded in one call provide more value than search
- **`scope_task` is the daily driver** -- one tool call replaces 10 minutes of codebase exploration
- **Local embedding model** -- `all-MiniLM-L6-v2` runs on-device, no API costs

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended for installation)

## License

Private.
