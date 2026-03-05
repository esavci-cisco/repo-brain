"""Embedding generation wrapper.

Only used during indexing (``repo-brain index`` / ``repo-brain setup``).
Query-time code paths use ChromaDB's built-in ONNX embedding instead,
so ``torch`` and ``sentence-transformers`` are never imported at query time.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy-loaded model cache.  Values are ``SentenceTransformer`` instances but
# we type as ``Any`` to avoid importing the heavy library at module level.
_model_cache: dict[str, object] = {}


def _local_model_dir(model_name: str) -> Path:
    """Path where we store a local copy of the model."""
    return Path.home() / ".repo-brain" / "models" / model_name


def _has_local_model(model_name: str) -> bool:
    """Check if we have a locally saved model."""
    local_dir = _local_model_dir(model_name)
    return (local_dir / "config.json").exists()


def export_model(model_name: str = "all-MiniLM-L6-v2") -> Path:
    """Save the model locally for faster loading.

    Downloads the model once from HuggingFace and saves it to
    ~/.repo-brain/models/. Future loads skip all network checks.
    """
    local_dir = _local_model_dir(model_name)
    if _has_local_model(model_name):
        logger.info("Model already saved at %s", local_dir)
        return local_dir

    logger.info("Downloading and saving model locally (one-time)...")
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    local_dir.mkdir(parents=True, exist_ok=True)
    model.save(str(local_dir), create_model_card=False)
    logger.info("Model saved to %s", local_dir)
    return local_dir


def get_model(model_name: str) -> object:
    """Get or load an embedding model. Lazy-loaded for fast startup."""
    if model_name not in _model_cache:
        logger.info("Loading embedding model: %s", model_name)
        from sentence_transformers import SentenceTransformer

        # Prefer local model (no network, fast load)
        if _has_local_model(model_name):
            local_dir = _local_model_dir(model_name)
            logger.info("Loading from local cache: %s", local_dir)
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            try:
                _model_cache[model_name] = SentenceTransformer(str(local_dir))
            finally:
                os.environ.pop("HF_HUB_OFFLINE", None)
                os.environ.pop("TRANSFORMERS_OFFLINE", None)
        else:
            # Fall back to HuggingFace download
            _model_cache[model_name] = SentenceTransformer(model_name)

        logger.info("Model loaded: %s", model_name)
    return _model_cache[model_name]


def generate_embeddings(
    texts: list[str],
    model_name: str = "all-MiniLM-L6-v2",
    batch_size: int = 64,
) -> list[list[float]]:
    """Generate embeddings for a list of texts.

    Args:
        texts: List of text strings to embed.
        model_name: Name of the sentence-transformers model.
        batch_size: Batch size for encoding.

    Returns:
        List of embedding vectors.
    """
    if not texts:
        return []

    model = get_model(model_name)
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=len(texts) > 100,
        normalize_embeddings=True,
    )
    return embeddings.tolist()
