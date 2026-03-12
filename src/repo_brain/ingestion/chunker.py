"""AST-aware code chunker.

Uses tree-sitter for language-agnostic chunking when available.
Falls back to Python AST for Python files.
Falls back to sliding window for unsupported languages.
"""

from __future__ import annotations

import ast
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

from repo_brain.config import RepoConfig
from repo_brain.ingestion.scanner import get_language

# Try to import tree-sitter chunker
try:
    from repo_brain.ingestion.tree_sitter_chunker import (
        TreeSitterChunker,
        TREE_SITTER_AVAILABLE,
    )
except ImportError:
    TREE_SITTER_AVAILABLE = False
    TreeSitterChunker = None

logger = logging.getLogger(__name__)


@dataclass
class CodeChunk:
    """A single chunk of code with metadata."""

    chunk_id: str
    file_path: str  # Relative to repo root
    language: str
    content: str
    line_start: int
    line_end: int
    symbol_name: str = ""  # Function/class name if available
    symbol_type: str = ""  # "function", "class", "method", "module"
    parent_class: str = ""  # For methods, the owning class
    imports: list[str] = field(default_factory=list)
    service: str = ""  # Inferred service name (e.g., "auth-service")

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()[:16]

    def to_document(self) -> str:
        """Format chunk as a document for embedding.

        Includes metadata in the text to improve semantic search relevance.
        """
        parts: list[str] = []

        # Header with context
        if self.service:
            parts.append(f"Service: {self.service}")
        parts.append(f"File: {self.file_path}")

        if self.symbol_name:
            label = self.symbol_type or "symbol"
            if self.parent_class:
                parts.append(f"{label}: {self.parent_class}.{self.symbol_name}")
            else:
                parts.append(f"{label}: {self.symbol_name}")

        parts.append(f"Language: {self.language}")
        parts.append("")  # Blank line
        parts.append(self.content)

        return "\n".join(parts)


def _generate_chunk_id(file_path: str, line_start: int, symbol_name: str) -> str:
    """Generate a deterministic chunk ID."""
    raw = f"{file_path}:{line_start}:{symbol_name}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def _infer_service(file_path: str) -> str:
    """Infer service name from file path.

    e.g., services/auth-service/app/main.go -> auth-service
          libraries/faa-models/src/... -> faa-models
          mcp_servers/rule-mcp/... -> rule-mcp
    """
    parts = Path(file_path).parts
    for i, part in enumerate(parts):
        if part in ("services", "libraries", "mcp_servers", "agents") and i + 1 < len(parts):
            return parts[i + 1]
    return ""


def _extract_imports_from_python(source: str) -> list[str]:
    """Extract import names from Python source."""
    imports: list[str] = []
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
    except SyntaxError:
        pass
    return imports


def _chunk_python(source: str, file_path: str, service: str) -> list[CodeChunk]:
    """Chunk Python source at function/class boundaries."""
    chunks: list[CodeChunk] = []
    lines = source.splitlines()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Fall back to sliding window if we can't parse
        return _chunk_sliding_window(source, file_path, "python", service)

    file_imports = _extract_imports_from_python(source)

    # Track which lines are covered by function/class chunks
    covered_lines: set[int] = set()

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            # Chunk the whole class
            start = node.lineno
            end = node.end_lineno or start
            class_content = "\n".join(lines[start - 1 : end])

            chunks.append(
                CodeChunk(
                    chunk_id=_generate_chunk_id(file_path, start, node.name),
                    file_path=file_path,
                    language="python",
                    content=class_content,
                    line_start=start,
                    line_end=end,
                    symbol_name=node.name,
                    symbol_type="class",
                    imports=file_imports,
                    service=service,
                )
            )
            covered_lines.update(range(start, end + 1))

            # Also chunk individual methods if the class is large
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    m_start = item.lineno
                    m_end = item.end_lineno or m_start
                    method_content = "\n".join(lines[m_start - 1 : m_end])

                    if m_end - m_start > 5:  # Only chunk methods > 5 lines
                        chunks.append(
                            CodeChunk(
                                chunk_id=_generate_chunk_id(
                                    file_path, m_start, f"{node.name}.{item.name}"
                                ),
                                file_path=file_path,
                                language="python",
                                content=method_content,
                                line_start=m_start,
                                line_end=m_end,
                                symbol_name=item.name,
                                symbol_type="method",
                                parent_class=node.name,
                                imports=file_imports,
                                service=service,
                            )
                        )

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno
            end = node.end_lineno or start
            func_content = "\n".join(lines[start - 1 : end])

            chunks.append(
                CodeChunk(
                    chunk_id=_generate_chunk_id(file_path, start, node.name),
                    file_path=file_path,
                    language="python",
                    content=func_content,
                    line_start=start,
                    line_end=end,
                    symbol_name=node.name,
                    symbol_type="function",
                    imports=file_imports,
                    service=service,
                )
            )
            covered_lines.update(range(start, end + 1))

    # If nothing was extracted (or file is mostly module-level), chunk the whole file
    if not chunks:
        chunks.append(
            CodeChunk(
                chunk_id=_generate_chunk_id(file_path, 1, "__module__"),
                file_path=file_path,
                language="python",
                content=source,
                line_start=1,
                line_end=len(lines),
                symbol_name="__module__",
                symbol_type="module",
                imports=file_imports,
                service=service,
            )
        )

    return chunks


