"""File scanner — walks a repo respecting .gitignore and skip patterns."""

from __future__ import annotations

import fnmatch
import logging
from pathlib import Path

from repo_brain.config import SKIP_PATTERNS, SUPPORTED_EXTENSIONS, RepoConfig

logger = logging.getLogger(__name__)


def _should_skip(path: Path, skip_patterns: list[str]) -> bool:
    """Check if a path matches any skip pattern."""
    for pattern in skip_patterns:
        # Check each part of the path
        for part in path.parts:
            if fnmatch.fnmatch(part, pattern):
                return True
    return False


def _load_gitignore_patterns(repo_path: Path) -> list[str]:
    """Load patterns from .gitignore if it exists."""
    gitignore = repo_path / ".gitignore"
    if not gitignore.exists():
        return []
    patterns: list[str] = []
    for line in gitignore.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            # Normalize: remove trailing slashes for directory patterns
            patterns.append(line.rstrip("/"))
    return patterns


def scan_files(config: RepoConfig) -> list[Path]:
    """Scan a repository and return all indexable files.

    Respects .gitignore, skip patterns, and only returns files
    with supported extensions.
    """
    repo_path = Path(config.path)
    if not repo_path.exists():
        raise FileNotFoundError(f"Repository path does not exist: {repo_path}")

    # Combine all skip patterns
    all_skip = SKIP_PATTERNS + config.extra_skip_patterns
    gitignore_patterns = _load_gitignore_patterns(repo_path)
    all_skip.extend(gitignore_patterns)

    files: list[Path] = []
    supported_suffixes = set(SUPPORTED_EXTENSIONS.keys())

    # Also index Dockerfiles (no extension)
    dockerfile_names = {"Dockerfile", "dockerfile", "Containerfile"}

    for item in repo_path.rglob("*"):
        if not item.is_file():
            continue

        # Check relative path against skip patterns
        try:
            rel_path = item.relative_to(repo_path)
        except ValueError:
            continue

        if _should_skip(rel_path, all_skip):
            continue

        # Check extension or special filenames
        if item.suffix.lower() in supported_suffixes:
            files.append(item)
        elif item.name in dockerfile_names:
            files.append(item)
        elif item.name == "justfile":
            files.append(item)
        elif item.name == "Makefile":
            files.append(item)

    logger.info("Scanned %d files in %s", len(files), repo_path)
    return files


def get_language(file_path: Path) -> str:
    """Determine the language of a file."""
    suffix = file_path.suffix.lower()
    if suffix in SUPPORTED_EXTENSIONS:
        return SUPPORTED_EXTENSIONS[suffix]

    name = file_path.name.lower()
    if name in ("dockerfile", "containerfile"):
        return "dockerfile"
    if name in ("justfile", "makefile"):
        return "makefile"

    return "unknown"
