# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Paper PDF Retriever is a Python tool that downloads academic papers from multiple open access sources. It takes DOIs or titles as input and searches sources in priority order (Unpaywall, arXiv, PMC, bioRxiv, Semantic Scholar, institutional access, web search) until a PDF is found.

## Commands

### Development Setup
```bash
uv sync                      # Install dependencies
uv sync --extra institutional  # Include Selenium for institutional access
```

### Running the CLI
```bash
paper-retriever get --doi "10.1038/nature12373"
paper-retriever get --title "Attention Is All You Need"
paper-retriever batch papers.txt
paper-retriever init           # Create config.yaml
paper-retriever sources        # List enabled sources
paper-retriever auth           # Authenticate institutional access
```

### Testing
```bash
uv run pytest tests/                    # Run all tests
uv run pytest tests/test_arxiv.py       # Run single test file
uv run pytest tests/test_arxiv.py -v    # Verbose output
```

## Architecture

### Core Flow
1. `cli.py` handles command-line interface (Click-based)
2. `retriever.py` orchestrates the retrieval - `PaperRetriever.retrieve()` is the main entry point
3. `config.py` loads YAML config with env var overrides
4. `rate_limiter.py` enforces per-source rate limits

### Source Clients (`clients/`)
Each source has its own async client. All follow a similar pattern:
- `get_*()` or `search_*()` methods return metadata/PDF URLs
- PDF URLs are downloaded by `PaperRetriever._download_pdf()`

Client priority order is defined in `config.py` default_sources dict. The retriever tries each enabled source until a PDF is found.

### Institutional Access
Two modes:
1. **VPN mode**: Runs user's VPN script (`vpn_script` config), then downloads directly
2. **EZProxy mode**: Uses Selenium for Shibboleth auth, saves cookies to `.institutional_cookies.pkl`

### Key Data Types
- `RetrievalResult`: Contains status (success/not_found/error/skipped), pdf_path, source, metadata
- `Config`: Dataclass with email, api_keys, sources, download settings, rate_limits

## Configuration
Config loads from `config.yaml` with env var overrides:
- `PAPER_RETRIEVER_EMAIL` - User email (required)
- `NCBI_API_KEY` - PubMed/PMC higher rate limits
- `SEMANTIC_SCHOLAR_API_KEY` - Semantic Scholar API key