def _chunk_sliding_window(
    source: str,
    file_path: str,
    language: str,
    service: str,
    max_lines: int = 80,
    overlap: int = 10,
) -> list[CodeChunk]:
    """Chunk using a sliding window. Fallback for non-Python files."""
    lines = source.splitlines()
    chunks: list[CodeChunk] = []

    if len(lines) <= max_lines:
        # Small file — single chunk
        chunks.append(
            CodeChunk(
                chunk_id=_generate_chunk_id(file_path, 1, "__file__"),
                file_path=file_path,
                language=language,
                content=source,
                line_start=1,
                line_end=len(lines),
                symbol_name="__file__",
                symbol_type="module",
                service=service,
            )
        )
        return chunks

    start = 0
    while start < len(lines):
        end = min(start + max_lines, len(lines))
        chunk_content = "\n".join(lines[start:end])

        chunks.append(
            CodeChunk(
                chunk_id=_generate_chunk_id(file_path, start + 1, f"__window_{start}__"),
                file_path=file_path,
                language=language,
                content=chunk_content,
                line_start=start + 1,
                line_end=end,
                symbol_name=f"lines_{start + 1}_{end}",
                symbol_type="fragment",
                service=service,
            )
        )

        if end >= len(lines):
            break
        start += max_lines - overlap

    return chunks


def chunk_file(file_path: Path, repo_config: RepoConfig) -> list[CodeChunk]:
    """Chunk a single file into indexable pieces."""
    repo_root = Path(repo_config.path)
    try:
        rel_path = str(file_path.relative_to(repo_root))
    except ValueError:
        rel_path = str(file_path)

    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.warning("Failed to read %s: %s", file_path, e)
        return []

    # Skip empty files
    if not source.strip():
        return []

    # Skip very large files (>10K lines likely generated)
    lines = source.splitlines()
    if len(lines) > 10_000:
        logger.info("Skipping large file (%d lines): %s", len(lines), rel_path)
        return []

    language = get_language(file_path)
    service = _infer_service(rel_path)

    # Try tree-sitter first for language-agnostic chunking
    if TREE_SITTER_AVAILABLE and TreeSitterChunker:
        chunker = TreeSitterChunker(repo_config)
        chunks = chunker.chunk_file(file_path, source, str(rel_path))
        # If tree-sitter succeeded and returned function-level chunks, use them
        if chunks and not (len(chunks) == 1 and chunks[0].symbol_name == "__file__"):
            logger.debug(f"Using tree-sitter chunks for {rel_path}: {len(chunks)} chunks")
            return chunks

    # Fall back to Python AST if available
    if language == "python":
        return _chunk_python(source, rel_path, service)

    # Final fallback to sliding window
    return _chunk_sliding_window(
        source,
        rel_path,
        language,
        service,
        max_lines=repo_config.chunk_max_lines,
        overlap=repo_config.chunk_overlap_lines,
    )
