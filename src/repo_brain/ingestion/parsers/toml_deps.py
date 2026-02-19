"""pyproject.toml dependency parser — extracts internal library dependencies."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _load_toml(path: Path) -> dict[str, Any]:
    """Load a TOML file."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    try:
        return tomllib.loads(path.read_text())
    except Exception as e:
        logger.warning("Failed to parse %s: %s", path, e)
        return {}


def _infer_component_name(toml_path: Path, repo_path: Path) -> str:
    """Infer a component name from the pyproject.toml path.

    e.g., services/rest-api/app/pyproject.toml -> rest-api
          libraries/python/faa-models/pyproject.toml -> faa-models
          mcp_servers/radkit/app/pyproject.toml -> radkit
    """
    try:
        rel = toml_path.parent.relative_to(repo_path)
    except ValueError:
        return toml_path.parent.name

    parts = rel.parts
    for i, part in enumerate(parts):
        if part in ("services", "libraries", "mcp_servers", "agents") and i + 1 < len(parts):
            # For libraries/python/X, return X
            if part == "libraries" and i + 2 < len(parts) and parts[i + 1] == "python":
                return parts[i + 2]
            return parts[i + 1]
    return parts[0] if parts else toml_path.parent.name


def _infer_component_type(toml_path: Path, repo_path: Path) -> str:
    """Infer component type from path."""
    try:
        rel = str(toml_path.relative_to(repo_path))
    except ValueError:
        return "unknown"

    if rel.startswith("services/"):
        return "service"
    if rel.startswith("libraries/"):
        return "library"
    if rel.startswith("mcp_servers/"):
        return "mcp_server"
    if rel.startswith("agents/"):
        return "agent"
    return "unknown"


def parse_toml_dependencies(repo_path: Path) -> dict[str, Any]:
    """Parse all pyproject.toml files and extract internal dependency edges.

    Returns:
        Dict with:
        - components: {name: {type, path, package_name, dependencies}}
        - edges: [(source, target, "library_dependency")]
    """
    components: dict[str, dict[str, Any]] = {}
    edges: list[tuple[str, str, str]] = []

    # Find all pyproject.toml files
    toml_files = list(repo_path.rglob("pyproject.toml"))

    # Filter out vendored/venv paths
    skip_patterns = {".venv", "venv", "node_modules", ".git", "__pycache__", "dist", "build"}
    toml_files = [f for f in toml_files if not any(skip in f.parts for skip in skip_patterns)]

    # First pass: collect all known internal package names
    internal_packages: dict[str, str] = {}  # package_name -> component_name

    for toml_path in toml_files:
        data = _load_toml(toml_path)
        project = data.get("project", {})
        pkg_name = project.get("name", "")
        if not pkg_name:
            continue

        component_name = _infer_component_name(toml_path, repo_path)
        internal_packages[pkg_name] = component_name
        # Also map the underscore variant (faa-models -> faa_models)
        internal_packages[pkg_name.replace("-", "_")] = component_name

    # Second pass: find internal dependency edges
    for toml_path in toml_files:
        data = _load_toml(toml_path)
        project = data.get("project", {})
        pkg_name = project.get("name", "")
        if not pkg_name:
            continue

        component_name = _infer_component_name(toml_path, repo_path)
        component_type = _infer_component_type(toml_path, repo_path)

        try:
            rel_path = str(toml_path.parent.relative_to(repo_path))
        except ValueError:
            rel_path = str(toml_path.parent)

        components[component_name] = {
            "type": component_type,
            "path": rel_path,
            "package_name": pkg_name,
            "description": project.get("description", ""),
            "internal_deps": [],
        }

        # Check [tool.uv.sources] for internal path dependencies
        uv_sources = data.get("tool", {}).get("uv", {}).get("sources", {})
        for dep_name, source_config in uv_sources.items():
            if isinstance(source_config, dict) and "path" in source_config:
                # This is an internal dependency
                target = internal_packages.get(dep_name) or internal_packages.get(
                    dep_name.replace("-", "_")
                )
                if target and target != component_name:
                    edges.append((component_name, target, "library_dependency"))
                    components[component_name]["internal_deps"].append(target)

        # Also check [project].dependencies for known internal packages
        # (some deps are implicit / base-image installed without uv.sources)
        deps = project.get("dependencies", [])
        for dep in deps:
            if not isinstance(dep, str):
                continue
            # Extract package name (strip version specifiers)
            dep_clean = dep.split(">=")[0].split("<=")[0].split("==")[0].split("~=")[0]
            dep_clean = dep_clean.split("[")[0].split("@")[0].strip()

            target = internal_packages.get(dep_clean) or internal_packages.get(
                dep_clean.replace("-", "_")
            )
            if target and target != component_name:
                # Avoid duplicate edges
                edge = (component_name, target, "library_dependency")
                if edge not in edges:
                    edges.append(edge)
                    if target not in components[component_name]["internal_deps"]:
                        components[component_name]["internal_deps"].append(target)

    logger.info(
        "Parsed %d pyproject.toml files: %d components, %d internal dependency edges",
        len(toml_files),
        len(components),
        len(edges),
    )
    return {"components": components, "edges": edges}
