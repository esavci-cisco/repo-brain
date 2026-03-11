"""Refresh/re-index tool."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from repo_brain.config import RepoConfig

logger = logging.getLogger(__name__)


def refresh_index(config: RepoConfig, pull: bool = True) -> dict[str, Any]:
    """Pull latest changes and re-index modified files.

    Args:
        config: Repo configuration.
        pull: Whether to git fetch/pull before indexing.

    Returns:
        Summary of what was refreshed.
    """
    repo_path = Path(config.path)
    result: dict[str, Any] = {
        "pulled": False,
        "changed_files": [],
        "reindexed": 0,
        "errors": [],
    }

    if pull:
        try:
            # Build environment with GitHub token if available
            env = None
            if config.github_token:
                import os

                env = os.environ.copy()
                # Git uses GIT_ASKPASS or credential helpers.
                # Setting the token via the header is the most reliable approach
                # for HTTPS remotes on private repos.
                env["GIT_TERMINAL_PROMPT"] = "0"
                env["GH_TOKEN"] = config.github_token
                # For git credential manager / gh auth
                env["GITHUB_TOKEN"] = config.github_token

            # Fetch latest
            fetch_result = subprocess.run(
                ["git", "fetch", "origin", config.branch],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60,
                env=env,
            )
            if fetch_result.returncode != 0:
                result["errors"].append(f"git fetch failed: {fetch_result.stderr.strip()}")
            else:
                result["pulled"] = True

                # Find changed files
                diff_result = subprocess.run(
                    ["git", "diff", "--name-only", f"HEAD..origin/{config.branch}"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if diff_result.returncode == 0:
                    changed = [f for f in diff_result.stdout.strip().splitlines() if f]
                    result["changed_files"] = changed

        except subprocess.TimeoutExpired:
            result["errors"].append("Git operation timed out")
        except FileNotFoundError:
            result["errors"].append("git not found in PATH")

    # Re-index changed files
    if result["changed_files"]:
        try:
            from repo_brain.ingestion.embedder import generate_embeddings
        except ImportError:
            result["errors"].append(
                "sentence-transformers is required for re-indexing. "
                "Install it with: uv pip install 'repo-brain[index]'"
            )
            return result

        from repo_brain.ingestion.chunker import chunk_file
        from repo_brain.ingestion.scanner import get_language
        from repo_brain.storage.metadata_db import MetadataDB, compute_file_hash
        from repo_brain.storage.vector_store import VectorStore

        store = VectorStore(config)
        metadata_db = MetadataDB(config)

        for rel_path in result["changed_files"]:
            abs_path = repo_path / rel_path
            if not abs_path.exists():
                # File was deleted
                store.delete_by_file(rel_path)
                metadata_db.remove_file(rel_path)
                continue

            try:
                chunks = chunk_file(abs_path, config)
                if not chunks:
                    continue

                documents = [c.to_document() for c in chunks]
                embeddings = generate_embeddings(documents, model_name=config.embedding_model)

                ids = [c.chunk_id for c in chunks]
                metadatas = [
                    {
                        "file_path": c.file_path,
                        "language": c.language,
                        "symbol_name": c.symbol_name,
                        "symbol_type": c.symbol_type,
                        "service": c.service,
                        "line_start": c.line_start,
                        "line_end": c.line_end,
                    }
                    for c in chunks
                ]

                store.delete_by_file(rel_path)
                store.add_chunks(ids, documents, embeddings, metadatas)

                content_hash = compute_file_hash(abs_path)
                language = get_language(abs_path)
                service = chunks[0].service if chunks else ""
                metadata_db.update_file(
                    rel_path, content_hash, language, service, len(chunks), len(documents)
                )
                result["reindexed"] += 1

            except Exception as e:
                result["errors"].append(f"Failed to re-index {rel_path}: {e}")

        try:
            metadata_db.close()
        except Exception:
            pass

    return result
