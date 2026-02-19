"""NetworkX-based dependency graph with JSON persistence."""

from __future__ import annotations

import json
import logging
from typing import Any

import networkx as nx

from repo_brain.config import RepoConfig

logger = logging.getLogger(__name__)


class GraphStore:
    """Manages the dependency graph for a repository."""

    def __init__(self, config: RepoConfig) -> None:
        self.config = config
        self._graph = nx.DiGraph()
        self._load()

    def _load(self) -> None:
        """Load graph from JSON file if it exists."""
        if self.config.graph_path.exists():
            try:
                data = json.loads(self.config.graph_path.read_text())
                self._graph = nx.node_link_graph(data)
                logger.info("Loaded graph with %d nodes", self._graph.number_of_nodes())
            except Exception as e:
                logger.warning("Failed to load graph: %s", e)
                self._graph = nx.DiGraph()

    def save(self) -> None:
        """Persist graph to JSON."""
        self.config.data_dir.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self._graph)
        self.config.graph_path.write_text(json.dumps(data, indent=2))
        logger.info("Saved graph with %d nodes", self._graph.number_of_nodes())

    def add_node(self, name: str, **attrs: Any) -> None:
        """Add or update a node."""
        self._graph.add_node(name, **attrs)

    def add_edge(self, source: str, target: str, **attrs: Any) -> None:
        """Add a directed edge (source depends on target)."""
        self._graph.add_edge(source, target, **attrs)

    def get_upstream(self, node: str, depth: int = 3) -> list[dict[str, Any]]:
        """Get nodes that the given node depends on (predecessors in reverse)."""
        if node not in self._graph:
            return []
        try:
            # BFS up to depth
            visited: set[str] = set()
            results: list[dict[str, Any]] = []
            queue: list[tuple[str, int]] = [(node, 0)]

            while queue:
                current, d = queue.pop(0)
                if d > depth:
                    continue
                for successor in self._graph.successors(current):
                    if successor not in visited:
                        visited.add(successor)
                        node_data = dict(self._graph.nodes[successor])
                        results.append({"name": successor, "depth": d + 1, **node_data})
                        queue.append((successor, d + 1))

            return results
        except nx.NetworkXError:
            return []

    def get_downstream(self, node: str, depth: int = 3) -> list[dict[str, Any]]:
        """Get nodes that depend on the given node (what would be affected)."""
        if node not in self._graph:
            return []
        try:
            visited: set[str] = set()
            results: list[dict[str, Any]] = []
            queue: list[tuple[str, int]] = [(node, 0)]

            while queue:
                current, d = queue.pop(0)
                if d > depth:
                    continue
                for predecessor in self._graph.predecessors(current):
                    if predecessor not in visited:
                        visited.add(predecessor)
                        node_data = dict(self._graph.nodes[predecessor])
                        results.append({"name": predecessor, "depth": d + 1, **node_data})
                        queue.append((predecessor, d + 1))

            return results
        except nx.NetworkXError:
            return []

    def get_node_info(self, node: str) -> dict[str, Any] | None:
        """Get info about a single node."""
        if node not in self._graph:
            return None
        data = dict(self._graph.nodes[node])
        data["name"] = node
        data["upstream_count"] = len(list(self._graph.successors(node)))
        data["downstream_count"] = len(list(self._graph.predecessors(node)))
        return data

    def get_all_nodes(self) -> list[dict[str, Any]]:
        """Get all nodes with their attributes."""
        nodes: list[dict[str, Any]] = []
        for name, attrs in self._graph.nodes(data=True):
            nodes.append({"name": name, **attrs})
        return nodes

    @property
    def node_count(self) -> int:
        return self._graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self._graph.number_of_edges()

    def clear(self) -> None:
        """Clear the entire graph."""
        self._graph.clear()
