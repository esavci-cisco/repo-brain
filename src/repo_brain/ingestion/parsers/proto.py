"""Proto file parser — extracts gRPC service definitions and cross-service contracts."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Regex patterns for proto parsing
SERVICE_PATTERN = re.compile(r"service\s+(\w+)\s*\{")
RPC_PATTERN = re.compile(r"rpc\s+(\w+)\s*\(")
PACKAGE_PATTERN = re.compile(r"package\s+([\w.]+)\s*;")


def parse_proto_files(repo_path: Path) -> dict[str, Any]:
    """Parse all .proto files and extract gRPC service definitions.

    Returns:
        Dict with:
        - services: {proto_service_name: {package, file, rpcs, owning_service}}
        - edges: [(client_service, server_service, "grpc")]
    """
    proto_files = list(repo_path.rglob("*.proto"))

    # Filter out vendored paths
    skip_patterns = {".venv", "venv", "node_modules", ".git"}
    proto_files = [f for f in proto_files if not any(skip in f.parts for skip in skip_patterns)]

    services: dict[str, dict[str, Any]] = {}
    # Track which service directory owns each proto
    proto_by_service: dict[str, list[str]] = {}  # owning_service -> [proto_service_names]
    proto_by_package: dict[str, str] = {}  # package_name -> owning_service

    for proto_path in proto_files:
        try:
            content = proto_path.read_text()
        except Exception as e:
            logger.warning("Failed to read %s: %s", proto_path, e)
            continue

        # Determine owning service from path
        try:
            rel = proto_path.relative_to(repo_path)
        except ValueError:
            continue

        owning_service = _infer_owning_service(rel)

        # Extract package
        package_match = PACKAGE_PATTERN.search(content)
        package = package_match.group(1) if package_match else ""

        if package:
            proto_by_package[package] = owning_service

        # Extract service definitions
        for svc_match in SERVICE_PATTERN.finditer(content):
            svc_name = svc_match.group(1)

            # Extract RPCs for this service
            # Find the block after this service definition
            start = svc_match.end()
            rpcs: list[str] = []
            brace_count = 1
            pos = start
            while pos < len(content) and brace_count > 0:
                if content[pos] == "{":
                    brace_count += 1
                elif content[pos] == "}":
                    brace_count -= 1
                pos += 1

            service_block = content[start:pos]
            for rpc_match in RPC_PATTERN.finditer(service_block):
                rpcs.append(rpc_match.group(1))

            services[svc_name] = {
                "package": package,
                "file": str(rel),
                "owning_service": owning_service,
                "rpcs": rpcs,
            }

            if owning_service not in proto_by_service:
                proto_by_service[owning_service] = []
            proto_by_service[owning_service].append(svc_name)

    # Detect gRPC client-server edges
    # If a proto file exists in service A but is a copy of service B's proto,
    # that means A is a client of B
    edges: list[tuple[str, str, str]] = []
    seen_protos: dict[str, str] = {}  # proto_service_name -> first owning service

    for svc_name, svc_info in services.items():
        owner = svc_info["owning_service"]
        if svc_name in seen_protos:
            # This proto service is defined in multiple places
            # The second occurrence is likely a client
            server = seen_protos[svc_name]
            if server != owner:
                edges.append((owner, server, "grpc"))
        else:
            seen_protos[svc_name] = owner

    logger.info(
        "Parsed %d proto files: %d gRPC services, %d edges",
        len(proto_files),
        len(services),
        len(edges),
    )
    return {"services": services, "edges": edges}


def _infer_owning_service(rel_path: Path) -> str:
    """Infer which service owns a proto file from its relative path."""
    parts = rel_path.parts
    for i, part in enumerate(parts):
        if part in ("services", "mcp_servers", "agents") and i + 1 < len(parts):
            return parts[i + 1]
    return parts[0] if parts else "unknown"
