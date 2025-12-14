"""Semantic Scholar API client for academic paper search."""

from typing import Any

import httpx


class SemanticScholarClient:
    """Client for the Semantic Scholar API."""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: str | None = None):
        """Initialize the Semantic Scholar client.

        Args:
            api_key: API key for higher rate limits.
        """
        self.api_key = api_key
        self.headers: dict[str, str] = {}
        if api_key:
            self.headers["x-api-key"] = api_key
        self.delay = 0.01 if api_key else 3.0  # ~100/5min = 1 per 3 sec

    async def get_paper(self, identifier: str) -> dict[str, Any] | None:
        """Get paper with open access PDF URL.

        Args:
            identifier: Paper identifier - DOI, CorpusID, ArXiv ID, etc.
                       If it looks like a DOI (contains '/'), adds DOI: prefix.
                       Otherwise uses the identifier as-is.

        Returns:
            Dict with paper info and PDF URL, or None if not found.
        """
        # Determine ID format - DOIs contain '/', CorpusIDs are numeric
        if "/" in identifier:
            paper_id = f"DOI:{identifier}"
        elif identifier.isdigit():
            paper_id = f"CorpusID:{identifier}"
        else:
            paper_id = identifier  # Already prefixed (e.g., "CorpusID:123")
        url = f"{self.BASE_URL}/paper/{paper_id}"
        params = {"fields": "title,authors,openAccessPdf,externalIds,year,venue"}

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.get(url, params=params, headers=self.headers)
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                data = response.json()

                result = {
                    "title": data.get("title"),
                    "authors": [
                        author.get("name") for author in data.get("authors", [])
                    ],
                    "year": data.get("year"),
                    "venue": data.get("venue"),
                    "external_ids": data.get("externalIds", {}),
                }

                if data.get("openAccessPdf"):
                    result["pdf_url"] = data["openAccessPdf"].get("url")
                    result["pdf_status"] = data["openAccessPdf"].get("status")

                return result
            except httpx.HTTPStatusError:
                return None

    async def search_title(
        self, title: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Search for papers by title.

        Args:
            title: The title to search for.
            limit: Maximum number of results.

        Returns:
            List of paper results.
        """
        url = f"{self.BASE_URL}/paper/search"
        params = {
            "query": title,
            "fields": "title,openAccessPdf,externalIds,authors,year",
            "limit": limit,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.get(url, params=params, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                return data.get("data", [])
            except httpx.HTTPStatusError:
                return []

    async def get_paper_by_arxiv_id(self, arxiv_id: str) -> dict[str, Any] | None:
        """Get paper by arXiv ID.

        Args:
            arxiv_id: The arXiv ID to look up.

        Returns:
            Paper info or None if not found.
        """
        url = f"{self.BASE_URL}/paper/ARXIV:{arxiv_id}"
        params = {"fields": "title,authors,openAccessPdf,externalIds,year,venue"}

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.get(url, params=params, headers=self.headers)
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                data = response.json()

                result = {
                    "title": data.get("title"),
                    "authors": [
                        author.get("name") for author in data.get("authors", [])
                    ],
                    "year": data.get("year"),
                    "venue": data.get("venue"),
                    "external_ids": data.get("externalIds", {}),
                }

                if data.get("openAccessPdf"):
                    result["pdf_url"] = data["openAccessPdf"].get("url")
                    result["pdf_status"] = data["openAccessPdf"].get("status")

                return result
            except httpx.HTTPStatusError:
                return None
