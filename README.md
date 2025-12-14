# Paper PDF Retriever

**Download academic papers automatically from multiple sources.**

Got a list of papers you need? This tool will find and download PDFs from open access sources, and optionally through your university's subscription access.

## What It Does

1. You give it a DOI or title
2. It searches multiple sources (Unpaywall, arXiv, PubMed Central, etc.)
3. It downloads the PDF to your computer

Works with single papers or a batch of hundreds.

---

## Installation

```bash
# Clone and install
git clone <repo-url>
cd paper-pdf-retriever

# Using uv (recommended)
uv sync

# Or with pip
pip install .
```

---

## Quick Start

### 1. Create a config file

```bash
paper-retriever init
```

### 2. Add your email

Edit `config.yaml` and set your email (required by APIs for polite access):

```yaml
user:
  email: "your.email@university.edu"
```

### 3. Download a paper

```bash
# By DOI
paper-retriever get --doi "10.1038/nature12373"

# By title
paper-retriever get --title "Attention Is All You Need"

# Specify where to save
paper-retriever get --doi "10.1145/3292500.3330919" -o ./papers
```

That's it! The PDF will be saved to `./downloads/` (or wherever you specify).

---

## Batch Processing

Have a list of papers? Put them in a file:

**Option 1: Text file (one DOI per line)**
```
10.1038/nature12373
10.1145/3292500.3330919
10.48550/arXiv.1706.03762
```

**Option 2: CSV file**
```csv
doi,title
10.1038/nature12373,
,Attention Is All You Need
10.1145/3292500.3330919,
```

Then run:
```bash
paper-retriever batch papers.txt
paper-retriever batch papers.csv --format csv
```

The tool will download all papers, skipping any you've already got.

---

## Sources (What Gets Searched)

The tool tries these sources in order:

| Priority | Source | What It Has |
|----------|--------|-------------|
| 1 | **Unpaywall** | Legal open access versions from publishers & repositories |
| 2 | **arXiv** | Preprints in physics, math, CS, quantitative biology |
| 3 | **PubMed Central** | Open access biomedical literature |
| 4 | **bioRxiv/medRxiv** | Biology and medical preprints |
| 5 | **Semantic Scholar** | Academic papers with open access PDFs |
| 6 | **Institutional** | IEEE, ACM, Elsevier via your university (optional) |

You can enable/disable sources and change priorities in `config.yaml`.

---

## University/Institutional Access

If you have a university subscription, you can download papers from IEEE, ACM, Elsevier, and other publishers.

### Two Options

**Option A: VPN Mode with Script**

If your university provides VPN access, create a script that connects to it:

```bash
# Example: scripts/vpn-connect.sh
#!/bin/bash
# Your VPN connection command here
# Examples:
# openconnect vpn.youruni.edu
# sudo openvpn --config ~/vpn/university.ovpn
# nmcli connection up "University VPN"
```

Then configure it:

```yaml
institutional:
  enabled: true
  vpn_enabled: true
  vpn_script: "./scripts/vpn-connect.sh"
  vpn_disconnect_script: "./scripts/vpn-disconnect.sh"  # optional
```

Run authentication to connect:
```bash
paper-retriever auth
```

This runs your VPN script. Once connected, papers download directly.

**Option B: EZProxy Mode (No VPN needed)**

If you can't use VPN, use your university's EZProxy:

```yaml
institutional:
  enabled: true
  vpn_enabled: false
  proxy_url: "https://ezproxy.gl.iit.edu/login?url="  # Your university's URL
```

Then authenticate once:
```bash
paper-retriever auth
```

This opens a browser where you log in through your university. Your session is saved for future use.

### Finding Your Proxy URL

Your proxy URL usually looks like:
- `https://ezproxy.youruni.edu/login?url=`
- `https://proxy.library.youruni.edu/login?url=`

Ask your library or check your library's website for "off-campus access" instructions.

---

## Configuration Reference

### Full config.yaml example

```yaml
# Required: Your email for API access
user:
  email: "you@university.edu"

# Optional: API keys for higher rate limits
api_keys:
  ncbi: null              # Get from https://www.ncbi.nlm.nih.gov/account/settings/
  semantic_scholar: null  # Get from https://www.semanticscholar.org/product/api

# Sources: Enable/disable and set priority (lower = tried first)
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

# Institutional access settings
institutional:
  enabled: false
  vpn_enabled: false
  proxy_url: null  # e.g., "https://ezproxy.youruni.edu/login?url="

# Where to save PDFs
download:
  output_dir: "./downloads"
  skip_existing: true
  max_title_length: 50

# Rate limiting (don't change unless you know what you're doing)
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
```

### Environment Variables

You can also set these via environment variables:

| Variable | Purpose |
|----------|---------|
| `PAPER_RETRIEVER_EMAIL` | Your email (overrides config) |
| `NCBI_API_KEY` | PubMed/PMC API key |
| `SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar API key |

---

## CLI Commands

```bash
# Show help
paper-retriever --help

