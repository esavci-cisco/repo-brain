"""Semantic code search tool."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from repo_brain.config import RepoConfig
from repo_brain.ingestion.embedder import generate_embeddings

if TYPE_CHECKING:
    from repo_brain.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)


def search_code(
    query: str,
    config: RepoConfig,
    limit: int = 10,
    service_filter: str | None = None,
    language_filter: str | None = None,
    vector_store: VectorStore | None = None,
) -> list[dict[str, Any]]:
    """Semantic search over indexed code.

    Args:
        query: Natural language search query.
        config: Repo configuration.
        limit: Max results to return.
        service_filter: Optional filter by service name.
        language_filter: Optional filter by language.
        vector_store: Optional pre-built VectorStore (avoids re-init).

    Returns:
        List of search results with file_path, snippet, score, metadata.
    """
    # Generate embedding for the query
    embeddings = generate_embeddings([query], model_name=config.embedding_model)
    if not embeddings:
        return []

    query_embedding = embeddings[0]

    # Build optional filter
    where: dict[str, Any] | None = None
    if service_filter or language_filter:
        conditions: list[dict[str, Any]] = []
        if service_filter:
            conditions.append({"service": service_filter})
        if language_filter:
            conditions.append({"language": language_filter})
        if len(conditions) == 1:
            where = conditions[0]
        else:
            where = {"$and": conditions}

    # Query vector store (use cached instance if provided)
    if vector_store is None:
        from repo_brain.storage.vector_store import VectorStore

        vector_store = VectorStore(config)
    raw_results = vector_store.search(query_embedding, limit=limit, where=where)

    # Format results
    results: list[dict[str, Any]] = []
    for item in raw_results:
        meta = item.get("metadata", {})
        result = {
            "file_path": meta.get("file_path", ""),
            "symbol_name": meta.get("symbol_name", ""),
            "symbol_type": meta.get("symbol_type", ""),
            "service": meta.get("service", ""),
            "language": meta.get("language", ""),
            "line_start": meta.get("line_start", 0),
            "line_end": meta.get("line_end", 0),
            "score": round(item.get("score", 0.0), 4),
            "snippet": _extract_snippet(item.get("document", ""), max_lines=20),
        }
        results.append(result)

    return results


def _extract_snippet(document: str, max_lines: int = 20) -> str:
    """Extract a code snippet from a document, stripping the metadata header."""
    lines = document.splitlines()

    # Find the blank line that separates metadata from code
    code_start = 0
    for i, line in enumerate(lines):
        if line.strip() == "" and i > 0:
            code_start = i + 1
            break

    code_lines = lines[code_start:]
    if len(code_lines) > max_lines:
        code_lines = code_lines[:max_lines]
        code_lines.append("... (truncated)")

    return "\n".join(code_lines)
