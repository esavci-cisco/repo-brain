"""Scope task tool — the primary entry point for daily developer workflow.

Takes a natural language description of work to do (ticket text, feature
request, bug description) and returns a focused context package: affected
services, dependencies, key files, and risk assessment.

This is NOT a planning tool — it doesn't tell you *how* to implement.
It tells you *what's in the blast radius* so the developer (or OpenCode's
plan mode) can skip the discovery phase and go straight to reading the
right files.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING, Any

from repo_brain.config import RepoConfig

if TYPE_CHECKING:
    from repo_brain.storage.graph_store import GraphStore
    from repo_brain.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)


def scope_task(
    description: str,
    config: RepoConfig,
    search_limit: int = 20,
    dep_depth: int = 2,
    vector_store: VectorStore | None = None,
    graph_store: GraphStore | None = None,
) -> dict[str, Any]:
    """Scope a task by finding affected services, files, and dependencies.

    Args:
        description: Natural language description of the work to do.
        config: Repo configuration.
        search_limit: How many search results to consider (default 20).
        dep_depth: How deep to traverse dependency graph (default 2).
        vector_store: Optional pre-built VectorStore (avoids re-init).
        graph_store: Optional pre-built GraphStore (avoids re-init).

    Returns:
        Structured scope analysis with affected services, files, deps, risks.
    """
    result: dict[str, Any] = {
        "description_summary": description[:200],
        "affected_services": [],
        "key_files": [],
        "dependencies": {},
        "risk_assessment": [],
        "suggested_reading_order": [],
    }

    # Step 1: Semantic search to find relevant code
    search_results = _semantic_search(
        description, config, limit=search_limit, vector_store=vector_store
    )

    if not search_results:
        result["note"] = (
            "No relevant code found via semantic search. "
            "The codebase index may be empty or the description may not match "
            "any indexed code. Try running `repo-brain index` first."
        )
        return result

    # Step 2: Extract affected services from search results
    service_hits = _extract_services(search_results)

    # Step 3: For each affected service, pull graph data
    graph_data = _get_graph_context(service_hits, config, depth=dep_depth, graph_store=graph_store)

    # Step 4: Build the key files list (deduplicated, ranked)
    key_files = _build_key_files(search_results)

    # Step 5: Build dependency map and risk assessment
    dep_map, risks = _assess_dependencies(service_hits, graph_data, config, graph_store=graph_store)

    # Step 6: Build suggested reading order
    reading_order = _suggest_reading_order(service_hits, key_files, graph_data)

    result["affected_services"] = service_hits
    result["key_files"] = key_files
    result["dependencies"] = dep_map
    result["risk_assessment"] = risks
    result["suggested_reading_order"] = reading_order

    return result


def format_scope_result(result: dict[str, Any]) -> str:
    """Format scope result as human-readable markdown-ish text.

    This is what the ``/scope`` custom command returns to OpenCode.
    """
    lines: list[str] = []

    lines.append("## Task Scope Analysis")
    lines.append("")

    # Affected services
    services = result.get("affected_services", [])
    if services:
        lines.append("### Affected Services")
        for svc in services:
            name = svc["service"]
            hits = svc["hit_count"]
            role = svc.get("role", "")
            role_str = f" — {role}" if role else ""
            deps_parts: list[str] = []
            if svc.get("upstream_deps"):
                deps_parts.append(f"deps: {', '.join(svc['upstream_deps'][:4])}")
            if svc.get("downstream_deps"):
                deps_parts.append(f"used by: {', '.join(svc['downstream_deps'][:4])}")
            deps_str = f" ({'; '.join(deps_parts)})" if deps_parts else ""
            lines.append(f"- **{name}** ({hits} matches){role_str}{deps_str}")
        lines.append("")

    # Key files — compact: just file:line and symbol
    key_files = result.get("key_files", [])
    if key_files:
        lines.append("### Key Files")
        for f in key_files[:12]:
            symbol = ""
            if f.get("symbol_name"):
                symbol = f" — {f['symbol_name']}"
            lines.append(f"- `{f['file_path']}`{symbol}")
        lines.append("")

    # Risk assessment
    risks = result.get("risk_assessment", [])
    if risks:
        lines.append("### Risks")
        for risk in risks:
            lines.append(f"- {risk}")
        lines.append("")

    # Note
    if result.get("note"):
        lines.append(f"**Note**: {result['note']}")
        lines.append("")

    # Post-call guidance — suggests follow-up actions so the LLM
    # continues using pre-indexed data rather than falling back to grep/glob.
    lines.append("---")
    lines.append("**Next steps**:")
    lines.append("- `/q <query>` — find implementations of specific concepts mentioned above")
    lines.append("- Read only the files listed under 'Key Files to Read'")
    lines.append("- Do NOT do broad grep/glob searches — the scoping already did discovery")

    return "\n".join(lines)


# ── Internal helpers ─────────────────────────────────────────────────


def _semantic_search(
    description: str,
    config: RepoConfig,
    limit: int = 20,
    vector_store: VectorStore | None = None,
) -> list[dict[str, Any]]:
    """Run semantic search on the description text."""
    from repo_brain.tools.search import search_code

    return search_code(query=description, config=config, limit=limit, vector_store=vector_store)


def _extract_services(
    search_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract and rank affected services from search results.

    Groups results by service, counts hits, returns ranked list.
    """
    service_counter: Counter[str] = Counter()
    service_files: dict[str, list[str]] = {}

    for r in search_results:
        svc = r.get("service", "")
        if not svc:
            # Try to infer service from file path
            svc = _infer_service_from_path(r.get("file_path", ""))
        if svc:
            service_counter[svc] += 1
            if svc not in service_files:
                service_files[svc] = []
            fp = r.get("file_path", "")
            if fp and fp not in service_files[svc]:
                service_files[svc].append(fp)

    services: list[dict[str, Any]] = []
    for svc_name, count in service_counter.most_common():
        services.append(
            {
                "service": svc_name,
                "hit_count": count,
                "files": service_files.get(svc_name, [])[:10],
            }
        )

    return services


