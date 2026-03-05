"""Repo map generator — AST-based skeleton of the repository.

Uses Tree-sitter to parse source files and extract only structural
information: file paths, class names, function/method signatures
(with parameters and return types).  Function bodies, comments, and
import statements are excluded to keep the output compact.

The generated map is designed to be injected into an LLM system prompt
via ``opencode.json`` instructions, giving the model "spatial awareness"
of the entire codebase without reading every file.

Token budget target: ~2 000 tokens for the final output.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from repo_brain.config import RepoConfig
from repo_brain.ingestion.scanner import scan_files

logger = logging.getLogger(__name__)

# Languages supported by the Tree-sitter repo map generator.
# Maps file extension → tree-sitter language name.
_TS_LANG_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
}


@dataclass
class Symbol:
    """A single extracted symbol (class, function, method, interface, etc.)."""

    name: str
    kind: str  # "class", "function", "method", "interface", "type"
    signature: str  # e.g. "def foo(x: int) -> str"
    line: int
    children: list[Symbol] = field(default_factory=list)


@dataclass
class FileSymbols:
    """All symbols extracted from a single file."""

    rel_path: str
    language: str
    symbols: list[Symbol] = field(default_factory=list)


# ── Tree-sitter extraction ───────────────────────────────────────────


def _get_parser(lang: str):
    """Get a tree-sitter parser for the given language."""
    from tree_sitter_language_pack import get_parser

    return get_parser(lang)


def _node_text(node) -> str:
    """Decode a tree-sitter node's text."""
    return node.text.decode("utf-8", errors="replace")


def _extract_python(root_node) -> list[Symbol]:
    """Extract classes and top-level functions from a Python AST."""
    symbols: list[Symbol] = []

    for node in root_node.children:
        if node.type == "class_definition":
            symbols.append(_extract_python_class(node))
        elif node.type == "function_definition":
            symbols.append(_extract_python_function(node))
        elif node.type == "decorated_definition":
            # Handle decorated classes/functions
            for child in node.children:
                if child.type == "class_definition":
                    symbols.append(_extract_python_class(child))
                elif child.type == "function_definition":
                    symbols.append(_extract_python_function(child))

    return symbols


def _extract_python_class(node) -> Symbol:
    """Extract a Python class with its methods."""
    name = ""
    bases = ""
    methods: list[Symbol] = []

    for child in node.children:
        if child.type == "identifier":
            name = _node_text(child)
        elif child.type == "argument_list":
            bases = _node_text(child)
        elif child.type == "block":
            for block_child in child.children:
                if block_child.type == "function_definition":
                    methods.append(_extract_python_function(block_child))
                elif block_child.type == "decorated_definition":
                    for dec_child in block_child.children:
                        if dec_child.type == "function_definition":
                            methods.append(_extract_python_function(dec_child))

    sig = f"class {name}{bases}" if bases else f"class {name}"
    return Symbol(
        name=name,
        kind="class",
        signature=sig,
        line=node.start_point[0] + 1,
        children=methods,
    )


def _extract_python_function(node) -> Symbol:
    """Extract a Python function/method signature."""
    name = ""
    params = ""
    return_type = ""
    is_async = False

    for child in node.children:
        if child.type == "identifier":
            name = _node_text(child)
        elif child.type == "parameters":
            params = _node_text(child)
        elif child.type == "type":
            return_type = _node_text(child)
        elif child.type == "async":
            is_async = True

    prefix = "async def" if is_async else "def"
    sig = f"{prefix} {name}{params}"
    if return_type:
        sig += f" -> {return_type}"

    kind = "method" if _is_method_params(params) else "function"
    return Symbol(name=name, kind=kind, signature=sig, line=node.start_point[0] + 1)


def _is_method_params(params: str) -> bool:
    """Check if params suggest this is a method (has self/cls)."""
    stripped = params.strip("()")
    first_param = stripped.split(",")[0].strip().split(":")[0].strip()
    return first_param in ("self", "cls")


# ── TypeScript / JavaScript extraction ───────────────────────────────


def _extract_typescript(root_node) -> list[Symbol]:
    """Extract classes, functions, interfaces from TS/JS AST."""
    symbols: list[Symbol] = []

    for node in root_node.children:
        extracted = _extract_ts_node(node)
        if extracted:
            symbols.append(extracted)

    return symbols


