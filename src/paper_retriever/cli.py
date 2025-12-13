"""Command-line interface for Paper PDF Retriever."""

import asyncio
import csv
import json
from pathlib import Path

import click

from paper_retriever.config import Config
from paper_retriever.retriever import (
    PaperRetriever,
    RetrievalStatus,
    batch_retrieve,
)


@click.group()
@click.option(
    "--config",
    "-c",
    default="config.yaml",
    help="Configuration file path",
    type=click.Path(),
)
@click.pass_context
def cli(ctx: click.Context, config: str) -> None:
    """Academic Paper PDF Retriever.

    Retrieve academic paper PDFs from multiple sources including
    Unpaywall, arXiv, PubMed Central, bioRxiv, and Semantic Scholar.
    """
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config


@cli.command()
@click.option("--doi", "-d", help="Paper DOI")
@click.option("--title", "-t", help="Paper title")
@click.option("--output", "-o", help="Output directory", type=click.Path())
@click.option("--email", "-e", help="Your email (required for API access)")
@click.pass_context
def get(
    ctx: click.Context,
    doi: str | None,
    title: str | None,
    output: str | None,
    email: str | None,
) -> None:
    """Retrieve a single paper PDF.

    You must provide either --doi or --title (or both).

    Examples:

        paper-retriever get --doi "10.1038/nature12373"

        paper-retriever get --title "Attention Is All You Need"

        paper-retriever get -d "10.1145/3292500.3330919" -o ./papers
    """
    if not doi and not title:
        raise click.UsageError("Must provide --doi or --title")

    config = Config.load(ctx.obj["config_path"])

    if email:
        config.email = email

    if not config.email:
        raise click.UsageError(
            "Email required. Provide via --email, config file, or PAPER_RETRIEVER_EMAIL env var"
        )

    if output:
        config.download["output_dir"] = output

    retriever = PaperRetriever(config)
    result = asyncio.run(retriever.retrieve(doi=doi, title=title))

    if result.status == RetrievalStatus.SUCCESS:
        click.echo(click.style("✓ Downloaded: ", fg="green") + str(result.pdf_path))
        click.echo(f"  Source: {result.source}")
        if result.metadata:
            if result.metadata.get("title"):
                click.echo(f"  Title: {result.metadata['title']}")
            if result.metadata.get("first_author"):
                click.echo(f"  Author: {result.metadata['first_author']}")
    elif result.status == RetrievalStatus.SKIPPED:
        click.echo(click.style("→ Skipped: ", fg="yellow") + "Already downloaded")
        click.echo(f"  Path: {result.pdf_path}")
    else:
        click.echo(click.style("✗ Failed: ", fg="red") + str(result.error))
        if result.metadata and result.metadata.get("title"):
            click.echo(f"  Title: {result.metadata['title']}")


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--output", "-o", help="Output directory", type=click.Path())
@click.option(
    "--format",
    "-f",
    "file_format",
    type=click.Choice(["csv", "json", "txt"]),
    default="txt",
    help="Input file format",
)
@click.option("--email", "-e", help="Your email (required for API access)")
@click.option(
    "--concurrent",
    "-n",
    default=3,
    help="Maximum concurrent downloads",
    type=int,
)
@click.pass_context
def batch(
    ctx: click.Context,
    file: str,
    output: str | None,
    file_format: str,
    email: str | None,
    concurrent: int,
) -> None:
    """Retrieve papers from a file.

    Supports CSV (with 'doi' and/or 'title' columns), JSON (array of objects
    with 'doi' and/or 'title' keys), or TXT (one DOI or title per line).

    Examples:

        paper-retriever batch papers.txt

        paper-retriever batch papers.csv --format csv -o ./downloads

        paper-retriever batch papers.json --format json -n 5
    """
    config = Config.load(ctx.obj["config_path"])

    if email:
        config.email = email

    if not config.email:
        raise click.UsageError(
            "Email required. Provide via --email, config file, or PAPER_RETRIEVER_EMAIL env var"
        )

    if output:
        config.download["output_dir"] = output

    # Load papers from file
    papers = _load_papers_from_file(file, file_format)
    if not papers:
        click.echo(click.style("No papers found in file", fg="yellow"))
        return

    click.echo(f"Found {len(papers)} papers to retrieve")

    retriever = PaperRetriever(config)
    results = asyncio.run(batch_retrieve(retriever, papers, max_concurrent=concurrent))

    # Report results
    success = sum(1 for r in results if r.status == RetrievalStatus.SUCCESS)
    skipped = sum(1 for r in results if r.status == RetrievalStatus.SKIPPED)
    failed = sum(
        1 for r in results if r.status in (RetrievalStatus.NOT_FOUND, RetrievalStatus.ERROR)
    )

    click.echo()
    click.echo("Results:")
    click.echo(click.style(f"  ✓ Downloaded: {success}", fg="green"))
    if skipped:
        click.echo(click.style(f"  → Skipped: {skipped}", fg="yellow"))
    if failed:
        click.echo(click.style(f"  ✗ Failed: {failed}", fg="red"))

    # List failures
    failures = [r for r in results if r.status == RetrievalStatus.NOT_FOUND]
    if failures:
        click.echo()
        click.echo("Failed papers:")
        for r in failures:
            identifier = r.doi or r.title
            click.echo(f"  - {identifier}")


