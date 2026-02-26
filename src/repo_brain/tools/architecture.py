"""Architecture document serving tool."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from repo_brain.config import RepoConfig

if TYPE_CHECKING:
    from repo_brain.storage.graph_store import GraphStore
    from repo_brain.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)


def get_architecture(config: RepoConfig) -> str:
    """Return the full architecture document content."""
    arch_path = config.docs_dir / "architecture.md"
    if arch_path.exists():
        return arch_path.read_text()
    return "No architecture document found. Run `repo-brain generate-docs` to create one."


def get_service_info(
    service_name: str,
    config: RepoConfig,
    vector_store: VectorStore | None = None,
    graph_store: GraphStore | None = None,
) -> dict[str, Any]:
    """Return architecture info for a specific service.

    Combines data from architecture docs, service_map.json, the dependency graph,
    and semantic search to provide key files and entry points.

    Args:
        service_name: Name of the service.
        config: Repo configuration.
        vector_store: Optional pre-built VectorStore (avoids re-init).
        graph_store: Optional pre-built GraphStore (avoids re-init).
    """
    result: dict[str, Any] = {
        "service": service_name,
        "architecture": "",
        "dependencies": [],
        "dependents": [],
    }

    # Try to extract service section from architecture.md
    arch_path = config.docs_dir / "architecture.md"
    if arch_path.exists():
        arch_content = arch_path.read_text()
        section = _extract_service_section(arch_content, service_name)
        if section:
            result["architecture"] = section

    # Load service map for dependency info
    service_map_path = config.docs_dir / "service_map.json"
    if service_map_path.exists():
        try:
            service_map = json.loads(service_map_path.read_text())
            services = service_map.get("services", {})
            if service_name in services:
                svc = services[service_name]
                result["dependencies"] = svc.get("dependencies", [])
                result["dependents"] = svc.get("dependents", [])
                result["data_stores"] = svc.get("data_stores", [])
                result["type"] = svc.get("type", "")
                result["path"] = svc.get("path", "")
        except (json.JSONDecodeError, KeyError):
            pass

    # Enrich with dependency graph data
    try:
        if graph_store is None:
            from repo_brain.storage.graph_store import GraphStore

            graph_store = GraphStore(config)
        node_info = graph_store.get_node_info(service_name)
        if node_info:
            result["graph_info"] = {
                "node_type": node_info.get("node_type", ""),
                "component_type": node_info.get("component_type", ""),
                "package_name": node_info.get("package_name", ""),
                "description": node_info.get("description", ""),
                "grpc_services": node_info.get("grpc_services", []),
                "upstream_count": node_info.get("upstream_count", 0),
                "downstream_count": node_info.get("downstream_count", 0),
            }
            result["upstream"] = graph_store.get_upstream(service_name, depth=2)
            result["downstream"] = graph_store.get_downstream(service_name, depth=2)
    except Exception:
        pass

    # Enrich with key files from semantic search
    try:
        from repo_brain.tools.search import search_code

        search_results = search_code(
            query=service_name,
            config=config,
            limit=10,
            service_filter=service_name,
            vector_store=vector_store,
        )
        if search_results:
            seen: set[str] = set()
            key_files: list[dict[str, str]] = []
            for r in search_results:
                fp = r.get("file_path", "")
                if fp and fp not in seen:
                    seen.add(fp)
                    entry: dict[str, str] = {"file_path": fp}
                    if r.get("symbol_name"):
                        entry["symbol"] = f"{r['symbol_type']}: {r['symbol_name']}"
                    key_files.append(entry)
            if key_files:
                result["key_files"] = key_files
    except Exception:
        pass

    return result


def get_domain_terms(config: RepoConfig) -> str:
    """Return domain terms document."""
    path = config.docs_dir / "domain_terms.md"
    if path.exists():
        return path.read_text()
    return "No domain terms document found. Run `repo-brain generate-docs` to create one."


def get_gotchas(config: RepoConfig) -> str:
    """Return gotchas document."""
    path = config.docs_dir / "gotchas.md"
    if path.exists():
        return path.read_text()
    return "No gotchas document found. Run `repo-brain generate-docs` to create one."


def _extract_service_section(content: str, service_name: str) -> str:
    """Extract a section about a specific service from architecture.md."""
    lines = content.splitlines()
    in_section = False
    section_lines: list[str] = []
    section_level = 0

    for line in lines:
        if line.startswith("#") and service_name.lower() in line.lower():
            in_section = True
            section_level = len(line) - len(line.lstrip("#"))
            section_lines.append(line)
            continue

        if in_section:
            # Stop at next heading of same or higher level
            if line.startswith("#"):
                current_level = len(line) - len(line.lstrip("#"))
                if current_level <= section_level:
                    break
            section_lines.append(line)

    return "\n".join(section_lines).strip()
