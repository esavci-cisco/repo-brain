"""Tree-sitter based language-agnostic code chunker.

Based on Aider's approach for uniform multi-language support.
Uses tree-sitter queries to extract definitions and references from any language.
"""

from __future__ import annotations

import hashlib
import logging
import warnings
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# Suppress FutureWarning from tree_sitter
warnings.simplefilter("ignore", category=FutureWarning)

try:
    from tree_sitter import Language, Parser, Query, QueryCursor
    from tree_sitter_language_pack import get_language, get_parser

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    Language = None
    Parser = None
    Query = None
    QueryCursor = None
    get_language = None
    get_parser = None

from repo_brain.config import RepoConfig

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
        """Format chunk as a document for embedding."""
        parts: list[str] = []

        # Header with context
        if self.service:
            parts.append(f"Service: {self.service}")

        # File location
        parts.append(f"File: {self.file_path}")

        # Symbol information
        if self.symbol_name:
            symbol_desc = self.symbol_type or "symbol"
            if self.parent_class:
                parts.append(f"{symbol_desc.capitalize()}: {self.parent_class}.{self.symbol_name}")
            else:
                parts.append(f"{symbol_desc.capitalize()}: {self.symbol_name}")

        # Code content
        parts.append("")
        parts.append(self.content)

        return "\n".join(parts)


def filename_to_lang(fname: str) -> str | None:
    """Map filename to tree-sitter language name."""
    # Common language extensions
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
        ".cs": "c_sharp",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".lua": "lua",
        ".r": "r",
        ".m": "objective_c",
        ".sh": "bash",
    }

    ext = Path(fname).suffix.lower()
    return ext_map.get(ext)


def get_scm_queries(lang: str) -> str | None:
    """Get tree-sitter query file for a language."""
    # These queries are based on Aider's approach
    # They extract name.definition.* and name.reference.* nodes

    queries = {
        "python": """
(function_definition
  name: (identifier) @name.definition.function)

(class_definition
  name: (identifier) @name.definition.class)

(identifier) @name.reference.identifier
""",
        "go": """
(function_declaration
  name: (identifier) @name.definition.function)

(method_declaration
  name: (field_identifier) @name.definition.method)

(type_declaration
  (type_spec
    name: (type_identifier) @name.definition.type))

(identifier) @name.reference.identifier
(field_identifier) @name.reference.field
(type_identifier) @name.reference.type
""",
        "javascript": """
(function_declaration
  name: (identifier) @name.definition.function)

(class_declaration
  name: (identifier) @name.definition.class)

(method_definition
  name: (property_identifier) @name.definition.method)

(identifier) @name.reference.identifier
""",
        "typescript": """
(function_declaration
  name: (identifier) @name.definition.function)

(class_declaration
  name: (type_identifier) @name.definition.class)

(method_definition
  name: (property_identifier) @name.definition.method)

(interface_declaration
  name: (type_identifier) @name.definition.interface)

(identifier) @name.reference.identifier
(type_identifier) @name.reference.type
""",
        "rust": """
(function_item
  name: (identifier) @name.definition.function)

(struct_item
  name: (type_identifier) @name.definition.struct)

(impl_item
  type: (type_identifier) @name.definition.impl)

(identifier) @name.reference.identifier
(type_identifier) @name.reference.type
""",
        "java": """
(method_declaration
  name: (identifier) @name.definition.method)

(class_declaration
  name: (identifier) @name.definition.class)

(interface_declaration
  name: (identifier) @name.definition.interface)

(identifier) @name.reference.identifier
""",
        "cpp": """
(function_definition
  declarator: (function_declarator
    declarator: (identifier) @name.definition.function))

(class_specifier
  name: (type_identifier) @name.definition.class)

(identifier) @name.reference.identifier
(type_identifier) @name.reference.type
""",
    }

    return queries.get(lang)