@cli.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize a configuration file.

    Creates a config.yaml file in the current directory with default settings.
    """
    config_path = Path(ctx.obj["config_path"])

    if config_path.exists():
        if not click.confirm(f"{config_path} exists. Overwrite?"):
            return

    default_config = '''# Paper PDF Retriever Configuration
# Edit this file to customize your settings

# Your email (required for polite API access)
user:
  email: "your.email@university.edu"

# API Keys (optional but recommended for higher rate limits)
api_keys:
  ncbi: null  # Get from https://www.ncbi.nlm.nih.gov/account/settings/
  semantic_scholar: null  # Get from https://www.semanticscholar.org/product/api

# Source configuration (ordered by priority)
sources:
  unpaywall:
    enabled: true
    priority: 1
  arxiv:
    enabled: true
    priority: 2
  pmc:
    enabled: true
    priority: 3
  biorxiv:
    enabled: true
    priority: 4
  semantic_scholar:
    enabled: true
    priority: 5

# Download settings
download:
  output_dir: "./downloads"
  skip_existing: true
  max_title_length: 50

# Rate limiting (seconds between requests per source)
rate_limits:
  global_delay: 1.0
  per_source_delays:
    crossref: 0.5
    unpaywall: 0.1
    arxiv: 3.0
    pmc: 0.34
    semantic_scholar: 3.0
    biorxiv: 1.0

# Batch processing
batch:
  max_concurrent: 3
  retry_failed: true
  max_retries: 2
'''

    config_path.write_text(default_config)
    click.echo(f"Created {config_path}")
    click.echo("Please edit the file and set your email address.")


@cli.command()
@click.pass_context
def sources(ctx: click.Context) -> None:
    """List available sources and their status."""
    config = Config.load(ctx.obj["config_path"])

    click.echo("Available sources:")
    click.echo()

    sorted_sources = []
    for name, settings in config.sources.items():
        sorted_sources.append((settings.get("priority", 99), name, settings))

    sorted_sources.sort(key=lambda x: x[0])

    for priority, name, settings in sorted_sources:
        enabled = settings.get("enabled", False)
        status = click.style("enabled", fg="green") if enabled else click.style("disabled", fg="red")
        click.echo(f"  {priority}. {name}: {status}")


def _load_papers_from_file(filepath: str, file_format: str) -> list[dict[str, str | None]]:
    """Load paper identifiers from file.

    Args:
        filepath: Path to the file.
        file_format: Format of the file (csv, json, txt).

    Returns:
        List of dicts with 'doi' and/or 'title' keys.
    """
    path = Path(filepath)

    if file_format == "json":
        with open(path) as f:
            data = json.load(f)
            if isinstance(data, list):
                return [{"doi": p.get("doi"), "title": p.get("title")} for p in data]
            return []

    elif file_format == "csv":
        papers = []
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                papers.append({"doi": row.get("doi"), "title": row.get("title")})
        return papers

    else:  # txt - one DOI or title per line
        papers = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("10."):  # DOI
                    papers.append({"doi": line, "title": None})
                else:
                    papers.append({"doi": None, "title": line})
        return papers


if __name__ == "__main__":
    cli()
