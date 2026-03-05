"""ChromaDB vector store wrapper."""

from __future__ import annotations

import logging
from typing import Any

import chromadb
from chromadb.config import Settings
from chromadb.errors import NotFoundError

from repo_brain.config import RepoConfig

logger = logging.getLogger(__name__)


class VectorStore:
    """Manages ChromaDB collections for a single repo."""

    COLLECTION_NAME = "code_chunks"

    def __init__(self, config: RepoConfig) -> None:
        self.config = config
        config.chroma_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Opening vector store...")
        self._client = chromadb.PersistentClient(
            path=str(config.chroma_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        try:
            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception:
            logger.warning("ChromaDB state appears corrupted; resetting collection.")
            self._force_reset_collection()

    @property
    def count(self) -> int:
        """Number of chunks in the collection."""
        return self._collection.count()

    def add_chunks(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Add chunks to the vector store in batches."""
        batch_size = 500
        for i in range(0, len(ids), batch_size):
            end = min(i + batch_size, len(ids))
            try:
                self._collection.upsert(
                    ids=ids[i:end],
                    documents=documents[i:end],
                    embeddings=embeddings[i:end],
                    metadatas=metadatas[i:end],
                )
            except NotFoundError:
                logger.warning("Collection disappeared; recreating and retrying batch.")
                self._force_reset_collection()
                self._collection.upsert(
                    ids=ids[i:end],
                    documents=documents[i:end],
                    embeddings=embeddings[i:end],
                    metadatas=metadatas[i:end],
                )
        logger.info("Stored %d chunks in vector store", len(ids))

    def search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar chunks by pre-computed embedding.

        Returns list of dicts with keys: id, document, metadata, distance.
        """
        kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": limit,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        results = self._collection.query(**kwargs)
        return self._parse_results(results)

    def search_by_text(
        self,
        query: str,
        limit: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar chunks using ChromaDB's built-in embedding.

        Uses ChromaDB's default embedding function (all-MiniLM-L6-v2 via
        onnxruntime) — avoids importing torch/sentence-transformers entirely,
        cutting query latency from ~10s to ~1s.
        """
        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": limit,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        results = self._collection.query(**kwargs)
        return self._parse_results(results)

    def _parse_results(self, results: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse raw ChromaDB query results into a flat list."""

        items: list[dict[str, Any]] = []
        if not results["ids"] or not results["ids"][0]:
            return items

        for i, chunk_id in enumerate(results["ids"][0]):
            item: dict[str, Any] = {"id": chunk_id}
            if results["documents"] and results["documents"][0]:
                item["document"] = results["documents"][0][i]
            if results["metadatas"] and results["metadatas"][0]:
                item["metadata"] = results["metadatas"][0][i]
            if results["distances"] and results["distances"][0]:
                # ChromaDB returns distance; convert to similarity score
                item["distance"] = results["distances"][0][i]
                item["score"] = 1.0 - results["distances"][0][i]
            items.append(item)

        return items

    def delete_by_file(self, file_path: str) -> None:
        """Delete all chunks for a given file path."""
        self._collection.delete(where={"file_path": file_path})

    def _force_reset_collection(self) -> None:
        """Delete and recreate the collection, tolerating missing state."""
        try:
            self._client.delete_collection(self.COLLECTION_NAME)
        except Exception:
            pass  # Collection may already be gone
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def delete_all(self) -> None:
        """Delete all chunks. Used for full re-index."""
        self._force_reset_collection()

    def get_indexed_files(self) -> set[str]:
        """Get set of all file paths currently indexed."""
        results = self._collection.get(include=["metadatas"])
        files: set[str] = set()
        if results["metadatas"]:
            for meta in results["metadatas"]:
                if meta and "file_path" in meta:
                    files.add(meta["file_path"])
        return files
