"""MCP server for repo-brain.

This is the entry point that OpenCode spawns as a subprocess.
Run with: python -m repo_brain.mcp_server

Performance note: expensive resources (ChromaDB client, embedding model,
graph store) are initialised once at startup and cached for the lifetime
of the server process.  Individual tool calls therefore pay only the cost
of the actual query, not of loading ~300 MB of state.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any

from mcp.server.fastmcp import FastMCP

from repo_brain.config import RepoConfig, find_repo_config_by_path, load_repo_config

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

MCP_INSTRUCTIONS = """\
repo-brain has pre-indexed this entire repository (parsed, chunked, embedded). \
Its tools return instant results without filesystem scanning, so they are the \
recommended way to research the codebase before falling back to grep/glob/Read.

Tool overview:
- scope_task — best starting point for planning: development plans, Jira \
tickets, figuring out affected files/services
- search_code — semantic search by concept ("authentication flow", "error \
handling in payments") rather than exact keyword
- get_architecture — repo overview, service boundaries, data flows, tech stack
- get_service_info — deep dive into one specific service or module
- query_dependencies — impact analysis, "what depends on X?", coupling

Prefer grep/glob/Read only when you already know the exact file path or need \
precise keyword/symbol matches that semantic search cannot provide.\
"""

mcp = FastMCP(
    "repo-brain",
    instructions=MCP_INSTRUCTIONS,
)


# ── Singleton resource cache ────────────────────────────────────────
#
# The MCP server is a long-running subprocess.  We cache expensive
# resources (ChromaDB client, embedding model, graph, metadata DB) so
# they are loaded once on startup rather than once per tool call.


class _ServerResources:
    """Lazy-but-cached holder for all expensive resources.

    Call ``warmup()`` once during startup to pay the initialisation cost
    up-front.  After that every property access returns the cached instance.
    """

    def __init__(self) -> None:
        self._config: RepoConfig | None = None
        self._config_resolved = False

        # Cached stores — populated by warmup() or on first access.
        # Use Any to avoid importing heavy modules at module level.
        self._vector_store: Any = None
        self._metadata_db: Any = None
        self._graph_store: Any = None

    # -- config -------------------------------------------------------

    def _resolve_config(self) -> RepoConfig | None:
        """Resolve the repo config from environment or auto-detect."""
        config: RepoConfig | None = None

        repo_path = os.environ.get("REPO_PATH", "")
        if repo_path:
            config = find_repo_config_by_path(repo_path)

        if not config:
            repo_slug = os.environ.get("REPO_SLUG", "")
            if repo_slug:
                config = load_repo_config(repo_slug)

        if not config:
            cwd = os.getcwd()
            config = find_repo_config_by_path(cwd)

        if config:
            env_token = os.environ.get("GITHUB_TOKEN", "")
            if env_token and not config.github_token:
                config.github_token = env_token

        return config

    @property
    def config(self) -> RepoConfig | None:
        if not self._config_resolved:
            self._config = self._resolve_config()
            self._config_resolved = True
        return self._config

    # -- vector store -------------------------------------------------

    @property
    def vector_store(self):
        """Return cached VectorStore (created on first access)."""
        if self._vector_store is None and self.config is not None:
            from repo_brain.storage.vector_store import VectorStore

            self._vector_store = VectorStore(self.config)
        return self._vector_store

    # -- metadata db --------------------------------------------------

    @property
    def metadata_db(self):
        """Return cached MetadataDB (created on first access)."""
        if self._metadata_db is None and self.config is not None:
            from repo_brain.storage.metadata_db import MetadataDB

            self._metadata_db = MetadataDB(self.config)
        return self._metadata_db

    # -- graph store --------------------------------------------------

    @property
    def graph_store(self):
        """Return cached GraphStore (created on first access)."""
        if self._graph_store is None and self.config is not None:
            from repo_brain.storage.graph_store import GraphStore

            self._graph_store = GraphStore(self.config)
        return self._graph_store

    # -- warmup -------------------------------------------------------

    def warmup(self) -> None:
        """Eagerly initialise all expensive resources.

        Called once from ``main()`` so the first tool call is fast.
        """
        if self.config is None:
            logger.warning("repo-brain: no repo config found — tools will return errors")
            return

        t0 = time.time()
        logger.info("repo-brain: warming up resources for '%s' ...", self.config.name)

        # 1. ChromaDB persistent client (biggest cost)
        _ = self.vector_store
        logger.info("  ✓ VectorStore ready (%.1fs)", time.time() - t0)

        # 2. Embedding model — stored in embedder._model_cache
        t1 = time.time()
        try:
            from repo_brain.ingestion.embedder import get_model

            get_model(self.config.embedding_model)
            logger.info("  ✓ Embedding model ready (%.1fs)", time.time() - t1)
        except Exception as exc:
            logger.warning("  ✗ Embedding model failed to load: %s", exc)

        # 3. MetadataDB (cheap, but cache it)
        t2 = time.time()
        _ = self.metadata_db
        logger.info("  ✓ MetadataDB ready (%.1fs)", time.time() - t2)

        # 4. GraphStore (reads JSON, moderate)
        t3 = time.time()
        _ = self.graph_store
        logger.info("  ✓ GraphStore ready (%.1fs)", time.time() - t3)

        logger.info("repo-brain: warmup complete (%.1fs total)", time.time() - t0)


# Module-level singleton — created when the module loads, warmed in main().
_resources = _ServerResources()


def _get_freshness_line() -> str:
    """Build an index freshness summary line for tool outputs."""
    try:
        db = _resources.metadata_db
        if db is None:
            return ""
        stats = db.get_stats()

        file_count = stats.get("total_files", 0)
        last_run = stats.get("last_index_run", "")

        parts = [f"{file_count} files indexed"]
        if last_run:
            parts.append(f"last updated {last_run}")
        return f"[Index: {', '.join(parts)}]"
    except Exception:
        return ""


@mcp.resource(
    "repo://architecture",
    name="architecture",
    title="Repository Architecture Overview",
    description="Full architecture document with service boundaries, dependencies, "
    "data flows, and infrastructure. Auto-loaded at session start.",
    mime_type="text/markdown",
)
def architecture_resource() -> str:
    """Serve architecture.md as an MCP resource for auto-loading."""
    config = _resources.config
    if not config:
        return "No repo configured. Run `repo-brain init <path>` first."

    from repo_brain.tools.architecture import get_architecture as _get_arch

    return _get_arch(config)


@mcp.tool()
def search_code(query: str, limit: int = 10, service: str = "", language: str = "") -> str:
    """Semantic code search — finds code by concept rather than exact keyword match.

    Useful for queries like "authentication logic", "database migration",
    "error handling in payments", etc. The entire repo is pre-indexed so
    results are instant.

    Args:
        query: Natural language description of what you're looking for.
        limit: Maximum number of results (default 10).
        service: Optional service name filter (e.g., "auth-service").
        language: Optional language filter (e.g., "python", "go").
    """
    config = _resources.config
    if not config:
        return "Error: No repo configured. Run `repo-brain init <path>` first."

    from repo_brain.tools.search import search_code as _search

    results = _search(
        query=query,
        config=config,
        limit=limit,
        service_filter=service or None,
        language_filter=language or None,
        vector_store=_resources.vector_store,
    )

    if not results:
        return "No results found."

    output_parts: list[str] = []

    # Freshness metadata
    freshness = _get_freshness_line()
    if freshness:
        output_parts.append(freshness)
        output_parts.append("")

    for i, r in enumerate(results, 1):
        header = f"[{i}] {r['file_path']}"
        if r["symbol_name"]:
            header += f" — {r['symbol_type']}: {r['symbol_name']}"
        if r["service"]:
            header += f" (service: {r['service']})"
        header += f"  [score: {r['score']}]"

        output_parts.append(header)
        output_parts.append(f"    Lines {r['line_start']}-{r['line_end']}")
        if r["snippet"]:
            # Indent snippet
            snippet_lines = r["snippet"].splitlines()[:15]
            for line in snippet_lines:
                output_parts.append(f"    {line}")
        output_parts.append("")

    output_parts.append("---")
    output_parts.append("**Follow-up repo-brain tools:**")
    output_parts.append("- `search_code(query)` with a refined query to narrow results")
    # Extract unique services from results for a targeted suggestion
    svc_names = sorted({r["service"] for r in results if r.get("service")})
    if svc_names:
        output_parts.append(
            f"- `get_service_info(service_name)` — details on {', '.join(svc_names[:3])}"
        )
    output_parts.append("- `query_dependencies(module)` — check impact before changing these files")
    output_parts.append("- Read files directly when you plan to edit them.")

    return "\n".join(output_parts)


@mcp.tool()
def get_architecture() -> str:
    """Full architecture overview — service boundaries, data flows, infrastructure.

    Useful when the user asks about repo structure, how services connect,
    what technologies are used, or for a high-level understanding of the codebase.
    """
    config = _resources.config
    if not config:
        return "Error: No repo configured. Run `repo-brain init <path>` first."

    from repo_brain.tools.architecture import get_architecture as _get_arch

    output = _get_arch(config)

    # Append follow-up tool suggestions
    output += (
        "\n\n---\n"
        "**Follow-up repo-brain tools:**\n"
        "- `scope_task(description)` — plan work based on this architecture\n"
        "- `search_code(query)` — find implementations of specific components\n"
        "- `get_service_info(service_name)` — deep dive into one service\n"
        "- `query_dependencies(module)` — trace dependencies between modules"
    )

    return output


@mcp.tool()
def get_service_info(service_name: str) -> str:
    """Detailed information about a specific service or module.

    Returns its purpose, dependencies, key files, and configuration.

    Args:
        service_name: Name of the service (e.g., "auth-service", "rest-api", "rule-mcp").
    """
    config = _resources.config
    if not config:
        return "Error: No repo configured. Run `repo-brain init <path>` first."

    from repo_brain.tools.architecture import get_service_info as _get_svc

    info = _get_svc(
        service_name,
        config,
        vector_store=_resources.vector_store,
        graph_store=_resources.graph_store,
    )

    # Append follow-up tool suggestions
    info["follow_up_tools"] = [
        "search_code(query) — find specific code within this service",
        "query_dependencies(module) — see what depends on this service",
        "scope_task(description) — plan changes involving this service",
    ]

    return json.dumps(info, indent=2)


@mcp.tool()
def query_dependencies(module: str, direction: str = "both", depth: int = 3) -> str:
    """Dependency graph query — what does module X depend on, and what depends on X?

    Useful for impact analysis ("what would break if I change X?"), understanding
    coupling, or tracing data flow between services.

    Args:
        module: Module or service name to query.
        direction: "up" (dependencies), "down" (dependents), or "both".
        depth: How many levels deep to traverse (default 3).
    """
    config = _resources.config
    if not config:
        return "Error: No repo configured. Run `repo-brain init <path>` first."

    from repo_brain.tools.dependencies import query_dependencies as _query_deps

    result = _query_deps(
        module=module,
        config=config,
        direction=direction,
        depth=depth,
        graph_store=_resources.graph_store,
    )

    # Append follow-up tool suggestions
    result["follow_up_tools"] = [
        "search_code(query) — find code related to these dependencies",
        "get_service_info(service_name) — details on a specific dependent service",
        "scope_task(description) — plan a change with impact awareness",
    ]

    return json.dumps(result, indent=2)


@mcp.tool()
def scope_task(description: str) -> str:
    """Plan and scope a task — identifies affected services, key files, dependencies, and risks.

    Useful for development plans, Jira tickets, feature requests, or bug reports.
    Returns affected services, key files to read, dependency context,
    risk assessment, and a suggested reading order.

    Args:
        description: The full ticket text, feature request, bug report, or
            natural language description of the work. More detail produces
            better results.
    """
    config = _resources.config
    if not config:
        return "Error: No repo configured. Run `repo-brain init <path>` first."

    from repo_brain.tools.scope import format_scope_result
    from repo_brain.tools.scope import scope_task as _scope

    result = _scope(
        description=description,
        config=config,
        vector_store=_resources.vector_store,
        graph_store=_resources.graph_store,
    )
    output = format_scope_result(result)

    # Prepend freshness metadata
    freshness = _get_freshness_line()
    if freshness:
        output = f"{freshness}\n\n{output}"

    return output


@mcp.tool()
def refresh_index(pull: bool = True) -> str:
    """Refresh the code index by pulling latest changes and re-indexing modified files.

    Args:
        pull: Whether to git fetch from remote before indexing (default True).
    """
    config = _resources.config
    if not config:
        return "Error: No repo configured. Run `repo-brain init <path>` first."

    from repo_brain.tools.refresh import refresh_index as _refresh

    result = _refresh(config, pull=pull)
    return json.dumps(result, indent=2)


@mcp.tool()
def index_status() -> str:
    """Show the current index status — file counts, staleness, and last run info."""
    config = _resources.config
    if not config:
        return "Error: No repo configured. Run `repo-brain init <path>` first."

    db = _resources.metadata_db
    if db is None:
        return "Error: MetadataDB not available."
    stats = db.get_stats()

    vs = _resources.vector_store
    if vs is not None:
        stats["vector_store_chunks"] = vs.count

    return json.dumps(stats, indent=2, default=str)


def main() -> None:
    """Entry point for the MCP server."""
    # Eagerly warm all expensive resources before accepting tool calls
    _resources.warmup()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