def _infer_service_from_path(file_path: str) -> str:
    """Try to extract a service name from a file path.

    Handles common patterns like:
    - services/<name>/...
    - libs/<name>/...
    - mcp-servers/<name>/...
    """
    parts = file_path.replace("\\", "/").split("/")
    for i, part in enumerate(parts):
        if part in ("services", "libs", "mcp-servers", "packages", "apps") and i + 1 < len(parts):
            return parts[i + 1]
    return ""


def _get_graph_context(
    service_hits: list[dict[str, Any]],
    config: RepoConfig,
    depth: int = 2,
    graph_store: GraphStore | None = None,
) -> dict[str, dict[str, Any]]:
    """Pull dependency graph context for each affected service."""
    try:
        if graph_store is None:
            from repo_brain.storage.graph_store import GraphStore

            graph_store = GraphStore(config)
    except Exception:
        return {}

    graph_data: dict[str, dict[str, Any]] = {}

    for svc in service_hits:
        name = svc["service"]
        node_info = graph_store.get_node_info(name)
        if not node_info:
            continue

        upstream = graph_store.get_upstream(name, depth=depth)
        downstream = graph_store.get_downstream(name, depth=depth)

        graph_data[name] = {
            "node_info": node_info,
            "upstream": upstream,
            "downstream": downstream,
        }

        # Enrich the service hit with graph data
        svc["upstream_deps"] = [u["name"] for u in upstream]
        svc["downstream_deps"] = [d["name"] for d in downstream]
        svc["role"] = node_info.get("description", "")

    return graph_data


