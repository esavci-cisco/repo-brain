"""MCP server for repo-brain.

This is the entry point that OpenCode spawns as a subprocess.
Run with: python -m repo_brain.mcp_server
"""

from __future__ import annotations

import json
import logging
import os
import sys

from mcp.server.fastmcp import FastMCP

from repo_brain.config import RepoConfig, find_repo_config_by_path, load_repo_config

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

MCP_INSTRUCTIONS = """\
Persistent repo intelligence tools with pre-computed context about the codebase \
architecture, dependencies, and code locations.

Use repo-brain first when you need to understand what's affected, how things \
connect, or where relevant code lives — before launching Explore agents or \
grepping across the codebase:

- scope_task(description): starting any new work, or understanding how a \
feature/system works across services. This is the primary tool.
- get_architecture: repo structure and service overview.
- get_service_info(service_name): focused context for a known service.
- query_dependencies(module): impact analysis before changing shared code.
- search_code(query): finding code by concept, not by name.

Use built-in tools (grep, glob, Read) when:
- You already know which file or service to look at.
- You need exact keyword or symbol matches.
- You are reading/editing specific files during implementation.

One scope_task call at the start of a task replaces minutes of codebase \
exploration. Do not call multiple repo-brain tools preemptively.\
"""

mcp = FastMCP(
    "repo-brain",
    instructions=MCP_INSTRUCTIONS,
)


def _get_config() -> RepoConfig | None:
    """Resolve the repo config from environment or auto-detect."""
    config: RepoConfig | None = None

    # Check explicit REPO_PATH env var
    repo_path = os.environ.get("REPO_PATH", "")
    if repo_path:
        config = find_repo_config_by_path(repo_path)

    # Check REPO_SLUG env var
    if not config:
        repo_slug = os.environ.get("REPO_SLUG", "")
        if repo_slug:
            config = load_repo_config(repo_slug)

    # Try CWD
    if not config:
        cwd = os.getcwd()
        config = find_repo_config_by_path(cwd)

    # Inject GITHUB_TOKEN from environment if not already set in config
    if config:
        env_token = os.environ.get("GITHUB_TOKEN", "")
        if env_token and not config.github_token:
            config.github_token = env_token

    return config


@mcp.tool()
def search_code(query: str, limit: int = 10, service: str = "", language: str = "") -> str:
    """Search the codebase semantically. Use this to find code by describing what it does.

    Args:
        query: Natural language description of what you're looking for.
        limit: Maximum number of results (default 10).
        service: Optional service name filter (e.g., "auth-service").
        language: Optional language filter (e.g., "python", "go").
    """
    config = _get_config()
    if not config:
        return "Error: No repo configured. Run `repo-brain init <path>` first."

    from repo_brain.tools.search import search_code as _search

    results = _search(
        query=query,
        config=config,
        limit=limit,
        service_filter=service or None,
        language_filter=language or None,
    )

    if not results:
        return "No results found."

    output_parts: list[str] = []
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

    return "\n".join(output_parts)


@mcp.tool()
def get_architecture() -> str:
    """Get the full architecture overview of the repository.

    Returns the architecture document with service boundaries,
    data flows, and infrastructure information.
    """
    config = _get_config()
    if not config:
        return "Error: No repo configured. Run `repo-brain init <path>` first."

    from repo_brain.tools.architecture import get_architecture as _get_arch

    return _get_arch(config)


@mcp.tool()
def get_service_info(service_name: str) -> str:
    """Get detailed information about a specific service.

    Args:
        service_name: Name of the service (e.g., "auth-service", "rest-api", "rule-mcp").
    """
    config = _get_config()
    if not config:
        return "Error: No repo configured. Run `repo-brain init <path>` first."

    from repo_brain.tools.architecture import get_service_info as _get_svc

    info = _get_svc(service_name, config)
    return json.dumps(info, indent=2)


@mcp.tool()
def query_dependencies(module: str, direction: str = "both", depth: int = 3) -> str:
    """Query the dependency graph for a module or service.

    Shows what a module depends on (upstream) and what depends on it (downstream).

    Args:
        module: Module or service name to query.
        direction: "up" (dependencies), "down" (dependents), or "both".
        depth: How many levels deep to traverse (default 3).
    """
    config = _get_config()
    if not config:
        return "Error: No repo configured. Run `repo-brain init <path>` first."

    from repo_brain.tools.dependencies import query_dependencies as _query_deps

    result = _query_deps(module=module, config=config, direction=direction, depth=depth)
    return json.dumps(result, indent=2)


@mcp.tool()
def scope_task(description: str) -> str:
    """Scope a task before starting implementation.

    Takes any natural language description of work to do — a Jira ticket,
    feature request, bug report, or just "add caching to rule queries" —
    and returns: affected services, key files to read, dependency context,
    and risk assessment.

    Use this FIRST when starting any new task where you don't already know
    which files are affected. This replaces the need to explore the codebase
    from scratch.

    Args:
        description: What the developer wants to do. Can be a ticket description,
            acceptance criteria, feature request, or any natural language description.
    """
    config = _get_config()
    if not config:
        return "Error: No repo configured. Run `repo-brain init <path>` first."

    from repo_brain.tools.scope import format_scope_result
    from repo_brain.tools.scope import scope_task as _scope

    result = _scope(description=description, config=config)
    return format_scope_result(result)


@mcp.tool()
def refresh_index(pull: bool = True) -> str:
    """Refresh the code index by pulling latest changes and re-indexing modified files.

    Args:
        pull: Whether to git fetch from remote before indexing (default True).
    """
    config = _get_config()
    if not config:
        return "Error: No repo configured. Run `repo-brain init <path>` first."

    from repo_brain.tools.refresh import refresh_index as _refresh

    result = _refresh(config, pull=pull)
    return json.dumps(result, indent=2)


@mcp.tool()
def index_status() -> str:
    """Show the current index status — file counts, staleness, and last run info."""
    config = _get_config()
    if not config:
        return "Error: No repo configured. Run `repo-brain init <path>` first."

    from repo_brain.storage.metadata_db import MetadataDB

    db = MetadataDB(config)
    stats = db.get_stats()
    db.close()

    from repo_brain.storage.vector_store import VectorStore

    store = VectorStore(config)
    stats["vector_store_chunks"] = store.count

    return json.dumps(stats, indent=2, default=str)


def main() -> None:
    """Entry point for the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
