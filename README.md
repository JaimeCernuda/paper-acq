# Paper PDF Retriever

A Python tool to retrieve academic paper PDFs from multiple open access sources.

## Features

- **Multiple Sources**: Tries Unpaywall, arXiv, PubMed Central, bioRxiv/medRxiv, and Semantic Scholar
- **Smart Metadata Resolution**: Resolves paper metadata via CrossRef API
- **Batch Processing**: Process multiple papers from CSV, JSON, or text files
- **Rate Limiting**: Respects API rate limits to avoid being blocked
- **Configurable**: YAML configuration with environment variable overrides
- **Caching**: Skips already-downloaded papers

## Installation

```bash
# Using uv (recommended)
uv pip install .

# Or with pip
pip install .
```

## Quick Start

1. Initialize configuration:

```bash
paper-retriever init
```

2. Edit `config.yaml` and add your email address (required for API access).

3. Download a paper:

```bash
# By DOI
paper-retriever get --doi "10.1038/nature12373"

# By title
paper-retriever get --title "Attention Is All You Need"

# Specify output directory
paper-retriever get --doi "10.1145/3292500.3330919" -o ./papers
```

## Batch Processing

Create a text file with DOIs (one per line):

```text
10.1038/nature12373
10.1145/3292500.3330919
10.48550/arXiv.1706.03762
```

Or a CSV file:

```csv
doi,title
10.1038/nature12373,
,Attention Is All You Need
```

Then run:

```bash
paper-retriever batch papers.txt
paper-retriever batch papers.csv --format csv
```

## Configuration

Copy `config.yaml.example` to `config.yaml` and customize:

```yaml
user:
  email: "your.email@university.edu"

sources:
  unpaywall:
    enabled: true
    priority: 1
  arxiv:
    enabled: true
    priority: 2
  # ... more sources

download:
  output_dir: "./downloads"
  skip_existing: true
```

### Environment Variables

- `PAPER_RETRIEVER_EMAIL`: Your email address
- `NCBI_API_KEY`: NCBI API key for higher PMC rate limits
- `SEMANTIC_SCHOLAR_API_KEY`: Semantic Scholar API key

## API Rate Limits

| Source | Rate Limit | Notes |
|--------|------------|-------|
| CrossRef | 50 req/sec (shared) | Use `mailto` parameter |
| Unpaywall | 100k/day | Very permissive |
| arXiv | 1 req/3 sec | Use `export.arxiv.org` |
| PMC | 3 req/sec (10 with key) | NCBI account for key |
| Semantic Scholar | 100 req/5 min | Free key available |
| bioRxiv | ~1 req/sec | No official limit |

## Sources

The tool tries sources in priority order:

1. **Unpaywall**: Finds legal open access versions
2. **arXiv**: Preprints in physics, math, CS, etc.
3. **PubMed Central**: Open access biomedical literature
4. **bioRxiv/medRxiv**: Biology and medical preprints
5. **Semantic Scholar**: Academic search with OA PDFs

## Python API

```python
import asyncio
from paper_retriever import PaperRetriever, Config

config = Config.load("config.yaml")
retriever = PaperRetriever(config)

# Single paper
result = asyncio.run(retriever.retrieve(doi="10.1038/nature12373"))
print(result.status, result.pdf_path)

# Batch
from paper_retriever.retriever import batch_retrieve

papers = [
    {"doi": "10.1038/nature12373"},
    {"title": "Attention Is All You Need"},
]
results = asyncio.run(batch_retrieve(retriever, papers))
```

## License

MIT
