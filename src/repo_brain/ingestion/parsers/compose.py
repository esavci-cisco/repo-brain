"""Docker Compose parser — extracts service topology from compose.yml."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Known data store images/names
DATA_STORE_PATTERNS: dict[str, str] = {
    "postgres": "PostgreSQL",
    "timescaledb": "TimescaleDB",
    "neo4j": "Neo4j",
    "chromadb": "ChromaDB",
    "chroma": "ChromaDB",
    "redis": "Redis",
    "kafka": "Kafka",
    "minio": "MinIO",
    "langfuse": "Langfuse",
}

# Init services that run once and exit
INIT_PATTERNS = {"init", "migrations", "setup"}


def _is_data_store(name: str, config: dict[str, Any]) -> bool:
    """Check if a compose service is a data store."""
    image = config.get("image", "")
    for pattern in DATA_STORE_PATTERNS:
        if pattern in name.lower() or pattern in image.lower():
            return True
    return False


def _is_init_service(name: str, config: dict[str, Any]) -> bool:
    """Check if a compose service is an init/migration service."""
    for pattern in INIT_PATTERNS:
        if pattern in name.lower():
            return True
    # Services with restart: "no" or no restart are often init services
    if config.get("restart") == "no":
        return True
    return False


def _classify_service(name: str, config: dict[str, Any]) -> str:
    """Classify a compose service type."""
    if _is_data_store(name, config):
        return "data_store"
    if _is_init_service(name, config):
        return "init"
    return "service"


def parse_compose(repo_path: Path) -> dict[str, Any]:
    """Parse Docker Compose file and extract service topology.

    Returns:
        Dict with:
        - services: {name: {type, image, depends_on, ports, ...}}
        - edges: [(source, target, edge_type)]
    """
    compose_file = repo_path / "compose.yml"
    if not compose_file.exists():
        compose_file = repo_path / "docker-compose.yml"
    if not compose_file.exists():
        compose_file = repo_path / "docker-compose.yaml"
    if not compose_file.exists():
        logger.info("No compose file found")
        return {"services": {}, "edges": []}

    try:
        data = yaml.safe_load(compose_file.read_text())
    except Exception as e:
        logger.warning("Failed to parse compose file: %s", e)
        return {"services": {}, "edges": []}

    if not data or "services" not in data:
        return {"services": {}, "edges": []}

    services: dict[str, dict[str, Any]] = {}
    edges: list[tuple[str, str, str]] = []

    for svc_name, svc_config in data.get("services", {}).items():
        if not isinstance(svc_config, dict):
            continue

        svc_type = _classify_service(svc_name, svc_config)

        # Determine data store type if applicable
        data_store_type = ""
        if svc_type == "data_store":
            image = svc_config.get("image", "")
            for pattern, store_type in DATA_STORE_PATTERNS.items():
                if pattern in svc_name.lower() or pattern in image.lower():
                    data_store_type = store_type
                    break

        services[svc_name] = {
            "type": svc_type,
            "image": svc_config.get("image", ""),
            "data_store_type": data_store_type,
            "build": bool(svc_config.get("build")),
            "ports": svc_config.get("ports", []),
            "profiles": svc_config.get("profiles", []),
        }

        # Extract depends_on edges
        depends_on = svc_config.get("depends_on", [])
        if isinstance(depends_on, dict):
            deps = list(depends_on.keys())
        elif isinstance(depends_on, list):
            deps = depends_on
        else:
            deps = []

        for dep in deps:
            dep_name = dep if isinstance(dep, str) else str(dep)
            # Classify the edge type
            if _is_data_store(dep_name, data.get("services", {}).get(dep_name, {})):
                edge_type = "uses_datastore"
            else:
                edge_type = "depends_on"
            edges.append((svc_name, dep_name, edge_type))

    logger.info(
        "Parsed compose: %d services, %d edges",
        len(services),
        len(edges),
    )
    return {"services": services, "edges": edges}
