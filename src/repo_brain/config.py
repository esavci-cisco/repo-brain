"""Configuration management for repo-brain."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_BASE_DIR = Path.home() / ".repo-brain"
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_CHUNK_MAX_LINES = 100
DEFAULT_CHUNK_OVERLAP_LINES = 5

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".md": "markdown",
    ".sh": "shell",
    ".bash": "shell",
    ".sql": "sql",
    ".proto": "protobuf",
    ".tf": "terraform",
    ".hcl": "hcl",
    ".dockerfile": "dockerfile",
}

# Files that should always be skipped
SKIP_PATTERNS: list[str] = [
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".next",
    "coverage",
    ".cache",
    ".DS_Store",
    "*.pyc",
    "*.pyo",
    "*.egg-info",
    "target",  # Rust
    ".tox",
    ".venv-test",  # Test virtualenvs
    "*.lock",  # Lock files (uv.lock, package-lock.json, etc.)
    "*.min.js",  # Minified files
    "*.min.css",
    "*.map",  # Source maps
    "coverage-reports",
    ".nyc_output",
    ".terraform",
    "*.tar.gz",
    "*.zip",
]


@dataclass
class RepoConfig:
    """Configuration for a single repository."""

    name: str
    path: str
    remote_url: str = ""
    branch: str = "develop"
    github_token: str = ""
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    chunk_max_lines: int = DEFAULT_CHUNK_MAX_LINES
    chunk_overlap_lines: int = DEFAULT_CHUNK_OVERLAP_LINES
    extra_skip_patterns: list[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        """Generate a unique slug for this repo based on its name."""
        # Sanitise for filesystem safety
        cleaned = self.name.replace("/", "-").replace("\\", "-").replace(" ", "-")
        return cleaned or "unnamed"

    @property
    def data_dir(self) -> Path:
        """Path to this repo's data directory."""
        return DEFAULT_BASE_DIR / "repos" / self.slug

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def metadata_db_path(self) -> Path:
        return self.data_dir / "metadata.db"

    @property
    def graph_path(self) -> Path:
        return self.data_dir / "graph.json"

    @property
    def docs_dir(self) -> Path:
        return self.data_dir / "docs"


@dataclass
class GlobalConfig:
    """Global repo-brain configuration."""

    base_dir: Path = field(default_factory=lambda: DEFAULT_BASE_DIR)
    default_embedding_model: str = DEFAULT_EMBEDDING_MODEL

    @property
    def config_path(self) -> Path:
        return self.base_dir / "config.toml"

    @property
    def repos_dir(self) -> Path:
        return self.base_dir / "repos"


def _detect_remote_url(repo_path: Path) -> str:
    """Try to detect git remote URL from a repo."""
    try:
        import git

        repo = git.Repo(repo_path)
        if repo.remotes:
            return repo.remotes.origin.url
    except Exception:
        pass
    return ""


def _detect_branch(repo_path: Path) -> str:
    """Try to detect the default branch."""
    try:
        import git

        repo = git.Repo(repo_path)
        return repo.active_branch.name
    except Exception:
        return "develop"


def load_global_config() -> GlobalConfig:
    """Load global config from ~/.repo-brain/config.toml."""
    config = GlobalConfig()
    if config.config_path.exists():
        data = tomllib.loads(config.config_path.read_text())
        if "base_dir" in data:
            config.base_dir = Path(data["base_dir"])
        if "default_embedding_model" in data:
            config.default_embedding_model = data["default_embedding_model"]
    return config


def save_global_config(config: GlobalConfig) -> None:
    """Save global config."""
    config.base_dir.mkdir(parents=True, exist_ok=True)
    content = f"""# repo-brain global configuration
[settings]
default_embedding_model = "{config.default_embedding_model}"
"""
    config.config_path.write_text(content)


def load_repo_config(repo_slug: str) -> RepoConfig | None:
    """Load a repo config by slug."""
    global_config = load_global_config()
    config_path = global_config.repos_dir / repo_slug / "config.toml"
    if not config_path.exists():
        return None
    data = tomllib.loads(config_path.read_text())
    repo_data = data.get("repo", {})
    return RepoConfig(
        name=repo_data.get("name", repo_slug),
        path=repo_data.get("path", ""),
        remote_url=repo_data.get("remote_url", ""),
        branch=repo_data.get("branch", "develop"),
        github_token=repo_data.get("github_token", ""),
        embedding_model=repo_data.get("embedding_model", DEFAULT_EMBEDDING_MODEL),
        chunk_max_lines=repo_data.get("chunk_max_lines", DEFAULT_CHUNK_MAX_LINES),
        chunk_overlap_lines=repo_data.get("chunk_overlap_lines", DEFAULT_CHUNK_OVERLAP_LINES),
        extra_skip_patterns=repo_data.get("extra_skip_patterns", []),
    )


def save_repo_config(config: RepoConfig) -> None:
    """Save repo config to its data directory."""
    config.data_dir.mkdir(parents=True, exist_ok=True)
    config.docs_dir.mkdir(parents=True, exist_ok=True)

    extra = ""
    if config.extra_skip_patterns:
        patterns = ", ".join(f'"{p}"' for p in config.extra_skip_patterns)
        extra = f"extra_skip_patterns = [{patterns}]"

    content = f"""# repo-brain configuration for {config.name}
[repo]
name = "{config.name}"
path = "{config.path}"
remote_url = "{config.remote_url}"
branch = "{config.branch}"
embedding_model = "{config.embedding_model}"
chunk_max_lines = {config.chunk_max_lines}
chunk_overlap_lines = {config.chunk_overlap_lines}
{extra}
"""
    (config.data_dir / "config.toml").write_text(content)


def find_repo_config_by_path(repo_path: str) -> RepoConfig | None:
    """Find a repo config by its filesystem path."""
    global_config = load_global_config()
    repos_dir = global_config.repos_dir
    if not repos_dir.exists():
        return None
    for slug_dir in repos_dir.iterdir():
        if not slug_dir.is_dir():
            continue
        config = load_repo_config(slug_dir.name)
        if config and config.path == repo_path:
            return config
    return None


def list_repos() -> list[RepoConfig]:
    """List all registered repos."""
    global_config = load_global_config()
    repos_dir = global_config.repos_dir
    if not repos_dir.exists():
        return []
    configs: list[RepoConfig] = []
    for slug_dir in repos_dir.iterdir():
        if not slug_dir.is_dir():
            continue
        config = load_repo_config(slug_dir.name)
        if config:
            configs.append(config)
    return configs


def init_repo(repo_path: str, name: str | None = None) -> RepoConfig:
    """Initialize a new repo for tracking."""
    path = Path(repo_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Repository path does not exist: {path}")

    remote_url = _detect_remote_url(path)
    branch = _detect_branch(path)
    repo_name = name or path.name

    config = RepoConfig(
        name=repo_name,
        path=str(path),
        remote_url=remote_url,
        branch=branch,
    )

    # Ensure global config exists
    global_config = load_global_config()
    save_global_config(global_config)

    # Save repo config
    save_repo_config(config)

    return config