def _extract_ts_node(node) -> Symbol | None:
    """Extract a single TS/JS top-level declaration."""
    # Handle export wrappers
    if node.type == "export_statement":
        for child in node.children:
            result = _extract_ts_node(child)
            if result:
                return result
        return None

    if node.type == "class_declaration":
        return _extract_ts_class(node)
    elif node.type == "function_declaration":
        return _extract_ts_function(node)
    elif node.type == "interface_declaration":
        return _extract_ts_interface(node)
    elif node.type == "type_alias_declaration":
        return _extract_ts_type_alias(node)
    elif node.type == "lexical_declaration":
        return _extract_ts_const_function(node)

    return None


def _extract_ts_class(node) -> Symbol:
    """Extract a TypeScript/JS class."""
    name = ""
    methods: list[Symbol] = []

    for child in node.children:
        if child.type == "type_identifier":
            name = _node_text(child)
        elif child.type == "class_body":
            for body_child in child.children:
                if body_child.type in ("method_definition", "public_field_definition"):
                    method = _extract_ts_method(body_child)
                    if method:
                        methods.append(method)

    return Symbol(
        name=name,
        kind="class",
        signature=f"class {name}",
        line=node.start_point[0] + 1,
        children=methods,
    )


def _extract_ts_method(node) -> Symbol | None:
    """Extract a TypeScript/JS method."""
    if node.type != "method_definition":
        return None

    name = ""
    params = ""
    return_type = ""

    for child in node.children:
        if child.type in ("property_identifier", "identifier"):
            name = _node_text(child)
        elif child.type == "formal_parameters":
            params = _node_text(child)
        elif child.type == "type_annotation":
            return_type = _node_text(child).lstrip(": ")

    sig = f"{name}{params}"
    if return_type:
        sig += f": {return_type}"

    return Symbol(name=name, kind="method", signature=sig, line=node.start_point[0] + 1)


def _extract_ts_function(node) -> Symbol:
    """Extract a TypeScript/JS function declaration."""
    name = ""
    params = ""
    return_type = ""

    for child in node.children:
        if child.type == "identifier":
            name = _node_text(child)
        elif child.type == "formal_parameters":
            params = _node_text(child)
        elif child.type == "type_annotation":
            return_type = _node_text(child).lstrip(": ")

    sig = f"function {name}{params}"
    if return_type:
        sig += f": {return_type}"

    return Symbol(name=name, kind="function", signature=sig, line=node.start_point[0] + 1)


def _extract_ts_interface(node) -> Symbol:
    """Extract a TypeScript interface."""
    name = ""
    methods: list[Symbol] = []

    for child in node.children:
        if child.type == "type_identifier":
            name = _node_text(child)
        elif child.type == "interface_body" or child.type == "object_type":
            for body_child in child.children:
                if body_child.type in ("method_signature", "property_signature"):
                    sig_name = ""
                    sig_params = ""
                    sig_ret = ""
                    for sc in body_child.children:
                        if sc.type in ("property_identifier", "identifier"):
                            sig_name = _node_text(sc)
                        elif sc.type == "formal_parameters":
                            sig_params = _node_text(sc)
                        elif sc.type == "type_annotation":
                            sig_ret = _node_text(sc).lstrip(": ")
                    if sig_name:
                        sig = f"{sig_name}{sig_params}"
                        if sig_ret:
                            sig += f": {sig_ret}"
                        methods.append(
                            Symbol(
                                name=sig_name,
                                kind="method",
                                signature=sig,
                                line=body_child.start_point[0] + 1,
                            )
                        )

    return Symbol(
        name=name,
        kind="interface",
        signature=f"interface {name}",
        line=node.start_point[0] + 1,
        children=methods,
    )


def _extract_ts_type_alias(node) -> Symbol:
    """Extract a TypeScript type alias."""
    name = ""
    for child in node.children:
        if child.type == "type_identifier":
            name = _node_text(child)
            break

    return Symbol(
        name=name,
        kind="type",
        signature=f"type {name}",
        line=node.start_point[0] + 1,
    )


def _extract_ts_const_function(node) -> Symbol | None:
    """Extract arrow functions assigned to const (e.g. const foo = () => ...)."""
    for child in node.children:
        if child.type == "variable_declarator":
            name = ""
            is_function = False
            for vc in child.children:
                if vc.type == "identifier":
                    name = _node_text(vc)
                elif vc.type in ("arrow_function", "function"):
                    is_function = True
            if name and is_function:
                return Symbol(
                    name=name,
                    kind="function",
                    signature=f"const {name}",
                    line=node.start_point[0] + 1,
                )
    return None