# Download a single paper
paper-retriever get --doi "10.1234/example"
paper-retriever get --title "Paper Title"
paper-retriever get -d "10.1234/example" -o ./papers -e you@email.com

# Download multiple papers
paper-retriever batch papers.txt
paper-retriever batch papers.csv --format csv -n 5  # 5 concurrent downloads

# Create config file
paper-retriever init

# Show available sources
paper-retriever sources

# Authenticate with your university (for institutional access)
paper-retriever auth

# Sync config across machines (requires GitHub CLI)
paper-retriever config push     # Upload config to private gist
paper-retriever config pull     # Download config from gist
```

---

## Python API

```python
import asyncio
from paper_retriever import PaperRetriever, Config

# Load config
config = Config.load("config.yaml")
retriever = PaperRetriever(config)

# Download a single paper
async def main():
    result = await retriever.retrieve(doi="10.1038/nature12373")
    print(f"Status: {result.status}")
    print(f"Path: {result.pdf_path}")

asyncio.run(main())
```

### Batch processing

```python
from paper_retriever.retriever import batch_retrieve

papers = [
    {"doi": "10.1038/nature12373"},
    {"title": "Attention Is All You Need"},
    {"doi": "10.1145/3292500.3330919"},
]

results = asyncio.run(batch_retrieve(retriever, papers, max_concurrent=3))

for r in results:
    print(f"{r.doi or r.title}: {r.status}")
```

---

## Troubleshooting

### "Email required" error

Add your email to `config.yaml` under `user.email` or use the `-e` flag:
```bash
paper-retriever get -d "10.1234/example" -e you@email.com
```

### Paper not found

The tool only searches open access sources by default. If the paper is behind a paywall:
1. Enable institutional access (see above)
2. Or try the paper's arXiv preprint (many papers have one)

### Rate limiting

If you're getting blocked, the tool is making requests too fast. The default settings are conservative, but you can increase delays in `config.yaml`:

```yaml
rate_limits:
  global_delay: 2.0  # Increase this
```

### Institutional auth not working

1. Make sure your `proxy_url` is correct
2. Clear old cookies: delete `.institutional_cookies.pkl`
3. Run `paper-retriever auth` again
4. Complete the login fully before pressing Enter

---

## Limitations & Known Issues

### Sources That Don't Work

| Source | Status | Why |
|--------|--------|-----|
| **ScienceDirect/Elsevier** | Not supported | Elsevier removed PDF support from their API in August 2017. Only XML is returned. Direct scraping is blocked by aggressive bot detection (Incapsula/Imperva). |
| **Springer** | Not supported | No public API for PDF access. Requires institutional subscription + authentication. |
| **Wiley** | Not supported | Same as Springer. TDM API exists but requires institutional agreement. |
| **Taylor & Francis** | Not supported | No public PDF API. |

### Sources With Caveats

| Source | Issue | Workaround |
|--------|-------|------------|
| **Semantic Scholar** | Aggressive rate limiting (429 errors) | Use 3+ second delays. Get an [API key](https://www.semanticscholar.org/product/api) for higher limits. Not all papers have OA PDFs. |
| **bioRxiv/medRxiv** | Occasional 403 blocks | Tool adds required headers automatically. If blocked, wait and retry. |
| **Institutional** | Requires active session | Re-run `paper-retriever auth` if cookies expire. VPN mode may be more reliable than EZProxy. |

### What This Means

For paywalled papers not in open access repositories, you'll need:
1. **Institutional access** via VPN or EZProxy (if your university provides it)
2. **Check arXiv** - many papers have preprint versions
3. **Email the authors** - most are happy to share PDFs directly
4. **Interlibrary loan** - your library can usually get any paper

### Gray Area Sources

Sci-Hub and LibGen clients exist in the code but are disabled by default. These sources operate in legal gray areas depending on jurisdiction. Enable at your own discretion:

```yaml
sources:
  scihub:
    enabled: true  # Use at your own risk
    priority: 99
  libgen:
    enabled: true  # Use at your own risk
    priority: 99
```

---

## Rate Limits

The tool respects API rate limits to avoid getting blocked:

| Source | Rate Limit | Notes |
|--------|------------|-------|
| CrossRef | 50 req/sec (shared pool) | Uses polite pool with email |
| Unpaywall | 100,000/day | Very permissive |
| arXiv | 1 request/3 sec | Official limit |
| PubMed Central | 3 req/sec (10 with key) | Get API key for more |
| Semantic Scholar | 100 req/5 min | Free API key available |
| bioRxiv | ~1 req/sec | No official limit |

---

## Contributing

Pull requests welcome! Please run tests before submitting:

```bash
uv run pytest tests/
```

---

## License

MIT