class TreeSitterChunker:
    """Language-agnostic code chunker using tree-sitter."""

    def __init__(self, config: RepoConfig):
        self.config = config
        self.parsers: dict[str, Parser] = {}

        if not TREE_SITTER_AVAILABLE:
            logger.warning(
                "tree-sitter not available. Install with: pip install tree-sitter tree-sitter-language-pack"
            )

    def get_parser(self, lang: str) -> Parser | None:
        """Get or create a parser for the given language."""
        if not TREE_SITTER_AVAILABLE:
            return None

        if lang in self.parsers:
            return self.parsers[lang]

        try:
            language = get_language(lang)
            parser = get_parser(lang)
            self.parsers[lang] = parser
            return parser
        except Exception as e:
            logger.warning(f"Failed to get parser for {lang}: {e}")
            return None

    def chunk_file(
        self,
        file_path: Path,
        content: str,
        relative_path: str,
    ) -> list[CodeChunk]:
        """Chunk a file using tree-sitter if available."""
        if not TREE_SITTER_AVAILABLE:
            # Fallback to whole-file chunking
            return self._fallback_chunk(file_path, content, relative_path)

        lang = filename_to_lang(str(file_path))
        if not lang:
            return self._fallback_chunk(file_path, content, relative_path)

        parser = self.get_parser(lang)
        if not parser:
            return self._fallback_chunk(file_path, content, relative_path)

        query_scm = get_scm_queries(lang)
        if not query_scm:
            return self._fallback_chunk(file_path, content, relative_path)

        try:
            tree = parser.parse(bytes(content, "utf-8"))
            language_obj = get_language(lang)
            query = Query(language_obj, query_scm)

            # Extract definitions
            chunks = self._extract_definitions(tree, query, content, file_path, relative_path, lang)

            if not chunks:
                # No definitions found, return whole file
                return self._fallback_chunk(file_path, content, relative_path)

            return chunks

        except Exception as e:
            logger.warning(f"Tree-sitter parsing failed for {file_path}: {e}")
            return self._fallback_chunk(file_path, content, relative_path)

    def _extract_definitions(
        self,
        tree,
        query: Query,
        content: str,
        file_path: Path,
        relative_path: str,
        lang: str,
    ) -> list[CodeChunk]:
        """Extract function/class definitions from parsed tree."""
        chunks = []
        lines = content.splitlines(keepends=True)

        try:
            # Run query to find all definitions
            cursor = QueryCursor()
            captures = cursor.captures(tree.root_node, query)

            # Group by tag type
            definitions = []
            for node, tag in captures:
                tag_str = tag
                if isinstance(tag, int):
                    # tree-sitter 0.25.x returns int indices
                    tag_str = query.capture_names[tag]

                if tag_str.startswith("name.definition."):
                    symbol_type = tag_str.replace("name.definition.", "")
                    definitions.append(
                        {
                            "name": node.text.decode("utf-8"),
                            "type": symbol_type,
                            "start_line": node.start_point[0],
                            "end_line": node.end_point[0],
                            "node": node,
                        }
                    )
        except Exception as e:
            logger.debug(f"Failed to extract definitions: {e}")
            return []

        if not definitions:
            return []

        # Sort by line number
        definitions.sort(key=lambda x: x["start_line"])

        # Create chunks for each definition
        for i, defn in enumerate(definitions):
            # Determine chunk boundaries
            start_line = defn["start_line"]

            # Try to find the end of this definition
            # Look for the parent node that represents the whole function/class
            parent = defn["node"]
            while parent and parent.type not in (
                "function_definition",
                "function_declaration",
                "function_item",
                "method_declaration",
                "method_definition",
                "class_definition",
                "class_declaration",
                "struct_item",
                "interface_declaration",
                "impl_item",
            ):
                parent = parent.parent

            if parent:
                end_line = parent.end_point[0]
            else:
                # Estimate based on next definition or end of file
                if i + 1 < len(definitions):
                    end_line = definitions[i + 1]["start_line"] - 1
                else:
                    end_line = len(lines) - 1

            # Extract content
            chunk_lines = lines[start_line : end_line + 1]
            chunk_content = "".join(chunk_lines)

            # Infer service name from path
            service = self._infer_service(relative_path)

            # Generate chunk ID
            chunk_id = self._generate_chunk_id(relative_path, start_line, end_line)

            chunks.append(
                CodeChunk(
                    chunk_id=chunk_id,
                    file_path=relative_path,
                    language=lang,
                    content=chunk_content.strip(),
                    line_start=start_line + 1,  # 1-indexed for display
                    line_end=end_line + 1,
                    symbol_name=defn["name"],
                    symbol_type=defn["type"],
                    service=service,
                )
            )

        return chunks

    def _fallback_chunk(
        self,
        file_path: Path,
        content: str,
        relative_path: str,
    ) -> list[CodeChunk]:
        """Fallback to whole-file chunking."""
        lang = filename_to_lang(str(file_path)) or "unknown"
        service = self._infer_service(relative_path)
        chunk_id = self._generate_chunk_id(relative_path, 0, len(content.splitlines()))

        return [
            CodeChunk(
                chunk_id=chunk_id,
                file_path=relative_path,
                language=lang,
                content=content.strip(),
                line_start=1,
                line_end=len(content.splitlines()),
                symbol_name="__file__",
                symbol_type="module",
                service=service,
            )
        ]

    def _infer_service(self, relative_path: str) -> str:
        """Infer service name from file path."""
        parts = Path(relative_path).parts
        for i, part in enumerate(parts):
            if part == "services" and i + 1 < len(parts):
                return parts[i + 1]
        return ""

    def _generate_chunk_id(self, relative_path: str, start: int, end: int) -> str:
        """Generate unique chunk ID."""
        key = f"{relative_path}:{start}:{end}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]


def chunk_repository(repo_path: Path, config: RepoConfig) -> list[CodeChunk]:
    """Chunk all files in a repository using tree-sitter."""
    chunker = TreeSitterChunker(config)
    all_chunks = []

    # Scan all tracked files
    from repo_brain.ingestion.scanner import scan_repository

    files = scan_repository(repo_path, config)

    for file_info in files:
        file_path = repo_path / file_info.relative_path
        try:
            content = file_path.read_text(encoding="utf-8")
            chunks = chunker.chunk_file(file_path, content, file_info.relative_path)
            all_chunks.extend(chunks)
        except Exception as e:
            logger.warning(f"Failed to chunk {file_path}: {e}")
            continue

    logger.info(f"Generated {len(all_chunks)} chunks from {len(files)} files")
    return all_chunks