# ── Extraction dispatch ──────────────────────────────────────────────

_EXTRACTORS: dict[str, Any] = {
    "python": _extract_python,
    "typescript": _extract_typescript,
    "tsx": _extract_typescript,
    "javascript": _extract_typescript,
}


def extract_file_symbols(file_path: Path, repo_root: Path) -> FileSymbols | None:
    """Parse a single file and extract its symbols.

    Returns None if the file's language is not supported by Tree-sitter
    or if parsing fails.
    """
    suffix = file_path.suffix.lower()
    ts_lang = _TS_LANG_MAP.get(suffix)
    if not ts_lang:
        return None

    extractor = _EXTRACTORS.get(ts_lang)
    if not extractor:
        return None

    try:
        source = file_path.read_bytes()
    except (OSError, UnicodeDecodeError):
        return None

    # Skip very large files
    if len(source) > 500_000:  # ~500KB
        return None

    try:
        parser = _get_parser(ts_lang)
        tree = parser.parse(source)
    except Exception as e:
        logger.debug("Tree-sitter parse failed for %s: %s", file_path, e)
        return None

    symbols = extractor(tree.root_node)
    if not symbols:
        return None

    try:
        rel_path = str(file_path.relative_to(repo_root))
    except ValueError:
        rel_path = str(file_path)

    return FileSymbols(rel_path=rel_path, language=ts_lang, symbols=symbols)


# ── Ranking ──────────────────────────────────────────────────────────


def _is_test_file(rel_path: str) -> bool:
    """Check if a file is a test file (low value for repo map)."""
    parts = rel_path.replace("\\", "/").split("/")
    basename = parts[-1] if parts else ""

    # Directory-level test indicators
    for part in parts:
        if part in ("tests", "test", "__tests__", "spec", "specs", "fixtures"):
            return True

    # File-level test indicators
    if basename.startswith("test_") or basename.endswith("_test.py"):
        return True
    if basename.endswith((".test.ts", ".test.tsx", ".test.js", ".test.jsx")):
        return True
    if basename.endswith((".spec.ts", ".spec.tsx", ".spec.js", ".spec.jsx")):
        return True
    if basename.startswith("conftest"):
        return True

    return False


def _rank_files_by_references(
    all_files: list[FileSymbols],
    graph_store: Any | None = None,
) -> list[FileSymbols]:
    """Rank files by importance using symbol references and graph data.

    Files with more symbols and graph connections are ranked higher.
    If a graph store is available, nodes with more dependents get a boost.
    Test files are excluded entirely.
    """
    # Filter out test files — they inflate the map with low-value symbols
    all_files = [fs for fs in all_files if not _is_test_file(fs.rel_path)]

    scores: dict[str, float] = {}

    # Base score: number of symbols (classes worth more than functions)
    for fs in all_files:
        score = 0.0
        for sym in fs.symbols:
            if sym.kind in ("class", "struct", "interface"):
                score += 3.0
                score += min(len(sym.children) * 0.5, 5.0)
            elif sym.kind == "function":
                score += 1.0
            elif sym.kind == "type":
                score += 1.5
        scores[fs.rel_path] = score

    # Graph boost: if we have a dependency graph, boost files in
    # highly-connected nodes.
    if graph_store is not None:
        try:
            for node_info in graph_store.get_all_nodes():
                node_name = node_info.get("name", "")
                downstream = graph_store.get_downstream(node_name, depth=1)
                boost = min(len(downstream) * 0.5, 5.0)
                # Apply boost to files that belong to this service
                for fs in all_files:
                    if node_name in fs.rel_path:
                        scores[fs.rel_path] = scores.get(fs.rel_path, 0) + boost
        except Exception:
            pass

    # Sort by score descending
    all_files.sort(key=lambda fs: scores.get(fs.rel_path, 0), reverse=True)
    return all_files


# ── Formatting ───────────────────────────────────────────────────────

# Approximate token budget.  1 token ≈ 4 chars in code-like text.
_TOKEN_BUDGET = 2000
_CHAR_BUDGET = _TOKEN_BUDGET * 4  # ~8 000 chars

# Max top-level symbols to show per file.
_MAX_SYMBOLS_PER_FILE = 8

# Max methods to show per class/interface.  Beyond this we summarize.
_MAX_METHODS_PER_SYMBOL = 3


