"""arXiv API client for preprint access."""

from pathlib import Path
from typing import Any

import arxiv


class ArxivClient:
    """Client for the arXiv API."""

    def __init__(self):
        """Initialize the arXiv client."""
        self.client = arxiv.Client(
            page_size=100,
            delay_seconds=3,  # Respect rate limit
            num_retries=3,
        )

    async def search_by_doi(self, doi: str) -> arxiv.Result | None:
        """Search arXiv by DOI (if available in metadata).

        Args:
            doi: The DOI to look up. Works best with arXiv DOIs.

        Returns:
            arXiv result or None if not found.
        """
        # arXiv DOIs have pattern 10.48550/arXiv.{id}
        if "arxiv" in doi.lower():
            arxiv_id = doi.split("arXiv.")[-1] if "arXiv." in doi else doi.split("arxiv.")[-1]
            search = arxiv.Search(id_list=[arxiv_id])
            results = list(self.client.results(search))
            return results[0] if results else None
        return None

    async def search_by_title(
        self, title: str, max_results: int = 5
    ) -> list[arxiv.Result]:
        """Search arXiv by title.

        Args:
            title: The title to search for.
            max_results: Maximum number of results.

        Returns:
            List of arXiv results.
        """
        search = arxiv.Search(
            query=f'ti:"{title}"',
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        return list(self.client.results(search))

    async def download_pdf(self, result: arxiv.Result, output_dir: str | Path) -> str:
        """Download PDF for an arXiv result.

        Args:
            result: The arXiv result to download.
            output_dir: Directory to save the PDF.

        Returns:
            Path to the downloaded PDF.
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        return result.download_pdf(dirpath=str(output_path))

    def get_pdf_url(self, result: arxiv.Result) -> str:
        """Get the PDF URL for an arXiv result.

        Args:
            result: The arXiv result.

        Returns:
            Direct PDF URL.
        """
        return result.pdf_url

    @staticmethod
    def result_to_dict(result: arxiv.Result) -> dict[str, Any]:
        """Convert arXiv result to metadata dict.

        Args:
            result: The arXiv result.

        Returns:
            Metadata dict.
        """
        return {
            "arxiv_id": result.entry_id.split("/")[-1],
            "title": result.title,
            "authors": [author.name for author in result.authors],
            "first_author": result.authors[0].name if result.authors else "Unknown",
            "summary": result.summary,
            "published": result.published.isoformat() if result.published else None,
            "pdf_url": result.pdf_url,
            "doi": result.doi,
            "categories": result.categories,
        }
