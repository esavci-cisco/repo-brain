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

This repo has a repo-brain MCP server with persistent context about the
codebase architecture, dependencies, and code locations.

Use repo-brain first when you need to understand what's affected, how things
connect, or where relevant code lives — before launching Explore agents or
grepping across the codebase:

- `scope_task(description)` — starting any new work, or understanding how
  a feature/system works across services
- `get_architecture` — repo structure and service overview
- `get_service_info(service_name)` — focused context for a known service
- `query_dependencies(module)` — impact analysis before changing shared code
- `search_code(query)` — finding code by concept, not by name

Use built-in tools (grep, glob, Read) when:
- You already know which file or service to look at
- You need exact keyword or symbol matches
- You're reading/editing specific files during implementation

One scope_task call at the start of a task replaces minutes of codebase
exploration. Do not call multiple repo-brain tools preemptively.
```

## MCP Tools

repo-brain is a **session starter**, not a per-prompt tool. It front-loads the context so the rest of the session is pure implementation -- one call eliminates the discovery phase, then OpenCode works with actual code using its built-in tools (Read, Edit, grep, LSP).

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

## Curating Your Docs (Highest ROI Activity)

`repo-brain generate-docs` creates starter docs at `~/.repo-brain/repos/<slug>/docs/`. These are **skeletons** -- auto-generated from scanning pyproject.toml files, compose.yml, and directory structure. They list services with their path, language, and framework, but nothing more.

The real value comes from **editing these docs** with the things only you know. repo-brain will never overwrite your edits. Every line you add saves you from explaining it to OpenCode in future sessions -- this is persistent memory.

### architecture.md

This is what `get_architecture()` returns to OpenCode. The generated version looks like this:

```markdown
### rest-api

- **Path**: `services/rest-api`
- **Type**: service
- **Language**: python
- **Framework**: FastAPI
- **Description**: REST API service for FAA Test & Validation Platform
```

That tells OpenCode almost nothing useful. Edit it to include what you actually know:

```markdown
### rest-api

- **Path**: `services/rest-api`
- **Type**: service
- **Language**: python
- **Framework**: FastAPI
- **Description**: REST API service for FAA Test & Validation Platform

The main external-facing API. All UI requests go through nginx -> rest-api.
Handles user auth (JWT via auth-service), topology CRUD, rule management,
and evaluation orchestration.

**Key patterns:**
- Uses gRPC client to talk to rule-grpc-api for all rule operations
- Evaluation requests are async: rest-api publishes to Kafka, 
  event-swarm-node picks them up
- Database access via SQLAlchemy + faa-models (shared library)
- All endpoints require JWT auth except /health and /docs

**Data flow:**
- Reads/writes: PostgreSQL (via faa-models)
- Reads: Neo4j (rule graph queries), ChromaDB (semantic rule search)
- Publishes to: Kafka (evaluation events, audit events)
- Depends on: auth-service, rule-grpc-api, faa-models, faa-config

**Watch out:**
- Don't add new SQLAlchemy models here -- they go in faa-models (shared lib)
- The rule endpoints are thin wrappers around gRPC calls, don't add rule 
  logic here
- Alembic migrations are in postgres-init, NOT in rest-api
```

The more context you add, the less time OpenCode spends exploring. When someone asks "add a new endpoint to rest-api," OpenCode reads this and immediately knows: use SQLAlchemy via faa-models, add the route in the routers directory, don't put migrations here.

**What to add per service:**
- What it actually does in business terms (not just "FastAPI service")
- How data flows in and out (which databases, queues, other services)
- Key patterns and conventions (how to add a new endpoint, where models live)
- What NOT to do (common mistakes, things that belong in other services)
- Which services it's tightly coupled with

You can also add top-level sections that aren't per-service:

```markdown
## Data Flow Overview

UI -> nginx -> rest-api -> PostgreSQL (CRUD)
                       |-> rule-grpc-api -> Neo4j (rules)
                       |-> Kafka -> event-swarm-node -> swarm-node (evaluations)
                                                    |-> TimescaleDB (metrics)

## Shared Libraries

All Python services depend on these. Changes here affect everything:
- faa-models: SQLAlchemy models, Pydantic schemas. THE source of truth for data shapes.
- faa-config: Environment config loading, secrets management.
- faa-responses: Standard API response format. Every service uses this.
```

### domain_terms.md

Generated as an empty table. Fill it with business vocabulary that an outsider wouldn't know:

```markdown
| Term | Meaning |
|------|---------|
| CATL | Cisco Automated Testing Library -- the 1,521 rules we evaluate devices against |
| Topology | A collection of network devices being tested together (not network topology) |
| Evaluation | Running CATL rules against a device's config to check compliance |
| Golden template | The expected "correct" config for a device type/platform |
| Swarm node | An agent instance that executes evaluations on a device |
| Platform | Network OS type: IOS-XE, IOS-XR, NX-OS, ASA, or FTD |
| RadKit | Cisco's Remote Automation and Diagnostics Kit -- SSH proxy for device access |
```

This gets loaded when OpenCode asks "what is X?" and prevents it from guessing wrong about domain-specific terms.

### gotchas.md

Generated as an empty skeleton. Fill it with things you've learned the hard way:

```markdown
## Known Issues

- Neo4j connection pool exhaustion: if you open connections in a loop without
  closing them, Neo4j hits the max connection limit (100). Always use the 
  neo4j_client context manager.
- ChromaDB collection names can't have dots. Service names with dots get 
  sanitized, but if you manually create collections, use underscores.

## Common Mistakes

- Adding SQLAlchemy models in service code instead of faa-models. Every service
  imports models from faa-models -- if you add a model in rest-api, other 
  services can't see it.
- Running migrations from the wrong service. Alembic migrations ONLY run from
  postgres-init. Don't create migration files in rest-api or evaluations.
- Forgetting to update the proto files when changing gRPC interfaces. The proto
  files in proto/ are the source of truth -- generated code in services is 
  derived from them.

## Edge Cases

- Device configs with mixed indentation (tabs + spaces) break the golden 
  template comparison. The normalizer handles this but only if you use 
  compare_normalized(), not raw string comparison.
```

### How Often to Update

You don't need to update these constantly. Good times to add to them:

- After finishing a complex ticket (write down what you learned)
- After debugging something non-obvious (add it to gotchas)
- When onboarding someone and explaining how things work (that explanation belongs in architecture.md)
- When OpenCode gets something wrong because it didn't know a domain concept (add to domain_terms.md)

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
