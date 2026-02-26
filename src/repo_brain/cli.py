"""repo-brain CLI."""

from __future__ import annotations

import logging
import sys
import time

import click

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """repo-brain: Persistent repo intelligence for OpenCode."""


@cli.command()
@click.argument("repo_path", type=click.Path(exists=True))
@click.option("--name", "-n", default=None, help="Display name for the repo")
def init(repo_path: str, name: str | None) -> None:
    """Initialize a repository for tracking."""
    from repo_brain.config import init_repo

    try:
        config = init_repo(repo_path, name=name)
        click.echo(f"Initialized repo: {config.name}")
        click.echo(f"  Path: {config.path}")
        click.echo(f"  Remote: {config.remote_url or '(none detected)'}")
        click.echo(f"  Branch: {config.branch}")
        click.echo(f"  Data dir: {config.data_dir}")
        click.echo()
        click.echo("Next steps:")
        click.echo("  repo-brain setup   # Index, build graph, generate docs (all-in-one)")
        click.echo()
        click.echo("Or run individually:")
        click.echo("  repo-brain index          # Index the codebase")
        click.echo("  repo-brain build-graph    # Build dependency graph")
        click.echo("  repo-brain generate-docs  # Generate architecture docs")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@cli.command()
@click.option("--full", is_flag=True, help="Full re-index (delete existing and rebuild)")
@click.option("--repo", "-r", default=None, help="Repo name or path (auto-detects if omitted)")
def index(full: bool, repo: str | None) -> None:
    """Index the repository codebase."""
    config = _resolve_config(repo)
    if not config:
        raise SystemExit(1)

    from pathlib import Path

    from repo_brain.ingestion.chunker import chunk_file
    from repo_brain.ingestion.scanner import get_language, scan_files
    from repo_brain.storage.metadata_db import MetadataDB, compute_file_hash
    from repo_brain.storage.vector_store import VectorStore

    click.echo(f"Indexing: {config.name} ({config.path})")

    # Initialize stores
    store = VectorStore(config)
    metadata_db = MetadataDB(config)

    if full:
        click.echo("Full re-index: clearing existing data...")
        store.delete_all()

    # Get existing index for incremental
    existing_index = metadata_db.get_all_indexed_files()

    # Scan files
    click.echo("Scanning files...")
    files = scan_files(config)
    click.echo(f"Found {len(files)} files")

    # Track progress
    run_id = metadata_db.start_index_run()
    files_indexed = 0
    files_skipped = 0
    total_chunks = 0

    # Process in batches for embedding efficiency
    batch_metadata: list[dict] = []
    batch_ids: list[str] = []
    batch_documents: list[str] = []
    batch_size = 200  # Chunks per embedding batch

    repo_root = Path(config.path)
    start_time = time.time()

    with click.progressbar(files, label="Indexing", show_pos=True) as progress:
        for file_path in progress:
            try:
                rel_path = str(file_path.relative_to(repo_root))
            except ValueError:
                continue

            # Check if file changed (incremental)
            if not full:
                file_hash = compute_file_hash(file_path)
                existing_hash = existing_index.get(rel_path)
                if existing_hash == file_hash:
                    files_skipped += 1
                    continue
            else:
                file_hash = compute_file_hash(file_path)

            # Chunk the file
            chunks = chunk_file(file_path, config)
            if not chunks:
                files_skipped += 1
                continue

            # Delete old chunks for this file (incremental update)
            if not full and rel_path in existing_index:
                store.delete_by_file(rel_path)

            for chunk in chunks:
                batch_ids.append(chunk.chunk_id)
                batch_documents.append(chunk.to_document())
                batch_metadata.append(
                    {
                        "file_path": chunk.file_path,
                        "language": chunk.language,
                        "symbol_name": chunk.symbol_name,
                        "symbol_type": chunk.symbol_type,
                        "service": chunk.service,
                        "line_start": chunk.line_start,
                        "line_end": chunk.line_end,
                    }
                )

            # Flush batch if large enough
            if len(batch_ids) >= batch_size:
                _flush_batch(store, config, batch_ids, batch_documents, batch_metadata)
                total_chunks += len(batch_ids)
                batch_ids.clear()
                batch_documents.clear()
                batch_metadata.clear()

            # Update metadata DB
            language = get_language(file_path)
            service = chunks[0].service if chunks else ""
            line_count = sum(c.line_end - c.line_start + 1 for c in chunks)
            metadata_db.update_file(rel_path, file_hash, language, service, len(chunks), line_count)
            files_indexed += 1

    # Flush remaining
    if batch_ids:
        _flush_batch(store, config, batch_ids, batch_documents, batch_metadata)
        total_chunks += len(batch_ids)

    elapsed = time.time() - start_time
    metadata_db.complete_index_run(run_id, len(files), files_indexed, files_skipped, total_chunks)
    metadata_db.close()

    click.echo()
    click.echo(f"Done in {elapsed:.1f}s")
    click.echo(f"  Files indexed: {files_indexed}")
    click.echo(f"  Files skipped (unchanged): {files_skipped}")
    click.echo(f"  Chunks created: {total_chunks}")
    click.echo(f"  Vector store total: {store.count}")