def _build_key_files(
    search_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build a deduplicated, ranked list of key files from search results."""
    seen_paths: set[str] = set()
    key_files: list[dict[str, Any]] = []

    for r in search_results:
        fp = r.get("file_path", "")
        if not fp or fp in seen_paths:
            continue
        seen_paths.add(fp)

        key_files.append(
            {
                "file_path": fp,
                "symbol_name": r.get("symbol_name", ""),
                "symbol_type": r.get("symbol_type", ""),
                "service": r.get("service", "") or _infer_service_from_path(fp),
                "language": r.get("language", ""),
                "relevance_score": r.get("score", 0),
            }
        )

    return key_files


def _assess_dependencies(
    service_hits: list[dict[str, Any]],
    graph_data: dict[str, dict[str, Any]],
    config: RepoConfig,
    graph_store: GraphStore | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Build dependency map and risk assessment."""
    dep_map: dict[str, Any] = {}
    risks: list[str] = []

    # Collect all unique upstream/downstream across affected services
    all_upstream: Counter[str] = Counter()
    all_downstream: Counter[str] = Counter()

    for svc in service_hits:
        name = svc["service"]
        if name in graph_data:
            gd = graph_data[name]
            for u in gd.get("upstream", []):
                all_upstream[u["name"]] += 1
            for d in gd.get("downstream", []):
                all_downstream[d["name"]] += 1

    if all_upstream:
        dep_map["upstream"] = {
            "direction": "services this task depends on",
            "items": [name for name, _ in all_upstream.most_common()],
        }

    if all_downstream:
        dep_map["downstream"] = {
            "direction": "services that could be affected",
            "items": [name for name, _ in all_downstream.most_common()],
        }

    # Risk assessment
    for svc in service_hits:
        name = svc["service"]
        downstream_count = len(svc.get("downstream_deps", []))
        if downstream_count > 10:
            risks.append(
                f"HIGH RISK: {name} has {downstream_count} dependents. "
                f"Changes here have wide blast radius."
            )
        elif downstream_count > 3:
            risks.append(f"MODERATE RISK: {name} has {downstream_count} dependents.")

    # Check if shared libraries are in the affected set
    try:
        if graph_store is None:
            from repo_brain.storage.graph_store import GraphStore

            graph_store = GraphStore(config)
        for svc in service_hits:
            name = svc["service"]
            node_info = graph_store.get_node_info(name)
            if node_info and node_info.get("node_type") == "library":
                downstream = graph_store.get_downstream(name, depth=1)
                if len(downstream) > 5:
                    risks.append(
                        f"SHARED LIBRARY: {name} is used by {len(downstream)} modules. "
                        f"Schema/API changes need careful coordination."
                    )
    except Exception:
        pass

    if not risks:
        risks.append("LOW RISK: Changes appear localized to specific services.")

    return dep_map, risks


def _suggest_reading_order(
    service_hits: list[dict[str, Any]],
    key_files: list[dict[str, Any]],
    graph_data: dict[str, dict[str, Any]],
) -> list[str]:
    """Suggest an order for reading files based on dependency structure.

    Principle: read shared/upstream code first, then service-specific code.
    """
    reading_order: list[str] = []

    # Categorize services by type
    libraries: list[str] = []
    services: list[str] = []

    for svc in service_hits:
        name = svc["service"]
        if name in graph_data:
            node_type = graph_data[name].get("node_info", {}).get("node_type", "")
            if node_type == "library":
                libraries.append(name)
            else:
                services.append(name)
        else:
            services.append(name)

    # Libraries first (shared code)
    for lib in libraries:
        files = [f["file_path"] for f in key_files if f.get("service") == lib][:3]
        if files:
            file_list = ", ".join(f"`{f}`" for f in files)
            reading_order.append(f"Shared library **{lib}**: {file_list}")

    # Then services, ordered by most relevant first
    for svc_name in services:
        files = [f["file_path"] for f in key_files if f.get("service") == svc_name][:3]
        if files:
            file_list = ", ".join(f"`{f}`" for f in files)
            reading_order.append(f"Service **{svc_name}**: {file_list}")

    # Any files not attributed to a service
    unattributed = [f for f in key_files if not f.get("service")][:3]
    if unattributed:
        file_list = ", ".join(f"`{f['file_path']}`" for f in unattributed)
        reading_order.append(f"Other relevant files: {file_list}")

    return reading_order