def _format_symbol_compact(sym: Symbol, indent: int = 1) -> str:
    """Format a symbol compactly, collapsing children beyond the limit."""
    prefix = "  " * indent
    line = f"{prefix}{sym.signature}"

    if not sym.children:
        return line

    shown = sym.children[:_MAX_METHODS_PER_SYMBOL]
    hidden = len(sym.children) - len(shown)

    child_lines = [f"{'  ' * (indent + 1)}{c.signature}" for c in shown]
    if hidden > 0:
        child_lines.append(f"{'  ' * (indent + 1)}... +{hidden} more")

    return line + "\n" + "\n".join(child_lines)


def format_repo_map(
    files: list[FileSymbols],
    char_budget: int = _CHAR_BUDGET,
) -> str:
    """Format extracted symbols into a compact repo map string.

    Stops adding files once the character budget is reached (~2K tokens).
    Symbols per file are capped and methods are collapsed.
    """
    lines: list[str] = []
    lines.append("# Repository Map")
    lines.append("")
    lines.append("Structural overview of key files (classes, functions, signatures).")
    lines.append("Use this to understand what exists and where before reading files.")
    lines.append("")

    total_chars = sum(len(ln) + 1 for ln in lines)  # +1 for newline

    for fs in files:
        # Build this file's block first, then check budget
        file_lines: list[str] = []
        file_lines.append(f"## {fs.rel_path}")

        symbols_to_show = fs.symbols[:_MAX_SYMBOLS_PER_FILE]
        hidden_symbols = len(fs.symbols) - len(symbols_to_show)

        for sym in symbols_to_show:
            file_lines.append(_format_symbol_compact(sym))

        if hidden_symbols > 0:
            file_lines.append(f"  ... +{hidden_symbols} more symbols")

        file_lines.append("")

        block_chars = sum(len(ln) + 1 for ln in file_lines)

        if total_chars + block_chars > char_budget:
            # Budget exhausted — note how many files were skipped
            remaining = len(files) - len([ln for ln in lines if ln.startswith("## ")])
            if remaining > 0:
                lines.append(f"*... {remaining} more files omitted*")
                lines.append("")
            break

        lines.extend(file_lines)
        total_chars += block_chars

    return "\n".join(lines)


# ── Public API ───────────────────────────────────────────────────────


def generate_repo_map(
    config: RepoConfig,
    max_files: int = 50,
    graph_store: Any | None = None,
) -> str:
    """Generate a repo map for the entire repository.

    Scans all supported files, extracts symbols via Tree-sitter,
    ranks by importance, and returns a formatted string.

    Args:
        config: Repository configuration.
        max_files: Maximum number of files to include in the map.
        graph_store: Optional graph store for ranking boost.

    Returns:
        Formatted repo map string (markdown).
    """
    repo_root = Path(config.path)
    files = scan_files(config)

    # Extract symbols from all supported files
    all_file_symbols: list[FileSymbols] = []
    for file_path in files:
        fs = extract_file_symbols(file_path, repo_root)
        if fs:
            all_file_symbols.append(fs)

    logger.info(
        "Extracted symbols from %d / %d files",
        len(all_file_symbols),
        len(files),
    )

    if not all_file_symbols:
        return "# Repository Map\n\nNo supported source files found.\n"

    # Rank and truncate
    ranked = _rank_files_by_references(all_file_symbols, graph_store=graph_store)
    top_files = ranked[:max_files]

    return format_repo_map(top_files)


def save_repo_map(config: RepoConfig, graph_store: Any | None = None) -> Path:
    """Generate and save the repo map to .repo-brain/repomap.md.

    The map is saved inside the target repository (not in ~/.repo-brain)
    so that ``opencode.json`` can reference it via a relative path.

    Returns:
        Path to the written file.
    """
    repo_root = Path(config.path)
    output_dir = repo_root / ".repo-brain"
    output_dir.mkdir(exist_ok=True)

    content = generate_repo_map(config, graph_store=graph_store)

    output_path = output_dir / "repomap.md"
    output_path.write_text(content + "\n")

    # Ensure .repo-brain/ is gitignored
    _ensure_gitignore(repo_root, ".repo-brain/")

    logger.info("Wrote repo map to %s", output_path)
    return output_path


def _ensure_gitignore(repo_root: Path, entry: str) -> None:
    """Make sure an entry exists in the repo's .gitignore."""
    gitignore = repo_root / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text()
        if entry in content:
            return
        if not content.endswith("\n"):
            content += "\n"
        content += f"{entry}\n"
        gitignore.write_text(content)
    else:
        gitignore.write_text(f"{entry}\n")