def _flush_batch(
    store: object,
    config: object,
    ids: list[str],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    """Generate embeddings and store a batch of chunks."""
    from repo_brain.ingestion.embedder import generate_embeddings

    embeddings = generate_embeddings(documents, model_name=config.embedding_model)  # type: ignore[union-attr]
    store.add_chunks(ids, documents, embeddings, metadatas)  # type: ignore[union-attr]


@cli.command()
@click.argument("query")
@click.option("--limit", "-l", default=10, help="Max results")
@click.option("--service", "-s", default=None, help="Filter by service name")
@click.option("--language", default=None, help="Filter by language")
@click.option("--repo", "-r", default=None, help="Repo name or path")
def search(
    query: str, limit: int, service: str | None, language: str | None, repo: str | None
) -> None:
    """Search the codebase semantically."""
    config = _resolve_config(repo)
    if not config:
        raise SystemExit(1)

    from repo_brain.tools.search import search_code

    click.echo(f"Searching: {query}")
    click.echo()

    results = search_code(
        query=query,
        config=config,
        limit=limit,
        service_filter=service,
        language_filter=language,
    )

    if not results:
        click.echo("No results found.")
        return

    for i, r in enumerate(results, 1):
        score = r["score"]
        path = r["file_path"]
        symbol = r["symbol_name"]
        stype = r["symbol_type"]
        svc = r["service"]

        header = f"[{i}] {path}"
        if symbol:
            header += f" — {stype}: {symbol}"
        if svc:
            header += f" ({svc})"

        click.secho(header, bold=True)
        click.echo(f"    Score: {score}  Lines: {r['line_start']}-{r['line_end']}")
        if r["snippet"]:
            for line in r["snippet"].splitlines()[:10]:
                click.echo(f"    {line}")
        click.echo()


@cli.command()
@click.option("--repo", "-r", default=None, help="Repo name or path")
def status(repo: str | None) -> None:
    """Show index status and statistics."""
    config = _resolve_config(repo)
    if not config:
        raise SystemExit(1)

    from repo_brain.storage.metadata_db import MetadataDB
    from repo_brain.storage.vector_store import VectorStore

    db = MetadataDB(config)
    stats = db.get_stats()
    db.close()

    store = VectorStore(config)

    click.echo(f"Repo: {config.name}")
    click.echo(f"Path: {config.path}")
    click.echo(f"Data: {config.data_dir}")
    click.echo()
    click.echo(f"Files indexed: {stats['total_files']}")
    click.echo(f"Total chunks:  {stats['total_chunks']}")
    click.echo(f"Vector store:  {store.count} chunks")
    click.echo()

    if stats["languages"]:
        click.echo("Languages:")
        for lang, count in stats["languages"].items():
            click.echo(f"  {lang}: {count} files")

    if stats["services"]:
        click.echo()
        click.echo("Services:")
        for svc, count in list(stats["services"].items())[:20]:
            click.echo(f"  {svc}: {count} files")

    if stats["last_run"]:
        run = stats["last_run"]
        click.echo()
        click.echo(f"Last index run: {run['completed_at'] or run['started_at']}")
        click.echo(f"  Status: {run['status']}")
        click.echo(f"  Files: {run['files_indexed']} indexed, {run['files_skipped']} skipped")
        click.echo(f"  Chunks: {run['chunks_created']}")


@cli.command("generate-docs")
@click.option("--repo", "-r", default=None, help="Repo name or path")
def generate_docs(repo: str | None) -> None:
    """Generate architecture documentation (one-shot)."""
    config = _resolve_config(repo)
    if not config:
        raise SystemExit(1)

    from repo_brain.generators.architecture import save_generated_docs

    click.echo(f"Generating docs for: {config.name}")
    created = save_generated_docs(config)

    for name, path in created.items():
        click.echo(f"  Created: {name} -> {path}")

    click.echo()
    click.echo("These docs are a starting point. Edit them to add domain knowledge.")


@cli.command()
@click.option("--full", is_flag=True, help="Full re-index (delete existing and rebuild)")
@click.option("--repo", "-r", default=None, help="Repo name or path")
@click.pass_context
def setup(ctx: click.Context, full: bool, repo: str | None) -> None:
    """Run the full pipeline: index, build-graph, generate-docs."""
    click.echo("=" * 40)
    click.echo("Step 1/3: Indexing")
    click.echo("=" * 40)
    ctx.invoke(index, full=full, repo=repo)

    click.echo()
    click.echo("=" * 40)
    click.echo("Step 2/3: Building dependency graph")
    click.echo("=" * 40)
    ctx.invoke(build_graph_cmd, repo=repo)

    click.echo()
    click.echo("=" * 40)
    click.echo("Step 3/3: Generating docs")
    click.echo("=" * 40)
    ctx.invoke(generate_docs, repo=repo)

    click.echo()
    click.echo("Setup complete. repo-brain is ready to use.")


@cli.command("build-graph")
@click.option("--repo", "-r", default=None, help="Repo name or path")
def build_graph_cmd(repo: str | None) -> None:
    """Build the dependency graph from compose.yml, pyproject.toml, and proto files."""
    config = _resolve_config(repo)
    if not config:
        raise SystemExit(1)

    from repo_brain.ingestion.build_graph import build_graph

    click.echo(f"Building dependency graph for: {config.name}")
    stats = build_graph(config)

    click.echo()
    click.echo("Sources:")
    click.echo(f"  Compose: {stats['compose_services']} services, {stats['compose_edges']} edges")
    click.echo(
        f"  pyproject.toml: {stats['toml_components']} components, {stats['toml_edges']} edges"
    )
    click.echo(f"  Proto: {stats['proto_services']} gRPC services, {stats['proto_edges']} edges")
    click.echo()
    click.echo(f"Total: {stats['total_nodes']} nodes, {stats['total_edges']} edges")
    click.echo(f"Saved to: {config.data_dir / 'graph.json'}")


@cli.command()
@click.option("--pull/--no-pull", default=True, help="Git fetch before indexing")
@click.option("--repo", "-r", default=None, help="Repo name or path")
def refresh(pull: bool, repo: str | None) -> None:
    """Pull latest changes and re-index modified files."""
    config = _resolve_config(repo)
    if not config:
        raise SystemExit(1)

    from repo_brain.tools.refresh import refresh_index

    click.echo(f"Refreshing: {config.name}")
    result = refresh_index(config, pull=pull)

    if result["pulled"]:
        click.echo(f"  Fetched from origin/{config.branch}")
    if result["changed_files"]:
        click.echo(f"  Changed files: {len(result['changed_files'])}")
        for f in result["changed_files"][:20]:
            click.echo(f"    {f}")
        if len(result["changed_files"]) > 20:
            click.echo(f"    ... and {len(result['changed_files']) - 20} more")
    click.echo(f"  Re-indexed: {result['reindexed']} files")
    if result["errors"]:
        click.echo("  Errors:")
        for err in result["errors"]:
            click.echo(f"    {err}")


@cli.command("list")
def list_repos() -> None:
    """List all registered repositories."""
    from repo_brain.config import list_repos as _list_repos

    repos = _list_repos()
    if not repos:
        click.echo("No repos registered. Run `repo-brain init <path>` to add one.")
        return

    for config in repos:
        click.echo(f"{config.name}")
        click.echo(f"  Path: {config.path}")
        click.echo(f"  Remote: {config.remote_url or '(none)'}")
        click.echo(f"  Data: {config.data_dir}")
        click.echo()


@cli.command()
def serve() -> None:
    """Start the MCP server (usually OpenCode does this automatically)."""
    click.echo("Starting MCP server on stdio...", err=True)
    from repo_brain.mcp_server import main

    main()


@cli.command("export-model")
def export_model_cmd() -> None:
    """Save the embedding model locally for faster search.

    One-time operation. Downloads the model and saves it to ~/.repo-brain/models/.
    Future searches load from local disk with no network calls.
    """
    from repo_brain.ingestion.embedder import export_model

    click.echo("Saving embedding model locally (one-time)...")
    try:
        model_dir = export_model()
        click.echo(f"Done. Model saved to: {model_dir}")
        click.echo("Future searches will load from local cache automatically.")
    except Exception as e:
        click.echo(f"Export failed: {e}", err=True)
        raise SystemExit(1)


def _resolve_config(repo: str | None) -> object | None:
    """Resolve repo config from CLI arg, CWD, or first registered repo."""
    import os

    from repo_brain.config import (
        find_repo_config_by_path,
        list_repos,
        load_repo_config,
    )

    if repo:
        # Try as slug first
        config = load_repo_config(repo)
        if config:
            return config
        # Try as path
        config = find_repo_config_by_path(os.path.abspath(repo))
        if config:
            return config
        click.echo(
            f"Error: Repo '{repo}' not found. Run `repo-brain list` to see registered repos.",
            err=True,
        )
        return None

    # Try CWD
    config = find_repo_config_by_path(os.getcwd())
    if config:
        return config

    # Try first registered repo
    repos = list_repos()
    if repos:
        return repos[0]

    click.echo("Error: No repo configured. Run `repo-brain init <path>` first.", err=True)
    return None


if __name__ == "__main__":
    cli()
