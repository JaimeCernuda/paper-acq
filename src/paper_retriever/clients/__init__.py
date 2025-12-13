"""API clients for various paper sources."""

from paper_retriever.clients.crossref import CrossRefClient
from paper_retriever.clients.unpaywall import UnpaywallClient
from paper_retriever.clients.arxiv_client import ArxivClient
from paper_retriever.clients.pmc import PMCClient
from paper_retriever.clients.biorxiv import BioRxivClient
from paper_retriever.clients.semantic_scholar import SemanticScholarClient

__all__ = [
    "CrossRefClient",
    "UnpaywallClient",
    "ArxivClient",
    "PMCClient",
    "BioRxivClient",
    "SemanticScholarClient",
]
