# repo-brain — Setup & Usage Guide

## What repo-brain does

repo-brain is a local MCP server that gives OpenCode persistent memory about your codebase. Without it, every OpenCode session starts from zero and you have to tell it to research the codebase every time.

The primary value is **architecture context loading** — OpenCode calls `get_architecture` and instantly knows your service map, data stores, and infrastructure. No filesystem exploration needed.

It also provides:
- **Semantic code search** for finding code by concept when grep won't work
- **Service-level context** for focused info about a specific service
- **Dependency queries** for impact analysis before changing shared code (Phase 2)

All data is stored locally in `~/.repo-brain/`. No Docker, no server process, no cloud.

---

## Quick Start

```bash
# 1. Install globally
uv tool install /path/to/repo-brain

# 2. Register your repo
repo-brain init /path/to/your/repo

# 3. Generate architecture docs (the main value)
repo-brain generate-docs

# 4. Build the dependency graph
repo-brain build-graph

# 5. Index the codebase (for semantic search)
repo-brain index

# 6. (Optional) Save embedding model locally for faster search
repo-brain export-model

# 7. Add MCP config to your repo's opencode.json
# 8. Add instructions to your repo's AGENTS.md
```

---

## Installation

### 1. Install repo-brain

```bash
uv tool install /path/to/repo-brain
```

This installs `repo-brain` globally on your PATH (at `~/.local/bin/repo-brain`) with all dependencies in an isolated environment managed by uv. No venv activation needed — just run `repo-brain` from anywhere.

To upgrade after code changes:

```bash
uv tool install /path/to/repo-brain --force --reinstall
```

### 2. Initialize a repository

```bash
repo-brain init /path/to/your/repo
```

This registers the repo, auto-detects the git remote and branch, and creates a config at `~/.repo-brain/repos/<repo-slug>/config.toml`.

### 3. Generate architecture docs

```bash
repo-brain generate-docs
```

This is the highest-value step. Creates starter docs at `~/.repo-brain/repos/<slug>/docs/`:
- `architecture.md` — service map, frameworks, data stores
- `service_map.json` — structured dependency data
- `domain_terms.md` — skeleton for business vocabulary (you fill this in)
- `gotchas.md` — skeleton for known traps (you fill this in)

**These are starting points.** Edit them to add real domain knowledge — what each service does, how data flows, what the gotchas are. repo-brain will never overwrite your edits. The more you curate these, the better OpenCode performs.

#### Curating the docs (highest ROI thing you can do)

The generated docs give OpenCode the skeleton. But the real value comes from adding the things only you know. Open `~/.repo-brain/repos/<slug>/docs/architecture.md` and add:

- **What each service actually does** in business terms (not just "FastAPI service")
- **How data flows** between services (e.g., "rest-api writes to Kafka → event-swarm-node consumes → writes evaluation results to Postgres")
- **Which services are critical** vs experimental or deprecated
- **Which services are tightly coupled** and which are independent
- **Common pitfalls** when working in specific areas of the codebase

Do the same for `domain_terms.md` (business vocabulary that an outsider wouldn't know) and `gotchas.md` (the things you've learned the hard way).

Every line you add saves you from explaining it to OpenCode in future sessions. This is persistent memory — write it once, benefit forever.

### 4. Build the dependency graph

```bash
repo-brain build-graph
```

Parses `compose.yml`, all `pyproject.toml` files, and `.proto` files to build a unified dependency graph. This powers `query_dependencies` and enriches `get_service_info` with upstream/downstream data.

For the FAA repo, this finds 63 nodes and 84 edges in under a second.

### 5. Index the codebase

```bash
repo-brain index
```

Full index: scans all files, chunks them (AST-aware for Python, sliding window for others), generates embeddings, and stores them in local ChromaDB.

For a ~4,300 file repo, this takes about 60 seconds on an M-series Mac.

### 5. (Optional) Save embedding model locally

```bash
repo-brain export-model
```

One-time operation. Saves the embedding model to `~/.repo-brain/models/` so future searches skip HuggingFace network checks. Shaves ~2 seconds off each search.

### 6. Wire into OpenCode

Add the `mcp` section to your target repo's `opencode.json`:

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

Since `repo-brain` is installed globally via `uv tool`, OpenCode can find it directly on your PATH.

**GITHUB_TOKEN** (optional): Only needed by the `refresh_index` tool (which runs `git fetch`). You can omit it if:
- Your repo is public
- You use SSH remotes (`git@github.com:...`)
- You have a git credential helper configured (`gh auth login`, macOS Keychain, etc.)

If you need it, add `"GITHUB_TOKEN": "{env:GITHUB_TOKEN}"` to the environment block.

### 7. Add to AGENTS.md (Important)

Add this to your repo's `AGENTS.md`. Without this, OpenCode will still launch Task agents to explore the filesystem even though repo-brain already has the answer. This instruction prevents that:

```markdown
## repo-brain

This repo has a repo-brain MCP server with persistent architecture context and a
dependency graph.

When to use repo-brain vs built-in tools:

- "What services exist / how is the repo structured?" → `get_architecture` (no exploration needed)
- "What does service X depend on?" → `get_service_info(service_name)` (no exploration needed)
- "What would break if I change X?" → `query_dependencies(module)` (no exploration needed)
- "Where is Y implemented?" (fuzzy/conceptual) → `search_code(query)`
- Implementation planning (e.g., "add feature X") → explore actual code with grep/Read as normal
- Exact names or keywords → grep/glob

Do NOT call multiple repo-brain tools preemptively. Only call the one that fits the question.
```

