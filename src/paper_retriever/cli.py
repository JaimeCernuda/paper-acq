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
  institutional:
    enabled: false  # Enable if you have university access
    priority: 6
  web_search:
    enabled: false  # Requires Claude Agent SDK
    priority: 9

# Institutional Access (for IEEE, ACM, etc. via your university)
# Two modes available:
#   1. VPN mode: Connect to university VPN, set vpn_enabled: true
#   2. EZProxy mode: Set proxy_url, then run 'paper-retriever auth'
institutional:
  enabled: false
  vpn_enabled: false  # Set true if using VPN instead of EZProxy
  proxy_url: null  # e.g., "https://ezproxy.gl.iit.edu/login?url="
  cookies_file: ".institutional_cookies.pkl"

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

    # Show institutional access status
    click.echo()
    inst = config.institutional
    if inst.get("enabled"):
        click.echo("Institutional access:")
        if inst.get("vpn_enabled"):
            click.echo(click.style("  Mode: VPN", fg="green"))
            vpn_script = inst.get("vpn_script")
            if vpn_script:
                script_exists = Path(vpn_script).exists()
                if script_exists:
                    click.echo(f"  VPN script: {vpn_script}")
                else:
                    click.echo(click.style(f"  VPN script: {vpn_script} (not found)", fg="red"))
            else:
                click.echo(click.style("  VPN script: not configured", fg="yellow"))
                click.echo("  Add vpn_script to config.yaml")
        elif inst.get("proxy_url"):
            click.echo("  Mode: EZProxy")
            click.echo(f"  Proxy URL: {inst.get('proxy_url')}")
            cookies_file = Path(inst.get("cookies_file", ".institutional_cookies.pkl"))
            if cookies_file.exists():
                click.echo(click.style("  Authentication: saved", fg="green"))
            else:
                click.echo(click.style("  Authentication: not configured", fg="yellow"))
                click.echo("  Run 'paper-retriever auth' to authenticate")


@cli.command()
@click.pass_context
def auth(ctx: click.Context) -> None:
    """Authenticate with your institution for access to IEEE, ACM, etc.

    Two authentication modes are supported:

    1. VPN Mode: Runs your VPN connection script
       Configure with vpn_enabled: true and vpn_script: "/path/to/script.sh"

    2. EZProxy Mode: Opens browser for Shibboleth/SAML login
       Configure with proxy_url: "https://ezproxy.your-university.edu/login?url="

    Example:

        paper-retriever auth
    """
    config = Config.load(ctx.obj["config_path"])

    if not config.institutional.get("enabled"):
        click.echo(click.style("Error: ", fg="red") + "Institutional access not enabled in config")
        click.echo()
        click.echo("Add the following to your config.yaml:")
        click.echo()
        click.echo("  institutional:")
        click.echo("    enabled: true")
        click.echo("    # For VPN mode:")
        click.echo('    vpn_enabled: true')
        click.echo('    vpn_script: "/path/to/vpn-connect.sh"')
        click.echo("    # OR for EZProxy mode:")
        click.echo('    proxy_url: "https://ezproxy.your-university.edu/login?url="')
        return

    from paper_retriever.clients.institutional import InstitutionalAccessClient

    inst = config.institutional

    # VPN mode with script
    if inst.get("vpn_enabled"):
        vpn_script = inst.get("vpn_script")
        if not vpn_script:
            click.echo(click.style("Error: ", fg="red") + "VPN mode enabled but no vpn_script configured")
            click.echo()
            click.echo("Add the VPN connection script to config.yaml:")
            click.echo()
            click.echo("  institutional:")
            click.echo("    enabled: true")
            click.echo("    vpn_enabled: true")
            click.echo('    vpn_script: "/path/to/vpn-connect.sh"')
            return

        client = InstitutionalAccessClient(
            vpn_enabled=True,
            vpn_script=vpn_script,
        )

        success = client.connect_vpn()
        if success:
            click.echo()
            click.echo(click.style("Success! ", fg="green") + "VPN connected. You can now download papers.")
        else:
            click.echo(click.style("VPN connection failed.", fg="red"))
        return

    # EZProxy mode
    if not inst.get("proxy_url"):
        click.echo(click.style("Error: ", fg="red") + "No proxy_url or vpn_script configured")
        click.echo("Set your institution's EZProxy URL or VPN script in config.yaml")
        return

    client = InstitutionalAccessClient(
        proxy_url=inst.get("proxy_url"),
        vpn_enabled=False,
        cookies_file=inst.get("cookies_file", ".institutional_cookies.pkl"),
    )

    try:
        success = client.authenticate_interactive()
        if success:
            click.echo()
            click.echo(click.style("Success! ", fg="green") + "You can now download papers via institutional access.")
        else:
            click.echo(click.style("Authentication failed.", fg="red"))
    except ImportError as e:
        click.echo(click.style("Error: ", fg="red") + str(e))
        click.echo()
        click.echo("Install Selenium with: pip install selenium webdriver-manager")


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
