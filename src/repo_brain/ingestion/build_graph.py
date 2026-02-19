"""Build the unified dependency graph from all parsers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from repo_brain.config import RepoConfig
from repo_brain.storage.graph_store import GraphStore

logger = logging.getLogger(__name__)


def build_graph(config: RepoConfig) -> dict[str, Any]:
    """Run all parsers and build a unified dependency graph.

    Returns summary stats.
    """
    from repo_brain.ingestion.parsers.compose import parse_compose
    from repo_brain.ingestion.parsers.proto import parse_proto_files
    from repo_brain.ingestion.parsers.toml_deps import parse_toml_dependencies

    repo_path = Path(config.path)
    graph = GraphStore(config)
    graph.clear()

    stats: dict[str, Any] = {
        "compose_services": 0,
        "compose_edges": 0,
        "toml_components": 0,
        "toml_edges": 0,
        "proto_services": 0,
        "proto_edges": 0,
        "total_nodes": 0,
        "total_edges": 0,
    }

    # 1. Parse Docker Compose → service topology
    compose_data = parse_compose(repo_path)
    for svc_name, svc_info in compose_data["services"].items():
        graph.add_node(
            svc_name,
            node_type=svc_info["type"],
            parsed_from="compose",
            data_store_type=svc_info.get("data_store_type", ""),
        )
    for src, tgt, edge_type in compose_data["edges"]:
        graph.add_edge(src, tgt, edge_type=edge_type, parsed_from="compose")
    stats["compose_services"] = len(compose_data["services"])
    stats["compose_edges"] = len(compose_data["edges"])

    # 2. Parse pyproject.toml → library dependencies
    toml_data = parse_toml_dependencies(repo_path)
    for comp_name, comp_info in toml_data["components"].items():
        # Merge with existing node if it came from compose
        existing = graph.get_node_info(comp_name)
        attrs: dict[str, Any] = {
            "component_type": comp_info["type"],
            "path": comp_info["path"],
            "package_name": comp_info["package_name"],
            "description": comp_info.get("description", ""),
        }
        if existing:
            # Preserve compose data, add toml data
            attrs["node_type"] = existing.get("node_type", comp_info["type"])
        else:
            attrs["node_type"] = comp_info["type"]
        attrs["parsed_from"] = "compose+toml" if existing else "toml"
        graph.add_node(comp_name, **attrs)

    for src, tgt, edge_type in toml_data["edges"]:
        graph.add_edge(src, tgt, edge_type=edge_type, parsed_from="toml")
    stats["toml_components"] = len(toml_data["components"])
    stats["toml_edges"] = len(toml_data["edges"])

    # 3. Parse proto files → gRPC service contracts
    proto_data = parse_proto_files(repo_path)
    for proto_svc_name, proto_info in proto_data["services"].items():
        owner = proto_info["owning_service"]
        # Add gRPC info to the owning service node
        existing = graph.get_node_info(owner)
        if existing:
            grpc_services = existing.get("grpc_services", [])
            if proto_svc_name not in grpc_services:
                grpc_services.append(proto_svc_name)
            graph.add_node(
                owner,
                grpc_services=grpc_services,
                grpc_rpcs=proto_info["rpcs"],
            )
    for src, tgt, edge_type in proto_data["edges"]:
        graph.add_edge(src, tgt, edge_type=edge_type, parsed_from="proto")
    stats["proto_services"] = len(proto_data["services"])
    stats["proto_edges"] = len(proto_data["edges"])

    # Save the graph
    graph.save()

    stats["total_nodes"] = graph.node_count
    stats["total_edges"] = graph.edge_count

    logger.info(
        "Graph built: %d nodes, %d edges",
        graph.node_count,
        graph.edge_count,
    )
    return stats