---

## When to index

### Short answer

- **Full index**: Once, on first setup. Then only if you change skip patterns or want a clean rebuild.
- **Incremental index**: Run `repo-brain index` periodically. It skips unchanged files automatically.
- **Refresh**: Run `repo-brain refresh` to pull latest from remote and re-index only changed files.

### How incremental indexing works

repo-brain tracks a SHA-256 hash for every indexed file in SQLite. When you run `repo-brain index`:

1. It scans all files in the repo
2. For each file, it computes the content hash
3. If the hash matches what's stored → **skip** (no re-embedding)
4. If the hash is different → **re-embed** only that file's chunks
5. If a file was deleted → **remove** its chunks from the vector store

This means running `repo-brain index` after a few file changes takes seconds, not minutes.

### Recommended workflow

| Situation | Command | Time |
|-----------|---------|------|
| First time setup | `repo-brain index` | ~60s for 4K files |
| After changing compose/toml/proto | `repo-brain build-graph` | ~1s |
| After pulling new code | `repo-brain index` | ~5-15s (only changed files) |
| Pull + re-index in one step | `repo-brain refresh` | ~5-15s (git fetch + delta) |
| Something feels stale | `repo-brain index` | Seconds if few changes |
| Changed skip patterns or config | `repo-brain index --full` | ~60s (full rebuild) |
| Check what's indexed | `repo-brain status` | Instant |

### You do NOT need to re-index every session

The index persists in `~/.repo-brain/`. It survives across OpenCode sessions, terminal restarts, and reboots. Once indexed, the data is there until you explicitly delete it or re-index.

Think of it like a database: you load data once, then query it many times.

### When the index gets stale

The index becomes stale when:
- Teammates push new code to the repo and you pull it
- You make significant local changes across many files
- You add new services or delete old ones

For day-to-day work where you're editing a few files, the existing index is fine. Run `repo-brain index` when it matters — before a big architecture question or cross-service refactor.

---

## CLI Reference

```
repo-brain init <path>         # Register a repo
repo-brain index [--full]      # Index (incremental by default)
repo-brain build-graph         # Build dependency graph from compose/toml/proto
repo-brain refresh [--no-pull] # Git fetch + re-index delta
repo-brain generate-docs       # Generate architecture docs (one-shot)
repo-brain export-model        # Save embedding model locally (one-time)
repo-brain search <query>      # Search from terminal
repo-brain status              # Show index stats
repo-brain list                # List registered repos
repo-brain serve               # Start MCP server (OpenCode does this automatically)
```

---

## MCP Tools (what OpenCode sees)

| Tool | What it does | When to use |
|------|-------------|-------------|
| `get_architecture()` | Returns the full architecture.md | **Primary tool** — architecture questions |
| `get_service_info(service_name)` | Returns focused info about one service | Working on a specific service |
| `search_code(query, limit, service, language)` | Semantic search across the codebase | Finding code by concept, not by name |
| `query_dependencies(module, direction, depth)` | Dependency graph traversal | Impact analysis before changing shared code |
| `refresh_index(pull)` | Pull latest + re-index changed files | Updating the index |
| `index_status()` | File counts, staleness, last run info | Checking index health |

---

## Multi-repo usage

repo-brain supports multiple repos. Each gets its own isolated storage:

```bash
repo-brain init /path/to/repo-a --name repo-a
repo-brain init /path/to/repo-b --name repo-b
repo-brain list  # Shows both repos
```

Data is stored at `~/.repo-brain/repos/<slug>/` per repo. The MCP server auto-detects which repo to use based on the `REPO_PATH` environment variable.

---

## Data location

Everything lives under `~/.repo-brain/`:

```
~/.repo-brain/
├── config.toml                      # Global settings
├── models/                          # Locally saved embedding models (optional)
└── repos/
    └── <repo-slug>/
        ├── config.toml              # Repo settings (path, remote, model)
        ├── chroma/                  # Vector embeddings (~500MB for large repos)
        ├── metadata.db              # SQLite file index (~1MB)
        ├── graph.json               # Dependency graph (Phase 2)
        └── docs/
            ├── architecture.md      # Edit this! Add domain knowledge
            ├── service_map.json     # Structured service data
            ├── domain_terms.md      # Edit this! Add vocabulary
            └── gotchas.md           # Edit this! Add known traps
```

To completely reset a repo's index: delete the `<repo-slug>/` directory and re-run `repo-brain init` + `repo-brain index`.

---

## Troubleshooting

**"No repo configured" error**: Run `repo-brain init <path>` first, or set the `REPO_PATH` environment variable.

**Search returns irrelevant vendored code**: Add skip patterns to `~/.repo-brain/repos/<slug>/config.toml` under `extra_skip_patterns`, then run `repo-brain index --full`.

**MCP server not connecting in OpenCode**: Make sure `repo-brain` is on your PATH (`which repo-brain`). If not, run `uv tool install /path/to/repo-brain` again. Test with `repo-brain serve` to verify the server starts.

**OpenCode still launches Task agents for architecture questions**: Make sure you added the repo-brain section to your `AGENTS.md` (step 7). Without it, OpenCode doesn't know to trust repo-brain and will redundantly explore the filesystem.

**Index seems slow**: First run downloads the embedding model (~90MB). Run `repo-brain export-model` to save it locally and skip network checks on future runs.
