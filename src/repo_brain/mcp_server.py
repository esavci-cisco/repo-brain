"""MCP server for repo-brain.

This is the entry point that OpenCode spawns as a subprocess.
Run with: python -m repo_brain.mcp_server

The server exposes two main tools: scope_task (planning) and search_code
(semantic search).  Architecture knowledge is delivered statically via
AGENTS.md to minimise per-session token overhead.

Performance note: expensive resources (ChromaDB client, embedding model,
graph store) are initialised once at startup and cached for the lifetime
of the server process.
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
repo-brain has a pre-built semantic index of this repository.
- scope_task — plan work: pass a ticket/feature/bug to get affected files, deps, risks
- search_code — find code by concept ("authentication flow") rather than keyword\
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
    """Build a compact index freshness note."""
    try:
        db = _resources.metadata_db
        if db is None:
            return ""
        stats = db.get_stats()
        file_count = stats.get("total_files", 0)
        last_run = stats.get("last_index_run", "")
        if file_count:
            parts = [f"{file_count} files"]
            if last_run:
                parts.append(f"updated {last_run}")
            return f"[Index: {', '.join(parts)}]"
    except Exception:
        pass
    return ""


@mcp.tool()
def search_code(query: str, limit: int = 10, service: str = "", language: str = "") -> str:
    """Semantic code search — finds code by concept rather than exact keyword.

    Args:
        query: Natural language description of what you're looking for.
        limit: Maximum number of results (default 10).
        service: Optional service name filter.
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

    freshness = _get_freshness_line()
    if freshness:
        output_parts.append(freshness)
        output_parts.append("")

    for i, r in enumerate(results, 1):
        # Compact: [1] file_path:line — symbol  [score]
        header = f"[{i}] {r['file_path']}:{r['line_start']}"
        if r["symbol_name"]:
            header += f" — {r['symbol_type']}: {r['symbol_name']}"
        if r["service"]:
            header += f" ({r['service']})"
        header += f"  [{r['score']}]"
        output_parts.append(header)

        # Show only first 3 lines of snippet
        if r["snippet"]:
            snippet_lines = r["snippet"].splitlines()[:3]
            for line in snippet_lines:
                output_parts.append(f"    {line}")
        output_parts.append("")

    return "\n".join(output_parts)


@mcp.tool()
def scope_task(description: str) -> str:
    """Plan and scope a task — identifies affected files, dependencies, and risks.

    Args:
        description: Ticket text, feature request, bug report, or description
            of the work. More detail produces better results.
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

    freshness = _get_freshness_line()
    if freshness:
        output = f"{freshness}\n\n{output}"

    return output


@mcp.tool()
def refresh_index(pull: bool = True) -> str:
    """Refresh the code index by pulling latest changes and re-indexing.

    Args:
        pull: Whether to git fetch from remote before indexing (default True).
    """
    config = _resources.config
    if not config:
        return "Error: No repo configured. Run `repo-brain init <path>` first."

    from repo_brain.tools.refresh import refresh_index as _refresh

    result = _refresh(config, pull=pull)
    return json.dumps(result)


def main() -> None:
    """Entry point for the MCP server."""
    # Eagerly warm all expensive resources before accepting tool calls
    _resources.warmup()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
