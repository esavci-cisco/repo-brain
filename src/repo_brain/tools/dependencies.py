"""Dependency query tool."""

from __future__ import annotations

import logging
from typing import Any

from repo_brain.config import RepoConfig
from repo_brain.storage.graph_store import GraphStore

logger = logging.getLogger(__name__)


def query_dependencies(
    module: str,
    config: RepoConfig,
    direction: str = "both",
    depth: int = 3,
) -> dict[str, Any]:
    """Query dependency graph for a module/service.

    Args:
        module: Name of the module or service to query.
        config: Repo configuration.
        direction: "up" (what it depends on), "down" (what depends on it), or "both".
        depth: How many levels deep to traverse.

    Returns:
        Dict with upstream, downstream dependencies and risk info.
    """
    graph = GraphStore(config)
    result: dict[str, Any] = {
        "module": module,
        "found": False,
        "upstream": [],
        "downstream": [],
        "risk_summary": "",
    }

    node_info = graph.get_node_info(module)
    if not node_info:
        # Try partial match
        all_nodes = graph.get_all_nodes()
        matches = [n for n in all_nodes if module.lower() in n["name"].lower()]
        if matches:
            result["suggestions"] = [m["name"] for m in matches[:5]]
            result["risk_summary"] = (
                f"Module '{module}' not found. Did you mean: {', '.join(result['suggestions'])}"
            )
        else:
            result["risk_summary"] = f"Module '{module}' not found in dependency graph."
        return result

    result["found"] = True
    result["node_info"] = node_info

    if direction in ("up", "both"):
        result["upstream"] = graph.get_upstream(module, depth=depth)

    if direction in ("down", "both"):
        result["downstream"] = graph.get_downstream(module, depth=depth)

    # Risk assessment
    downstream_count = len(result["downstream"])
    if downstream_count > 10:
        result["risk_summary"] = (
            f"HIGH RISK: {downstream_count} modules depend on '{module}'. "
            "Changes here have wide blast radius."
        )
    elif downstream_count > 3:
        result["risk_summary"] = f"MODERATE RISK: {downstream_count} modules depend on '{module}'."
    else:
        result["risk_summary"] = f"LOW RISK: {downstream_count} modules depend on '{module}'."

    return result
